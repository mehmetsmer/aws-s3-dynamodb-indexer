# AWS S3-to-DynamoDB Metadata Indexer 

Bu proje, AWS S3 bucket'ına yüklenen herhangi bir dosyanın metadata bilgilerini (isim, boyut, tarih) yakalayıp DynamoDB tablosuna kaydeden **Serverless** ve **Event-Driven** bir otomasyon çözümüdür.

Tüm altyapı AWS Console kullanılmadan, **Python (Boto3)** ile **Infrastructure as Code (IaC)** prensibine uygun olarak kodlanmıştır.

## Mimari (Architecture)

* **S3 Bucket:** Dosya yükleme alanı (Trigger source).
* **AWS Lambda:** Business logic'i çalıştıran fonksiyon (Python 3.9).
* **DynamoDB:** Metadata verilerinin tutulduğu NoSQL veritabanı.
* **IAM:** Least Privilege prensibine uygun yetkilendirme.

## Karşılaşılan Zorluklar ve Çözümler (Key Learnings)

Bu proje geliştirilirken karşılaşılan gerçek hayat senaryoları ve uygulanan çözümler:

### 1. Region Management & LocationConstraint
**Sorun:** `us-east-1` dışındaki bölgelerde (örn: `eu-central-1`) S3 bucket oluştururken `LocationConstraint` belirtilmediğinde "IllegalLocationConstraintException" hatası alınıyordu.
**Çözüm:** Deployment scripti, çalıştırılan Region'ı dinamik olarak algılayıp, eğer `us-east-1` değilse gerekli `LocationConstraint` parametresini otomatik ekleyecek şekilde optimize edildi.

### 2. IAM Role Propagation & Race Conditions
**Sorun:** IAM rolü oluşturulduktan hemen sonra Lambda fonksiyonu oluşturulmaya çalışıldığında, AWS'in distributed yapısından dolayı rol henüz tüm region'a yayılmadığı için yetki hatası alınıyordu.
**Çözüm:** Script içerisine `Waiters` ve `time.sleep` mekanizmaları eklenerek, IAM rolünün "active" duruma gelmesi beklendi ve Race Condition önlendi.

### 3. S3 Event Trigger Conflict
**Sorun:** Bucket silinip yeniden oluşturulduğunda, Lambda üzerindeki eski izinler (Resource Policy) çakışma yaratıyordu (`Statement ID conflict`).
**Çözüm:** Lambda'ya eklenen izinlerin `StatementId` parametresi dinamik hale getirildi (`f"s3-trigger-{bucket_name}"`). Böylece her bucket-lambda ilişkisi benzersiz bir kimliğe sahip oldu.

## Kurulum ve Çalıştırma

Bu projeyi kendi AWS hesabınızda (Free Tier uyumlu) ayağa kaldırmak için:

1.  **Repoyu Klonlayın:**
    ```bash
    git clone [https://github.com/mehmetsmer/aws-s3-dynamodb-indexer.git](https://github.com/mehmetsmer/aws-s3-dynamodb-indexer.git)
    cd aws-s3-dynamodb-indexer
    ```

2.  **Sanal Ortamı Kurun:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Deploy Edin (Tek Komut):**
    ```bash
    python scripts/deploy.py
    ```
    *Bu script IAM Rolü, DynamoDB Tablosu, S3 Bucket ve Lambda fonksiyonunu otomatik kurar.*

4.  **Temizlik (Kaynakları Silme):**
    ```bash
    python scripts/cleanup.py
    ```

## 📂 Proje Yapısı

```text
├── src/
│   └── lambda_function.py  # AWS Lambda üzerinde çalışan backend kodu
├── scripts/
│   ├── deploy.py           # Altyapıyı kuran otomasyon scripti (IaC)
│   └── cleanup.py          # Kaynakları silen script
├── requirements.txt        # Gerekli kütüphaneler (boto3)
└── README.md