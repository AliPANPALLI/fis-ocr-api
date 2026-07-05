import webbrowser

import uvicorn

from receipt_api import app


def main() -> None:
    host = "127.0.0.1"
    port = 8000
    url = f"http://{host}:{port}"
    print("Fis OCR API baslatiliyor...")
    print(f"Adres: {url}")
    print("Kapatmak icin bu pencereyi kapatabilir veya Ctrl+C yapabilirsin.")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
