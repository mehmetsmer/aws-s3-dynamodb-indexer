import boto3

# --- AYARLAR (Deploy dosyasi ile AYNI olmali) ---
PROJECT_NAME = "s3-metadata-indexer"
BUCKET_NAME = f"{PROJECT_NAME}-bucket-v2"  
TABLE_NAME = f"{PROJECT_NAME}-table"
LAMBDA_FUNC_NAME = f"{PROJECT_NAME}-func"
ROLE_NAME = f"{PROJECT_NAME}-role"
REGION = "eu-central-1" 

# Clientlar
s3 = boto3.resource('s3', region_name=REGION)
lambda_client = boto3.client('lambda', region_name=REGION)
dynamodb_client = boto3.client('dynamodb', region_name=REGION)
iam_client = boto3.client('iam', region_name=REGION)

def cleanup():
    print("--- TEMIZLIK BASLIYOR ---")
    
    # 1. S3 Bucket Temizligi
    print(f"Bucket siliniyor: {BUCKET_NAME}")
    try:
        bucket = s3.Bucket(BUCKET_NAME)
        # Bucket doluysa once icindekileri silmek gerekir, yoksa hata verir
        bucket.objects.all().delete() 
        bucket.delete() 
        print("-> Bucket silindi.")
    except Exception as e:
        print(f"S3 Hatasi (Belki zaten silinmistir): {e}")

    # 2. DynamoDB Tablosu Silme
    print(f"Tablo siliniyor: {TABLE_NAME}")
    try:
        dynamodb_client.delete_table(TableName=TABLE_NAME)
        print("-> Tablo silindi.")
    except Exception as e:
        print(f"DynamoDB Hatasi: {e}")

    # 3. Lambda Fonksiyonu Silme
    print(f"Lambda siliniyor: {LAMBDA_FUNC_NAME}")
    try:
        lambda_client.delete_function(FunctionName=LAMBDA_FUNC_NAME)
        print("-> Lambda silindi.")
    except Exception as e:
        print(f"Lambda Hatasi: {e}")

    # 4. IAM Rolu Silme
    print(f"Rol siliniyor: {ROLE_NAME}")
    try:
        # Once policy detach edilmeli
        iam_client.detach_role_policy(RoleName=ROLE_NAME, PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")
        iam_client.detach_role_policy(RoleName=ROLE_NAME, PolicyArn="arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess")
        iam_client.delete_role(RoleName=ROLE_NAME)
        print("-> Rol silindi.")
    except Exception as e:
        print(f"IAM Hatasi: {e}")

    print("\n--- TEMIZLIK TAMAMLANDI ---")

if __name__ == "__main__":
    cleanup()