import boto3
import json
import time
import zipfile
import os
from botocore.exceptions import ClientError

# --- KONFIGURASYON ---
PROJECT_NAME = "s3-metadata-indexer"

# AWS Kaynak isimleri (Bunlar AWS'de görünecek isimler)
# Not: S3 Bucket isimleri dünyada essiz (unique) olmali. 
# Eger hata alirsan sonuna rastgele sayi ekle (or: v1-99)
BUCKET_NAME = f"{PROJECT_NAME}-bucket-v2" 
TABLE_NAME = f"{PROJECT_NAME}-table"
LAMBDA_FUNC_NAME = f"{PROJECT_NAME}-func"
ROLE_NAME = f"{PROJECT_NAME}-role"
REGION = "eu-central-1" # Kendine uygun bolgeyi sec (us-east-1 genelde standarttir)

# Boto3 Clientlar - AWS ile iletisim kuran ajanlarimiz
s3_client = boto3.client('s3', region_name=REGION)
lambda_client = boto3.client('lambda', region_name=REGION)
dynamodb_client = boto3.client('dynamodb', region_name=REGION)
iam_client = boto3.client('iam', region_name=REGION)

def create_iam_role():
    """
    Console: IAM > Roles > Create Role
    Lambda fonksiyonuna yetki karti (Kimlik) olusturur.
    """
    print(f"[IAM] Rol olusturuluyor: {ROLE_NAME}...")
    
    # 1. Trust Policy: "Bu rolu sadece Lambda servisi takabilir" kurali
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }

    try:
        role = iam_client.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy)
        )
        
        # 2. Izinler: Lambda log yazabilsin ve DynamoDB'ye erisebilsin
        # Console'da "Add Permissions" dedigin kisim burasi.
        iam_client.attach_role_policy(
            RoleName=ROLE_NAME,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        )
        iam_client.attach_role_policy(
            RoleName=ROLE_NAME,
            PolicyArn="arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
        )
        
        print(f"[IAM] Rol hazir. Propagasyon icin 10sn bekleniyor... (AWS'nin uyanmasi lazim)")
        time.sleep(10) # IAM yetkilerinin aktif olmasi bazen zaman alir, beklemezsek hata verir.
        return role['Role']['Arn']
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"[IAM] Rol zaten mevcut. Mevcut olani kullaniyoruz...")
            role = iam_client.get_role(RoleName=ROLE_NAME)
            return role['Role']['Arn']
        else:
            raise e

def create_dynamodb_table():
    """
    Console: DynamoDB > Create Table
    """
    print(f"[DynamoDB] Tablo olusturuluyor: {TABLE_NAME}...")
    try:
        table = dynamodb_client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{'AttributeName': 'file_name', 'KeyType': 'HASH'}], # Partition Key
            AttributeDefinitions=[{'AttributeName': 'file_name', 'AttributeType': 'S'}], # String
            ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1} # Free Tier dostu en dusuk ayar
        )
        # Tablo "Creating" modundan "Active" moduna gecene kadar bekle
        waiter = dynamodb_client.get_waiter('table_exists')
        waiter.wait(TableName=TABLE_NAME)
        print(f"[DynamoDB] Tablo aktif.")
        return table['TableDescription']['TableArn']
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"[DynamoDB] Tablo zaten mevcut.")
        else:
            raise e

def create_s3_bucket():
    """
    S3 > Create Bucket
    """
    print(f"[S3] Bucket olusturuluyor: {BUCKET_NAME}...")
    print(f"[S3] Hedef Bolge: {REGION}") # Hata ayiklama icin bunu ekledik
    
    try:
        if REGION == "us-east-1":
            # Virginia icin ozel durum: LocationConstraint GONDERILMEZ
            s3_client.create_bucket(Bucket=BUCKET_NAME)
        else:
            # Diger tum bolgeler (Frankfurt vb.) icin ZORUNLUDUR
            s3_client.create_bucket(
                Bucket=BUCKET_NAME,
                CreateBucketConfiguration={'LocationConstraint': REGION}
            )
        print(f"[S3] Bucket hazir.")
        
    except ClientError as e:
        if e.response['Error']['Code'] in ['BucketAlreadyOwnedByYou', 'BucketAlreadyExists']:
            print(f"[S3] Bucket zaten mevcut. Devam ediliyor...")
        else:
            # Hata kodunu detayli gosterelim
            print(f"S3 Hatasi: {e}")
            raise e

def deploy_lambda(role_arn):
    """
    Console: Lambda > Create Function > Upload Zip
    """
    print(f"[Lambda] Kod zipleniyor ve yukleniyor...")
    
    # Python kodunu AWS'ye gondermek icin once ZIP yapmamiz lazim
    zip_output_name = 'lambda_deployment_package.zip'
    with zipfile.ZipFile(zip_output_name, 'w', zipfile.ZIP_DEFLATED) as zip_f:
        # src klasorundeki dosyayi zip'in icine koy
        zip_f.write(os.path.join('src', 'lambda_function.py'), arcname='lambda_function.py')
        
    with open(zip_output_name, 'rb') as f:
        zipped_code = f.read()

    try:
        response = lambda_client.create_function(
            FunctionName=LAMBDA_FUNC_NAME,
            Runtime='python3.9',
            Role=role_arn, # Yukarida olusturdugumuz kimlik kartini veriyoruz
            Handler='lambda_function.lambda_handler', # DosyaAdi.FonksiyonAdi
            Code={'ZipFile': zipped_code},
            Environment={
                'Variables': {'TABLE_NAME': TABLE_NAME} # Ortam degiskeni
            },
            Timeout=15,
            MemorySize=128
        )
        print(f"[Lambda] Fonksiyon olusturuldu.")
        
        os.remove(zip_output_name) # Copu temizle
        return response['FunctionArn']
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceConflictException':
            print(f"[Lambda] Fonksiyon zaten mevcut. Kod guncelleniyor...")
            lambda_client.update_function_code(
                FunctionName=LAMBDA_FUNC_NAME,
                ZipFile=zipped_code
            )
            os.remove(zip_output_name)
            func = lambda_client.get_function(FunctionName=LAMBDA_FUNC_NAME)
            return func['Configuration']['FunctionArn']
        else:
            raise e

def add_s3_trigger(lambda_arn):
    """
    Console: Lambda > Add Trigger > S3
    """
    print(f"[Trigger] S3 bildirimi ayarlaniyor...")
    
    # 1. Lambda'ya "S3 beni dürtebilir" izni ver (Resource Policy)
    try:
        lambda_client.add_permission(
            FunctionName=LAMBDA_FUNC_NAME,
            StatementId=f's3-trigger-permission-{BUCKET_NAME}',
            Action='lambda:InvokeFunction',
            Principal='s3.amazonaws.com',
            SourceArn=f"arn:aws:s3:::{BUCKET_NAME}"
        )
    except ClientError as e:
        if e.response['Error']['Code'] != 'ResourceConflictException':
            raise e

    print("İzinlerin yayilmasi icin 5 saniye bekleniyor...")
    time.sleep(5)

    # 2. S3'e "Dosya gelince bu Lambda'yi calistir" talimati ver
    s3_client.put_bucket_notification_configuration(
        Bucket=BUCKET_NAME,
        NotificationConfiguration={
            'LambdaFunctionConfigurations': [{
                'LambdaFunctionArn': lambda_arn,
                'Events': ['s3:ObjectCreated:*'] # Sadece yeni dosya olusunca
            }]
        }
    )
    print(f"[Trigger] Baglanti tamamlandi.")

if __name__ == "__main__":
    # Hepsini sirayla cagiriyoruz
    create_dynamodb_table()
    role_arn = create_iam_role()
    create_s3_bucket()
    lambda_arn = deploy_lambda(role_arn)
    add_s3_trigger(lambda_arn)
    print("\n--- DEPLOYMENT TAMAMLANDI ---")