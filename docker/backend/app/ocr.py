"""
OCR-модуль: нормализация фотографии этикетки + извлечение текста.

Подсказка кейсодержателя: нормализация фото заметно улучшает F1.
Здесь применяется базовый, но эффективный набор шагов классического CV:
  1. Приведение к серому.
  2. Автоконтраст / CLAHE (выравнивание освещённости, борьба с бликами).
  3. Адаптивная бинаризация.
  4. Оценка и коррекция угла поворота (deskew) по минимальной ограничивающей рамке текста.
  5. Апскейл мелких изображений (OCR слабо работает на низком разрешении).

Всё выполняется на CPU, без нейросетей — соответствует требованию
"использование нейросетей не обязательно; классическое CV/OCR-решение допустимо".
"""

import re
import unicodedata
from io import BytesIO

import cv2
import numpy as np
import pytesseract
from PIL import Image

from app.config import settings

_MIN_SIDE_FOR_UPSCALE = 900


def _read_image(image_bytes: bytes) -> np.ndarray:
    pil_img = Image.open(BytesIO(image_bytes)).convert("RGB")
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def _deskew(gray: np.ndarray) -> np.ndarray:
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 20:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    # Не пытаемся крутить, если угол ничтожен или явно ошибочен
    if abs(angle) < 0.5 or abs(angle) > 20:
        return gray
    (h, w) = gray.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def preprocess(image_bytes: bytes) -> np.ndarray:
    """Возвращает подготовленное для OCR ч/б изображение (numpy array)."""
    bgr = _read_image(image_bytes)

    h, w = bgr.shape[:2]
    if min(h, w) < _MIN_SIDE_FOR_UPSCALE:
        scale = _MIN_SIDE_FOR_UPSCALE / min(h, w)
        bgr = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # CLAHE — борьба с неравномерным освещением и бликами на этикетке
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    gray = cv2.bilateralFilter(gray, 7, 50, 50)
    gray = _deskew(gray)

    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    return binary


def extract_text(image_bytes: bytes) -> str:
    processed = preprocess(image_bytes)
    config = "--oem 3 --psm 6"
    raw = pytesseract.image_to_string(processed, lang=settings.OCR_LANGS, config=config)
    return raw


_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Нижний регистр, снятие диакритики, чистка пунктуации/лишних пробелов."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def extract_and_normalize(image_bytes: bytes) -> str:
    return normalize_text(extract_text(image_bytes))
