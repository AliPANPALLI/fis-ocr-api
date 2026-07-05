# Fis OCR API - Windows EXE

Bu repo kaynak kod paylasmak icin degil, hazir Windows `.exe` dosyasini kullanmak icin tutulur.

Kaynak kod dosyalari public repoda bulunmaz.

## Indirme

Hazir exe dosyasi GitHub Release icindedir:

[fis-ocr-api.exe indir](https://github.com/AliPANPALLI/fis-ocr-api/releases/tag/v1.0.0)

Release sayfasindan `fis-ocr-api.exe` dosyasini indir.

## Baska Bir Sey Kurmak Gerekir mi?

Hayir.

Karsi tarafin bilgisayarina sunlari kurmasi gerekmez:

- Python
- Tesseract
- Windows OCR
- pip paketleri
- `requirements.txt`

Exe icinde API, OCR kutuphanesi ve gerekli calisma paketleri bulunur.

## Nasil Calistirilir?

1. `fis-ocr-api.exe` dosyasini indir.
2. Exe dosyasina cift tikla.
3. Siyah konsol penceresi acik kalsin.
4. Tarayicidan su adrese gir:

```text
http://127.0.0.1:8000
```

5. Fis gorselini yukle.
6. Sonucu JSON olarak al.

## API'ye Programdan Istek Atma

Windows PowerShell ornegi:

```powershell
curl.exe -X POST http://127.0.0.1:8000/extract `
  -F "file=@C:\path\to\fis.jpeg"
```

## Donen Alanlar

API su alanlari dondurur:

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
- `ocr_confidence`

## Windows Uyarisi

Exe imzali olmadigi icin Windows ilk acilista "bilinmeyen yayinci" uyarisi verebilir.

Bu normaldir. Devam etmek icin:

```text
Ek bilgi > Yine de calistir
```

## Kod Gizliligi

Normal kullanici exe icindeki kodlari gormez.

Ama Python ile uretilen exe dosyalari yuzde yuz tersine muhendislik korumasi saglamaz. Ileri seviye biri exe uzerinde analiz yapabilir. En guvenli yontem API'yi kendi sunucunda calistirip karsi tarafa sadece API adresi vermektir.

Bu repo public oldugu icin kaynak kod dosyalari buraya yuklenmez.
