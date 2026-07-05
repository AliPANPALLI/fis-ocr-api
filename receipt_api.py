import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image, ImageEnhance, ImageOps
from pydantic import BaseModel
from rapidocr_onnxruntime import RapidOCR


APP_DIR = Path(__file__).resolve().parent
SAMPLE_DIR = APP_DIR / "FIS_ORNEKLERI"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

app = FastAPI(title="Fis OCR API", version="1.0.0")
ocr_engine = RapidOCR()


class ReceiptResponse(BaseModel):
    filename: str
    fields: dict[str, Any]
    raw_text: str
    engine: str = "rapidocr-onnxruntime"


def normalize_text(value: str) -> str:
    replacements = {
        "：": ":",
        "；": ":",
        "，": ",",
        "İ": "I",
        "Ş": "S",
        "Ğ": "G",
        "Ü": "U",
        "Ö": "O",
        "Ç": "C",
        "ı": "i",
        "ş": "s",
        "ğ": "g",
        "ü": "u",
        "ö": "o",
        "ç": "c",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def crop_receipt_area(image: Image.Image) -> Image.Image:
    rgb = ImageOps.exif_transpose(image).convert("RGB")
    gray = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2GRAY)
    _, mask = cv2.threshold(gray, 165, 255, cv2.THRESH_BINARY)
    kernel = np.ones((19, 19), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count <= 1:
        return rgb

    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x = stats[largest, cv2.CC_STAT_LEFT]
    y = stats[largest, cv2.CC_STAT_TOP]
    w = stats[largest, cv2.CC_STAT_WIDTH]
    h = stats[largest, cv2.CC_STAT_HEIGHT]
    if w < rgb.width * 0.2 or h < rgb.height * 0.2:
        return rgb

    margin_x = max(10, int(rgb.width * 0.015))
    margin_y = max(10, int(rgb.height * 0.015))
    left = max(0, x - margin_x)
    top = max(0, y - margin_y)
    right = min(rgb.width, x + w + margin_x)
    bottom = min(rgb.height, y + h + margin_y)
    return rgb.crop((left, top, right, bottom))


def scale_for_ocr(image: Image.Image, target_width: int = 1800) -> Image.Image:
    if image.width >= target_width:
        return image
    scale = target_width / image.width
    return image.resize((target_width, int(image.height * scale)), Image.Resampling.LANCZOS)


def make_ocr_variants(image_path: Path) -> list[Image.Image]:
    with Image.open(image_path) as image:
        original = scale_for_ocr(ImageOps.exif_transpose(image).convert("RGB"))
        cropped = crop_receipt_area(image)
        color = scale_for_ocr(ImageOps.autocontrast(cropped.convert("RGB"), cutoff=1))

        gray = scale_for_ocr(cropped.convert("L"))
        gray = ImageOps.autocontrast(gray, cutoff=1)
        gray = ImageEnhance.Contrast(gray).enhance(1.25)
        gray = ImageEnhance.Sharpness(gray).enhance(1.2)

        strong = np.array(gray)
        strong = np.where(strong < 205, 0, 255).astype(np.uint8)
        binary = Image.fromarray(strong, mode="L")

        return [color, gray.convert("RGB"), binary.convert("RGB"), original]


def rapid_result_to_lines(result: list[Any]) -> tuple[list[str], float]:
    boxes = []
    scores = []
    for item in result or []:
        if len(item) < 2 or not item[1]:
            continue
        score = float(item[2]) if len(item) > 2 and item[2] is not None else 1.0
        if score < 0.35:
            continue
        points = item[0]
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        boxes.append({
            "text": normalize_text(str(item[1])),
            "x": sum(xs) / len(xs),
            "y": sum(ys) / len(ys),
            "h": max(ys) - min(ys),
        })
        scores.append(score)

    if not boxes:
        return [], 0.0

    median_height = float(np.median([box["h"] for box in boxes if box["h"] > 0])) or 18.0
    row_gap = max(10.0, median_height * 0.72)
    rows: list[list[dict[str, Any]]] = []
    for box in sorted(boxes, key=lambda value: value["y"]):
        if rows:
            row_y = sum(item["y"] for item in rows[-1]) / len(rows[-1])
            if abs(box["y"] - row_y) <= row_gap:
                rows[-1].append(box)
                continue
        rows.append([box])

    lines = []
    for row in rows:
        line = " ".join(item["text"] for item in sorted(row, key=lambda value: value["x"]))
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    avg_score = sum(scores) / len(scores) if scores else 0.0
    return lines, round(avg_score, 4)


def ocr_image(image_path: Path) -> tuple[str, float]:
    best_lines: list[str] = []
    best_score = -1.0
    best_confidence = 0.0

    for index, image in enumerate(make_ocr_variants(image_path)):
        with tempfile.NamedTemporaryFile(suffix=f"_{index}.png", delete=False) as temp:
            temp_path = Path(temp.name)
        image.save(temp_path)
        try:
            result, _ = ocr_engine(str(temp_path))
        finally:
            temp_path.unlink(missing_ok=True)

        lines, confidence = rapid_result_to_lines(result or [])
        text = "\n".join(lines)
        quality = score_text(text) + confidence * 100
        if quality > best_score:
            best_lines = lines
            best_score = quality
            best_confidence = confidence

    return "\n".join(best_lines), best_confidence


def score_text(text: str) -> float:
    upper = normalize_text(text).upper()
    keywords = ["TARIH", "SAAT", "FIS", "Z", "RAPORU", "TOPLAM", "KDV", "BANKA", "KREDI", "KUM.TOP"]
    return sum(upper.count(keyword) * 15 for keyword in keywords) + min(len(upper), 2000) / 10


def parse_amount(value: str) -> float | None:
    normalized = normalize_amount(value)
    if not normalized:
        return None
    cleaned = normalized.replace(".", "").replace(",", ".")
    cleaned = re.sub(r"[^0-9.]", "", cleaned)
    try:
        return float(cleaned)
    except ValueError:
        return None


def find_first(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.upper()
    value = value.replace("O", "0").replace("D", "0")
    value = value.replace("I", "1").replace("L", "1")
    value = value.replace("B", "8").replace("S", "5")
    value = re.sub(r"[^0-9./-]", "", value)
    match = re.search(r"(\d{2})([./-])(\d{2})([./-])(\d{4})", value)
    if not match:
        return None
    year = int(match.group(5))
    if not 2000 <= year <= 2099:
        year = 2000 + int(match.group(5)[-2:])
    return f"{match.group(1)}{match.group(2)}{match.group(3)}{match.group(4)}{year:04d}"


def find_date(text: str) -> str | None:
    exact = find_first([r"\b(\d{2}[./-]\d{2}[./-]\d{4})\b"], text)
    if exact:
        return exact
    tolerant = find_first([r"\b([0-9ODILBS]{2}[./-][0-9ODILBS]{2}[./-][0-9ODILBS]{4})\b"], text)
    return normalize_date(tolerant)


def find_receipt_date(lines: list[str]) -> str | None:
    date_pattern = re.compile(r"\b([0-9ODILBS]{2}[./-][0-9ODILBS]{2}[./-][0-9ODILBS]{4})\b", re.IGNORECASE)
    priority_patterns = [
        r"TARIH",
        r"SAAT",
        r"SAA[TI]",
        r"FI[SŞ]\s*NO",
        r"FIS\s*NO",
        r"Z\s*RAPOR",
        r"TOPLU\s+Z\s+RAPOR",
    ]

    for line in lines:
        upper = normalize_text(line).upper()
        if not any(re.search(pattern, upper) for pattern in priority_patterns):
            continue
        matches = list(date_pattern.finditer(line))
        if not matches:
            continue
        fis_match = re.search(r"FI[SŞ]\s*NO|FIS\s*NO|FISNO", upper)
        if fis_match:
            selected = min(matches, key=lambda item: abs(item.start() - fis_match.start()))
            return normalize_date(selected.group(1))
        return normalize_date(matches[-1].group(1))

    for index, line in enumerate(lines):
        upper = normalize_text(line).upper()
        if len(upper) > 90:
            continue
        window = " ".join(lines[max(0, index - 1):min(len(lines), index + 2)])
        window_upper = normalize_text(window).upper()
        match = date_pattern.search(line)
        if not match:
            continue
        if any(re.search(pattern, upper) for pattern in priority_patterns):
            return normalize_date(match.group(1))
        if any(re.search(pattern, window_upper) for pattern in priority_patterns):
            return normalize_date(match.group(1))

    compact_text = " ".join(line for line in lines if len(normalize_text(line)) <= 90)
    return find_date(compact_text)


def normalize_z_no(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits or None


def find_z_no(lines: list[str], flat: str) -> str | None:
    z_patterns = [
        r"\bZ\s*NO\s*:?\s*([0-9]+(?:\.[0-9]+)*)",
        r"\bZNO\s*:?\s*([0-9]+(?:\.[0-9]+)*)",
        r"\bZ\s*[-:]\s*([0-9]+(?:\.[0-9]+)*)",
    ]
    for line in lines:
        upper = normalize_text(line).upper()
        if "Z" not in upper:
            continue
        for pattern in z_patterns:
            match = re.search(pattern, upper)
            if match:
                return normalize_z_no(match.group(1))
    for index, line in enumerate(lines):
        upper = normalize_text(line).upper()
        if not re.search(r"Z\s*RAPOR", upper):
            continue
        nearby = " ".join(lines[index:min(len(lines), index + 3)])
        candidates = re.findall(r"\b\d{4,6}\b", nearby)
        if candidates:
            return normalize_z_no(candidates[-1])
    return normalize_z_no(find_first(z_patterns, flat))


def find_amount_after(label_patterns: list[str], lines: list[str]) -> str | None:
    amount_pattern = re.compile(r"[*#¥+·]?\d+(?:[.\s]\d{3})*[,.]\d{2}")
    for index, line in enumerate(lines):
        upper = normalize_text(line).upper()
        if any(re.search(pattern, upper) for pattern in label_patterns):
            amounts = amount_pattern.findall(line)
            if amounts:
                return normalize_amount(amounts[0])
            search_lines = []
            if index + 1 < len(lines):
                search_lines.append(lines[index + 1])
            joined = " ".join(search_lines)
            amounts = amount_pattern.findall(joined)
            if amounts:
                return normalize_amount(amounts[-1])
    return None


def normalize_amount(value: str | None) -> str | None:
    if not value:
        return None
    value = value.replace(" ", "").replace("*", "")
    value = value.replace("，", ",")
    value = re.sub(r"^[^0-9]+", "", value)
    if "," not in value and "." in value:
        head, tail = value.rsplit(".", 1)
        if len(tail) == 2:
            value = f"{head},{tail}"
    if "," in value:
        whole, decimal = value.split(",", 1)
        digits = re.sub(r"\D", "", whole)
        if digits:
            whole = f"{int(digits):,}".replace(",", ".")
            value = f"{whole},{decimal[:2]}"
    return value


def format_amount(number: float) -> str:
    whole = int(number)
    decimal = int(round((number - whole) * 100))
    if decimal == 100:
        whole += 1
        decimal = 0
    return f"{whole:,}".replace(",", ".") + f",{decimal:02d}"


def normalize_kdv_rate(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    return f"%{int(digits)}"


def reconcile_kdv_with_rate(toplam: str | None, kdv: str | None, kdv_orani: str | None) -> str | None:
    total_number = parse_amount(toplam or "")
    kdv_number = parse_amount(kdv or "")
    if total_number is None or total_number < 0:
        return kdv
    rate_text = normalize_kdv_rate(kdv_orani)
    if not rate_text:
        return kdv
    rate = int(re.sub(r"\D", "", rate_text))
    if rate <= 0:
        return kdv
    expected = total_number * rate / (100 + rate)
    if kdv_number is None:
        return format_amount(expected)
    tolerance = max(0.75, expected * 0.12)
    if abs(kdv_number - expected) > tolerance:
        return format_amount(expected)
    return kdv


def repair_small_total(lines: list[str], toplam: str | None, kdv: str | None, kdv_orani: str | None) -> tuple[str | None, str | None]:
    total_number = parse_amount(toplam or "")
    if total_number is None or total_number >= 1000:
        return toplam, kdv

    amount_candidates: list[tuple[str, float]] = []
    for line in lines:
        upper = normalize_text(line).upper()
        if re.search(r"K[UO]M", upper):
            continue
        if not re.search(r"NET|BRUT|SATIS|TOPLAM|TOPSAT|SARKUTERI|GIDA|GIYIM|YIYECEK|PAKET", upper):
            continue
        for amount in extract_amounts(line) + extract_tax_amounts(line):
            number = parse_amount(amount)
            if number is not None and 1000 <= number <= 100_000:
                amount_candidates.append((amount, number))

    if not amount_candidates:
        return toplam, kdv

    repaired_total, repaired_number = max(amount_candidates, key=lambda item: item[1])
    rate_text = normalize_kdv_rate(kdv_orani)
    expected_kdv = None
    if rate_text:
        rate = int(re.sub(r"\D", "", rate_text))
        if rate > 0:
            expected_kdv = repaired_number * rate / (100 + rate)

    kdv_candidates: list[tuple[str, float]] = []
    for line in lines:
        upper = normalize_text(line).upper()
        if re.search(r"K[UO]M", upper):
            continue
        if not re.search(r"KDV|TOPKDV|IUV|KOV", upper):
            continue
        for amount in extract_amounts(line) + extract_tax_amounts(line):
            number = parse_amount(amount)
            if number is not None and 0 < number < repaired_number * 0.25:
                kdv_candidates.append((amount, number))

    repaired_kdv = kdv
    if kdv_candidates:
        if expected_kdv is not None:
            closest_amount, closest_number = min(kdv_candidates, key=lambda item: abs(item[1] - expected_kdv))
            tolerance = max(0.75, expected_kdv * 0.12)
            repaired_kdv = closest_amount if abs(closest_number - expected_kdv) <= tolerance else format_amount(expected_kdv)
        else:
            repaired_kdv = max(kdv_candidates, key=lambda item: item[1])[0]
    elif expected_kdv is not None:
        repaired_kdv = format_amount(expected_kdv)

    return repaired_total, repaired_kdv


def extract_amounts(text: str) -> list[str]:
    text = normalize_text(text)
    values = re.findall(r"[*#¥+·]?\d+(?:[.\s]\d{3})*[,.]\d{2}", text)
    return [normalize_amount(value) for value in values if normalize_amount(value)]


def amount_from_compact_digits(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 3:
        return None
    whole = digits[:-2] or "0"
    decimal = digits[-2:]
    return normalize_amount(f"{whole},{decimal}")


def extract_tax_amounts(line: str) -> list[str]:
    text = normalize_text(line).upper()
    text = re.sub(r"%\s*\d{1,2}\s*TOPLAM", " ", text)
    text = re.sub(r"(TOPKDV|KDV|TOPLAM|TOPIAM|TOPL/)\s*(?:[Z/%]\s*)?\d{1,3}(?=\s+\d{1,3}[,.]\d{2}|\s+\d{4,8}\b)", " ", text)
    text = re.sub(r"TOPLAMZ\d{1,2}(?=\s+\d{4,8}\b)", " ", text)
    text = re.sub(r"TOPKDV\s*[Z/%]?", " ", text)
    text = re.sub(r"TOPLAM\s*[Z/%]?|TOPIAM|TOPL/", " ", text)
    text = re.sub(r"TOPSAT|TOP\s+SAT|TOP\s*KASA", " ", text)
    text = re.sub(r"\bKDV\s*[Z/%]?", " ", text)

    amounts = extract_amounts(text)
    for token in re.findall(r"\b\d{4,8}\b", text):
        compact = amount_from_compact_digits(token)
        if compact:
            amounts.append(compact)

    deduped = []
    for amount in amounts:
        if amount and amount not in deduped:
            deduped.append(amount)
    return deduped


def line_amount_candidates(line: str) -> list[tuple[str, float]]:
    candidates = []
    for amount in extract_amounts(line):
        number = parse_amount(amount)
        if number is not None:
            candidates.append((amount, number))
    return candidates


def extract_card_amount(lines: list[str], toplam: str | None) -> str | None:
    total_number = parse_amount(toplam or "")
    label_pattern = re.compile(
        r"BANKA|KREDI|KREDİ|K\.?\s*KARTI|KARTI|VAKIFLAR|GARANTI|YAPI\s*KREDI|KASA\s*KREDI",
        re.IGNORECASE,
    )
    ignore_pattern = re.compile(r"K[UO]M|TOPKDV|KDV|TOPLAM\s+FI[SŞ]|TOP\s*KASA|NAKIT\+CEK\+KREDI|FATURA|TARIH", re.IGNORECASE)

    best: tuple[str, float] | None = None
    for index, line in enumerate(lines):
        upper = normalize_text(line).upper()
        if not label_pattern.search(upper) or ignore_pattern.search(upper):
            continue

        nearby = [line]
        for look_ahead in range(index + 1, min(index + 3, len(lines))):
            next_upper = normalize_text(lines[look_ahead]).upper()
            if re.search(r"K[UO]M|TOPLAM|TOPKDV|KDV|NAKIT|FIS\s+SAY", next_upper):
                break
            nearby.append(lines[look_ahead])

        for amount, number in line_amount_candidates(" ".join(nearby)):
            if number <= 0:
                continue
            if total_number is not None and number > total_number:
                continue
            if best is None or number > best[1]:
                best = (amount, number)

    return best[0] if best else None


def extract_tax_summary(lines: list[str]) -> tuple[str | None, str | None]:
    amount_pattern = re.compile(r"[*#¥+·]?\d+(?:[.\s]\d{3})*[,.]\d{2}")
    normalized_lines = [normalize_text(line).upper() for line in lines]
    candidates: list[tuple[str, str, float, float]] = []

    for index, line in enumerate(lines):
        upper = normalized_lines[index]
        if re.search(r"K[UO]M", upper):
            continue

        has_total = bool(re.search(r"TOPLAM|TOPIAM|TOPL/|TOPSAT|TOP\s+SAT|TOP\s+KASA", upper))
        has_kdv = bool(re.search(r"TOPKDV|KDV|IUV|KOV", upper))
        if not has_total and not has_kdv:
            continue

        relevant_line = line
        keyword_match = re.search(r"TOPSAT|TOP\s+SAT|TOPLAM|TOPIAM|TOPL/|TOP\s+KASA|%\s*\d+\s*TOPLAM", upper)
        if keyword_match:
            relevant_line = line[keyword_match.start():]
        current_amounts = extract_tax_amounts(relevant_line)
        current_amounts = [amount for amount in current_amounts if amount]

        if has_total and has_kdv and len(current_amounts) >= 2:
            parsed = [(amount, parse_amount(amount)) for amount in current_amounts]
            parsed = [(amount, number) for amount, number in parsed if number is not None and number >= 0]
            if len(parsed) >= 2:
                total_amount, total_number = max(parsed, key=lambda item: item[1])
                kdv_options = [
                    (amount, number) for amount, number in parsed
                    if (0 < number < total_number) or (number == 0 and total_number == 0)
                ]
                if kdv_options:
                    positive_options = [(amount, number) for amount, number in kdv_options if number > 0]
                    kdv_amount, kdv_number = min(positive_options or kdv_options, key=lambda item: item[1])
                    candidates.append((total_amount, kdv_amount, total_number, kdv_number))

        if has_total and current_amounts:
            total_candidates = [(amount, parse_amount(amount)) for amount in current_amounts]
            total_candidates = [(amount, number) for amount, number in total_candidates if number is not None]
            if not total_candidates:
                continue
            toplam = max(total_candidates, key=lambda item: item[1])[0]

            for look_ahead in range(index + 1, min(index + 4, len(lines))):
                next_upper = normalized_lines[look_ahead]
                if re.search(r"K[UO]M", next_upper):
                    break
                if not re.search(r"TOPKDV|KDV", next_upper):
                    continue
                kdv_amounts = extract_tax_amounts(lines[look_ahead])
                kdv_amounts = [amount for amount in kdv_amounts if amount]
                if not kdv_amounts:
                    continue
                kdv_candidates = [(amount, parse_amount(amount)) for amount in kdv_amounts]
                kdv_candidates = [(amount, number) for amount, number in kdv_candidates if number is not None and number >= 0]
                total_number = parse_amount(toplam)
                kdv_candidates = [
                    (amount, number) for amount, number in kdv_candidates
                    if total_number is not None and ((0 <= number < total_number) or (number == 0 and total_number == 0))
                ]
                if kdv_candidates:
                    kdv = min(kdv_candidates, key=lambda item: item[1])[0]
                    kdv_number = parse_amount(kdv)
                    if total_number is not None and kdv_number is not None:
                        candidates.append((toplam, kdv, total_number, kdv_number))

    if not candidates:
        return None, None
    plausible = [
        candidate for candidate in candidates
        if candidate[2] == 0 or 0 <= candidate[3] / candidate[2] <= 0.25
    ]
    best = max(plausible or candidates, key=lambda item: (item[2], item[3] > 0, item[3]))
    return best[0], best[1]


def extract_cumulative_summary(lines: list[str]) -> tuple[str | None, str | None, str | None]:
    amount_pattern = re.compile(r"[*#¥+·]?\d+(?:[.\s]\d{3})*[,.]\d{2}")
    kum_top = None
    kum_kdv = None
    kum_knv = None

    for line in lines:
        upper = normalize_text(line).upper()
        if not re.search(r"K[UO]M", upper):
            continue

        amounts = [normalize_amount(value) for value in amount_pattern.findall(line)]
        amounts = [amount for amount in amounts if amount]
        if not amounts:
            continue

        has_top = "TOP" in upper or "TOPLAM" in upper
        has_kdv = "KDV" in upper or "TOPKDV" in upper
        has_knv = "KNV" in upper

        if has_top and has_kdv and len(amounts) >= 2:
            kum_top = amounts[0]
            kum_kdv = amounts[1]
        elif has_top and not has_kdv and not kum_top:
            kum_top = amounts[0]
            if len(amounts) >= 2 and not kum_kdv:
                kum_kdv = amounts[1]
        elif has_kdv and not kum_kdv:
            kum_kdv = amounts[0]
        elif has_knv and not kum_knv:
            kum_knv = amounts[0]

    return kum_top, kum_kdv, kum_knv


def most_common_transaction_total(amounts: list[str]) -> str | None:
    candidates = []
    for amount in amounts:
        number = parse_amount(amount)
        if number is None:
            continue
        if 50 <= number <= 100_000:
            candidates.append(amount)
    if not candidates:
        return None
    return Counter(candidates).most_common(1)[0][0]


def extract_receipt_fields(raw_text: str, confidence: float) -> dict[str, Any]:
    lines = [line for line in raw_text.splitlines() if line.strip()]
    flat = normalize_text(" ".join(lines)).upper()
    amounts = extract_amounts(flat)

    tarih = find_receipt_date(lines)
    saat = find_first([r"\b(\d{2}:\d{2})\b"], flat)
    fis_no = find_first([r"FIS\s*NO\s*:?\s*(\d{3,8})", r"FI[SŞ]\s*NO\s*:?\s*(\d{3,8})"], flat)
    z_no = find_z_no(lines, flat)
    kdv_orani = find_first([r"(%\s*\d{1,2})", r"TOP(?:LAM|SAT)?\s*/\s*(\d{1,2})", r"TOPKDV\s*/\s*(\d{1,2})"], flat)
    adet = find_first([r"ADET\s*:?\s*(\d+,\d{3})", r"(%\s*\d{1,2})\s+(\d+,\d{3})"], flat)
    if adet and adet.startswith("%"):
        adet = None
    if not adet:
        adet = find_first([r"\b(\d+,\d{3})\b"], flat)

    tax_toplam, tax_kdv = extract_tax_summary(lines)
    toplam = tax_toplam or find_amount_after([r"^TOPLAM$", r"TOPLAM"], lines) or most_common_transaction_total(amounts)
    kdv = tax_kdv or find_amount_after([r"^KDV$", r"TOPKDV"], lines)
    if parse_amount(toplam or "") == 0:
        kdv = "0,00"
    if not kdv:
        total_number = parse_amount(toplam or "")
        for amount in amounts:
            number = parse_amount(amount)
            if total_number and number and 0 < number < total_number:
                kdv = amount
                break
    kdv = reconcile_kdv_with_rate(toplam, kdv, kdv_orani)
    toplam, kdv = repair_small_total(lines, toplam, kdv, kdv_orani)

    banka_kredi_karti = extract_card_amount(lines, toplam) or find_amount_after([r"BANKA", r"KREDI", r"K\.?\s*KARTI", r"KARTI"], lines) or toplam
    cumulative_top, cumulative_kdv, cumulative_knv = extract_cumulative_summary(lines)
    kum_top = cumulative_top or find_amount_after([r"K[UO]M\.?\s*TOP"], lines)
    kum_kdv = cumulative_kdv or find_amount_after([r"K[UO]M\.?\s*KDV"], lines)
    kum_knv = cumulative_knv or find_amount_after([r"K[UO]M\.?\s*KNV"], lines)

    return {
        "tarih": tarih,
        "saat": saat,
        "fis_no": fis_no,
        "z_no": z_no,
        "kategori": "YIYECEK" if "YIYECEK" in flat else None,
        "kdv_orani": normalize_kdv_rate(kdv_orani),
        "adet": adet,
        "toplam": toplam,
        "kdv": kdv,
        "banka_kredi_karti": banka_kredi_karti,
        "kum_top": kum_top,
        "kum_kdv": kum_kdv,
        "kum_knv": kum_knv,
        "ocr_confidence": confidence,
    }


def extract_from_path(image_path: Path) -> ReceiptResponse:
    raw_text, confidence = ocr_image(image_path)
    if not raw_text:
        raise HTTPException(status_code=422, detail="Gorselden metin okunamadi.")
    return ReceiptResponse(
        filename=image_path.name,
        fields=extract_receipt_fields(raw_text, confidence),
        raw_text=raw_text,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def upload_page() -> str:
    return """
<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fiş OCR</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Arial, sans-serif;
      background: #f5f5f2;
      color: #1f2933;
    }
    body {
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }
    main {
      width: min(960px, 100%);
      background: white;
      border: 1px solid #ddd8ce;
      border-radius: 8px;
      padding: 22px;
      box-shadow: 0 10px 30px rgba(0,0,0,.08);
    }
    h1 {
      font-size: 24px;
      margin: 0 0 16px;
    }
    .bar {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 18px;
    }
    input[type=file] {
      flex: 1;
      min-width: 260px;
      border: 1px solid #cfc8bc;
      border-radius: 6px;
      padding: 10px;
      background: #fbfaf7;
    }
    button {
      border: 0;
      border-radius: 6px;
      padding: 11px 16px;
      background: #1f6feb;
      color: white;
      font-weight: 700;
      cursor: pointer;
    }
    button:disabled {
      opacity: .55;
      cursor: wait;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 10px;
      margin: 16px 0;
    }
    .field {
      border: 1px solid #e4dfd5;
      border-radius: 6px;
      padding: 10px;
      background: #fffdf8;
    }
    .label {
      font-size: 12px;
      color: #667085;
      margin-bottom: 4px;
      text-transform: uppercase;
    }
    .value {
      font-size: 18px;
      font-weight: 700;
      word-break: break-word;
    }
    pre {
      overflow: auto;
      background: #111827;
      color: #e5e7eb;
      padding: 14px;
      border-radius: 6px;
      max-height: 340px;
    }
    .status {
      min-height: 22px;
      color: #475467;
      margin-top: 8px;
    }
  </style>
</head>
<body>
  <main>
    <h1>Fiş OCR</h1>
    <div class="bar">
      <input id="file" type="file" accept="image/*">
      <button id="send" type="button">Gönder</button>
    </div>
    <div id="status" class="status"></div>
    <section id="fields" class="grid"></section>
    <pre id="json">{}</pre>
  </main>

  <script>
    const fileInput = document.getElementById("file");
    const sendButton = document.getElementById("send");
    const statusBox = document.getElementById("status");
    const fieldsBox = document.getElementById("fields");
    const jsonBox = document.getElementById("json");

    const labels = {
      tarih: "Tarih",
      saat: "Saat",
      fis_no: "Fiş No",
      z_no: "Z No",
      kategori: "Kategori",
      kdv_orani: "KDV Oranı",
      adet: "Adet",
      toplam: "Toplam",
      kdv: "KDV",
      banka_kredi_karti: "Banka/Kredi Kartı",
      kum_top: "KUM.TOP",
      kum_kdv: "KUM.KDV",
      kum_knv: "KUM.KNV",
      ocr_confidence: "OCR Güven"
    };

    function renderFields(fields) {
      fieldsBox.innerHTML = "";
      Object.keys(labels).forEach((key) => {
        const card = document.createElement("div");
        card.className = "field";
        const label = document.createElement("div");
        label.className = "label";
        label.textContent = labels[key];
        const value = document.createElement("div");
        value.className = "value";
        value.textContent = fields?.[key] ?? "-";
        card.append(label, value);
        fieldsBox.appendChild(card);
      });
    }

    sendButton.addEventListener("click", async () => {
      const file = fileInput.files[0];
      if (!file) {
        statusBox.textContent = "Önce bir resim seç.";
        return;
      }

      const formData = new FormData();
      formData.append("file", file);
      sendButton.disabled = true;
      statusBox.textContent = "Okunuyor...";

      try {
        const response = await fetch("/extract", { method: "POST", body: formData });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "İstek başarısız.");
        renderFields(data.fields);
        jsonBox.textContent = JSON.stringify(data, null, 2);
        statusBox.textContent = "Tamamlandı.";
      } catch (error) {
        statusBox.textContent = error.message;
      } finally {
        sendButton.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


@app.post("/extract", response_model=ReceiptResponse)
async def extract(file: UploadFile = File(...)) -> ReceiptResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="JPG, PNG, BMP, TIFF veya WEBP gorsel yukleyin.")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        temp_path = Path(temp.name)
        temp.write(await file.read())

    try:
        return extract_from_path(temp_path).model_copy(update={"filename": file.filename or temp_path.name})
    finally:
        temp_path.unlink(missing_ok=True)


@app.get("/extract-sample/{name}", response_model=ReceiptResponse)
def extract_sample(name: str) -> ReceiptResponse:
    image_path = (SAMPLE_DIR / name).resolve()
    if not str(image_path).startswith(str(SAMPLE_DIR.resolve())) or not image_path.exists():
        raise HTTPException(status_code=404, detail="Ornek fis bulunamadi.")
    return extract_from_path(image_path)
