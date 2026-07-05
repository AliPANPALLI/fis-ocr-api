# Fis OCR REST API

Fis / Z raporu gorselinden OCR ile alan cikaran FastAPI servisidir.

API'ye gorsel gonderirsin, servis su alanlari JSON olarak dondurur:

- `tarih`
- `saat`
- `fis_no`
- `z_no`
- `kategori`
- `kdv_orani`
- `adet`
- `toplam`
- `kdv`
- `banka_kredi_karti`
- `kum_top`
- `kum_kdv`
- `kum_knv`

OCR motoru olarak `rapidocr-onnxruntime` kullanilir. Windows OCR'a bagli degildir.

## Neden `receipt_api.py` GitHub'a Yuklendi?

`receipt_api.py` bu projenin ana uygulama dosyasidir.

Bu dosyanin icinde sunlar bulunur:

- FastAPI endpointleri: `/`, `/health`, `/extract`, `/extract-sample/{dosya_adi}`
- Gorseli alma ve OCR'a hazirlama islemleri
- Fis alanlarini cikaran parser
- Tarih, Z No, toplam, KDV, banka/kredi karti gibi alanlari duzeltme kurallari

Yani `receipt_api.py` GitHub'a yuklenmezse proje calismaz. `requirements.txt` sadece hangi kutuphanelerin kurulacagini soyler; uygulamanin kendisi `receipt_api.py` dosyasidir.

Kodun herkese acik gorunmesini istemiyorsan repo'yu GitHub'da private yapman gerekir. Alternatif olarak Docker image hazirlanip sadece image dagitilabilir, ama normal GitHub repo ile calistirmak icin Python kod dosyasi gerekir.

## Gereksinimler

- Python 3.11 onerilir
- Windows, Linux veya Docker

## OCR Ayrica Kurulacak mi?

Hayir, kullanicinin bilgisayarina ayrica Tesseract, Windows OCR veya baska bir OCR programi kurmasi gerekmez.

OCR icin gereken Python paketi `requirements.txt` icindedir:

```text
rapidocr-onnxruntime
```

Kullanici su komutu calistirdiginda OCR kutuphanesi de otomatik kurulur:

```bash
pip install -r requirements.txt
```

Ilk calismada OCR modeli ve bagimli paketler yuklenebilir. Bu yuzden ilk kurulum internet ister. Kurulum bittikten sonra API lokal makinede calisir.

## Lokal Calistirma

Projeyi indirdikten sonra:

```bash
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
pip install -r requirements.txt
run_receipt_api.bat
```

Windows'ta adim adim:

1. Python 3.11 kur.
2. GitHub reposunu indir veya clone et.
3. Proje klasorunde terminal ac.
4. `python -m venv .venv` komutunu calistir.
5. `.venv\Scripts\activate` komutunu calistir.
6. `pip install -r requirements.txt` komutunu calistir.
7. `run_receipt_api.bat` dosyasini calistir.
8. Tarayicidan `http://127.0.0.1:8000` adresine gir.

Linux / macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn receipt_api:app --host 0.0.0.0 --port 8000
```

Linux sunucuda calistirirken:

```bash
git clone https://github.com/AliPANPALLI/fis-ocr-api.git
cd fis-ocr-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn receipt_api:app --host 0.0.0.0 --port 8000
```

API acildiktan sonra:

```text
http://127.0.0.1:8000
```

Bu adreste basit bir resim yukleme ekrani da vardir.

## Docker ile Calistirma

Docker kullanirsan kullanicinin Python paketleriyle tek tek ugrasmamasi daha kolay olur. Docker image icinde Python, API ve OCR kutuphaneleri kurulur.

```bash
docker build -t fis-ocr-api .
docker run --rm -p 8000:8000 fis-ocr-api
```

Sonra:

```text
http://127.0.0.1:8000
```

## API Kullanimi

### Saglik kontrolu

```bash
curl http://127.0.0.1:8000/health
```

Beklenen cevap:

```json
{"status":"ok"}
```

### Gorsel gonderme

Windows PowerShell:

```powershell
curl.exe -X POST http://127.0.0.1:8000/extract `
  -F "file=@C:\path\to\fis.jpeg"
```

Linux / macOS:

```bash
curl -X POST http://127.0.0.1:8000/extract \
  -F "file=@/path/to/fis.jpeg"
```

Ornek cevap:

```json
{
  "filename": "fis.jpeg",
  "fields": {
    "tarih": "15-04-2026",
    "saat": null,
    "fis_no": "000",
    "z_no": "0618",
    "kategori": null,
    "kdv_orani": null,
    "adet": "12,020",
    "toplam": "2.020,00",
    "kdv": "183,64",
    "banka_kredi_karti": "1.820,00",
    "kum_top": null,
    "kum_kdv": "628,30",
    "kum_knv": null,
    "ocr_confidence": 0.9222
  },
  "raw_text": "...",
  "engine": "rapidocr-onnxruntime"
}
```

## Test Gorselleri

`GET /extract-sample/{dosya_adi}` endpointi sadece lokal test icindir.

Ornek:

```text
http://127.0.0.1:8000/extract-sample/30.jpeg
```

Bu endpointin calismasi icin proje klasorunde `FIS_ORNEKLERI` klasoru ve icinde ilgili gorsel olmalidir.

Gercek fis fotograflarini GitHub'a yukleme. `.gitignore` bu klasoru ve gorsel dosyalarini disarida birakir.

## GitHub'a Yuklenecek Dosyalar

Bu repo kod ve calisma dosyalarini icermelidir:

- `receipt_api.py`
- `requirements.txt`
- `Dockerfile`
- `run_receipt_api.bat`
- `README.md`
- `.gitignore`

Bu dosyalar olmadan proje baska bilgisayarda kurulamaz. Ozellikle `receipt_api.py` zorunludur; API'nin kendisi odur.

Su dosyalari GitHub'a koyma:

- Gercek fis fotograflari
- `FIS_ORNEKLERI/`
- `ocr_temp/`
- `okunan_fisler.txt`
- `__pycache__/`
- `.env`

## GitHub'da Direkt Calisir mi?

Hayir. GitHub sadece kodu saklar. API'nin calismasi icin bu kodun bir bilgisayarda, VPS'te, Docker sunucusunda, Render/Railway gibi bir platformda veya kendi makinenizde calistirilmasi gerekir.

## Deploy Notu

Sunucuya kurarken temel komut:

```bash
pip install -r requirements.txt
uvicorn receipt_api:app --host 0.0.0.0 --port 8000
```

Docker destekleyen bir platformda ise:

```bash
docker build -t fis-ocr-api .
docker run -p 8000:8000 fis-ocr-api
```
