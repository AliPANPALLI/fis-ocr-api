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

## Gereksinimler

- Python 3.11 onerilir
- Windows, Linux veya Docker

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

Linux / macOS:

```bash
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
