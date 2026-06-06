# Kişiye Özel Boyama Kitabı Anketi

Streamlit ile hazırlanmış Türkçe/Arapça ürün talep anketi.

## Local Çalıştırma

```bash
pip install -r requirements.txt
streamlit run app.py
```

Turso bilgileri yoksa uygulama local SQLite kullanır:

```text
data/survey.db
```

Bu dosya `.gitignore` içindedir, public GitHub reposuna eklenmemelidir.

## Admin

Dashboard herkese açık menüde görünmez. Admin giriş sayfası:

```text
http://localhost:8501/admin
```

Yedek adres:

```text
http://localhost:8501/?admin=1
```

Turso secrets yokken local geliştirme için varsayılan admin şifresi:

```text
admin123
```

Canlı yayında mutlaka `ADMIN_PASSWORD` secret değeri tanımlayın. Turso aktifken `ADMIN_PASSWORD` yoksa admin paneli açılmaz.

## Turso Ayarları

Uygulama şu iki değer varsa otomatik Turso veritabanına bağlanır:

```text
TURSO_DATABASE_URL
TURSO_AUTH_TOKEN
```

Turso CLI ile örnek:

```bash
turso db create boyama-anket
turso db show --url boyama-anket
turso db tokens create boyama-anket
```

Turso paneli SQLite dosyası isterse şu temiz seed dosyasını yükleyin:

```text
data/turso_seed.db
```

Bu dosyada sadece `responses` tablosu vardır, cevap kaydı yoktur.

Bu değerleri public repoya koymayın.

## Local Secrets

Local test için örnek dosyayı kopyalayabilirsiniz:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Sonra gerçek değerleri `.streamlit/secrets.toml` içine yazın.

Önemli: `.streamlit/secrets.toml` `.gitignore` içindedir ve GitHub'a gönderilmemelidir.

## Streamlit Community Cloud Deploy

1. Bu klasörü GitHub’da public repo olarak yayınlayın.
2. Streamlit Community Cloud’da yeni app oluşturun.
3. Repo olarak bu projeyi seçin.
4. Main file path olarak şunu girin:

```text
app.py
```

5. App secrets bölümüne şunları ekleyin:

```toml
ADMIN_PASSWORD = "guclu-bir-admin-sifresi"
TURSO_DATABASE_URL = "libsql://your-database-your-org.turso.io"
TURSO_AUTH_TOKEN = "your-turso-token"
```

## Public Repo Güvenlik Notları

Commit etmemen gerekenler:

```text
.streamlit/secrets.toml
.env
data/survey.db
Turso tokenları
Admin şifresi
```

Repoda kalması güvenli olanlar:

```text
.streamlit/secrets.toml.example
requirements.txt
app.py
config/questions.json
images/
```

## Dosya Yapısı

```text
app.py
config/questions.json
images/
requirements.txt
.streamlit/secrets.toml.example
```

Soruları ve çevirileri değiştirmek için `config/questions.json` dosyasını düzenlemek yeterlidir.
