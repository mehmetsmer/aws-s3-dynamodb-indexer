import json
import urllib.parse
import boto3
import os
from datetime import datetime

# DynamoDB servisine baglanti (Bunu fonksiyon disinda yapiyoruz, performans icin!)
dynamodb = boto3.resource('dynamodb')

# Tablo ismini Kodun icine gommek yerine Environment Variable'dan aliyoruz.
# Boylece tablo adi degisse bile kodu degistirmemize gerek kalmaz.
TABLE_NAME = os.environ.get('TABLE_NAME')
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    """
    S3 Put eventinden tetiklenen ana fonksiyon.
    Dosya metadata bilgilerini DynamoDB'ye yazar.
    """
    try:
        # S3 Event yapisindan bucket ve dosya ismini (key) cekme
        # Event yapisi bir liste oldugu icin ilk kaydi aliyoruz
        for record in event['Records']:
            s3_bucket = record['s3']['bucket']['name']
            
            # Dosya ismindeki ozel karakterleri (bosluk vb) cozme
            s3_key = urllib.parse.unquote_plus(record['s3']['object']['key'], encoding='utf-8')
            
            # Dosya boyutu (byte cinsinden)
            s3_size = record['s3']['object']['size']
            
            # Event zamani
            event_time = record['eventTime']

            print(f"Islem yapiliyor: {s3_bucket} -> {s3_key}")

            # DynamoDB'ye yazilacak item
            item = {
                'file_name': s3_key,       # Partition Key (Anahtar)
                'bucket_name': s3_bucket,
                'file_size_bytes': s3_size,
                'upload_timestamp': event_time,
                'processed_at': str(datetime.now())
            }

            # Veritabanina kayit
            table.put_item(Item=item)
            print(f"Metadata basariyla kaydedildi: {s3_key}")

        return {
            'statusCode': 200,
            'body': json.dumps('Metadata Indexing Successful')
        }

    except Exception as e:
        print(f"Hata olustu: {str(e)}")
        raise e