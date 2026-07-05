# Fis OCR API EXE Kullanimi

Bu dosya, kodlari paylasmadan karsi tarafa Windows uygulamasi vermek icindir.

## Karsi Tarafa Ne Verilecek?

Build alindiktan sonra olusan dosya:

```text
dist\fis-ocr-api.exe
```

Karsi tarafa normalde sadece bu `.exe` dosyasi verilir.

## Karsi Taraf Python veya OCR Kuracak mi?

Hayir.

Dogru paketlenmis `.exe` icinde sunlar bulunur:

- Python calisma ortami
- FastAPI / Uvicorn
- RapidOCR
- ONNX Runtime
- OpenCV
- OCR icin gereken model/paket dosyalari

Bu yuzden karsi tarafin bilgisayarina Python, Tesseract, Windows OCR veya ekstra Python paketi kurmasi gerekmez.

## Karsi Taraf Nasil Calistiracak?

1. `fis-ocr-api.exe` dosyasina cift tiklar.
2. Siyah bir konsol penceresi acilir.
3. API su adreste calisir:

```text
http://127.0.0.1:8000
```

4. Tarayicidan bu adrese girip gorsel yukleyebilir.
5. Baska programdan istek atacaksa:

```powershell
curl.exe -X POST http://127.0.0.1:8000/extract `
  -F "file=@C:\path\to\fis.jpeg"
```

## Exe Nasil Uretilir?

Gelistirici bilgisayarinda:

```bat
build_exe.bat
```

Islem bitince exe burada olusur:

```text
dist\fis-ocr-api.exe
```

## Kodlar Gorunur mu?

Normal kullanici `.exe` icinde kodlari gormez.

Ama bu yontem yuzde yuz kaynak kod korumasi degildir. Python ile uretilen `.exe` dosyalari ileri seviye kisiler tarafindan incelenebilir. Kodun hic kimse tarafindan gorulmemesi gerekiyorsa en saglam cozum API'yi senin kendi sunucunda calistirip karsi tarafa sadece API adresi vermektir.

## GitHub Notu

Repo public ise GitHub'a yuklenen `.py` dosyalari herkes tarafindan gorulebilir.

Kod gizli kalacaksa:

- Repo private yapilmali, veya
- GitHub'a kaynak kod degil sadece Release altina `.exe` yuklenmeli, veya
- Ayrica kod icermeyen yeni bir public repo acilip sadece exe ve kullanim dokumani paylasilmalidir.
