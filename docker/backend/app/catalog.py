"""
Загрузка каталога «Своё Вино» и построение нормализованного текстового индекса
для фаззи-сопоставления с OCR-текстом этикетки.

Поддерживаются оба формата, упомянутых в ТЗ:
  - CSV (публичный дамп для тестирования, "по одной эталонной фотографии на позицию")
  - JSON (формат дампа БД для продовой интеграции)

Ожидаемые (гибко сопоставляемые) поля одной позиции каталога:
  slug, name, producer, region, grape, category, vintage,
  description, roskachestvo_score, food_pairing, image_url
Если реальный дамп называет поля иначе — правьте ALIASES ниже,
переписывать остальной пайплайн не требуется.
"""

import csv
import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.ocr import normalize_text

ALIASES: Dict[str, List[str]] = {
    "slug": ["slug", "id", "sku", "code"],
    "name": ["name", "title", "wine_name", "наименование", "название"],
    "producer": ["producer", "winery", "brand", "производитель", "винодельня"],
    "region": ["region", "регион"],
    "grape": ["grape", "sort", "variety", "сорт", "сорт_винограда"],
    "category": ["category", "type", "категория", "тип"],
    "color": ["color", "цвет"],
    "vintage": ["vintage", "year", "год"],
    "description": ["description", "desc", "описание"],
    "roskachestvo_score": ["roskachestvo_score", "roskachestvo", "score", "балл_роскачества"],
    "public_rating": ["public_rating", "rating", "народный_рейтинг", "рейтинг"],
    "abv": ["abv", "alcohol", "крепость"],
    "serving_temp": ["serving_temp", "temperature", "температура_подачи"],
    "food_pairing": ["food_pairing", "pairing", "к_чему_подать", "гастропара", "сочетание_с_блюдами"],
    "image_url": ["image_url", "image", "photo", "image_path"],
}


def _pick(row: dict, field_name: str) -> Optional[str]:
    for alias in ALIASES[field_name]:
        for key in row.keys():
            if key.strip().lower() == alias:
                value = row[key]
                if value is None:
                    continue
                value = str(value).strip()
                if value:
                    return value
    return None


@dataclass
class CatalogItem:
    slug: str
    name: str
    producer: Optional[str] = None
    region: Optional[str] = None
    grape: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    vintage: Optional[str] = None
    description: Optional[str] = None
    roskachestvo_score: Optional[float] = None
    public_rating: Optional[float] = None
    abv: Optional[str] = None
    serving_temp: Optional[str] = None
    food_pairing: List[str] = field(default_factory=list)
    image_url: Optional[str] = None
    search_text: str = field(default="", repr=False)

    def to_card_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "producer": self.producer,
            "region": self.region,
            "grape": self.grape,
            "category": self.category,
            "color": self.color,
            "vintage": self.vintage,
            "description": self.description,
            "roskachestvo_score": self.roskachestvo_score,
            "public_rating": self.public_rating,
            "abv": self.abv,
            "serving_temp": self.serving_temp,
            "food_pairing": self.food_pairing,
            "image_url": self.image_url,
        }


def _row_to_item(row: dict) -> Optional[CatalogItem]:
    slug = _pick(row, "slug")
    name = _pick(row, "name")
    if not slug or not name:
        return None

    def _to_float(field_name: str) -> Optional[float]:
        raw = _pick(row, field_name)
        if not raw:
            return None
        try:
            return float(raw.replace(",", ".").replace("%", "").strip())
        except ValueError:
            return None

    food_raw = _pick(row, "food_pairing")
    food_pairing = [p.strip() for p in re.split(r"[;,]", food_raw) if p.strip()] if food_raw else []

    item = CatalogItem(
        slug=slug,
        name=name,
        producer=_pick(row, "producer"),
        region=_pick(row, "region"),
        grape=_pick(row, "grape"),
        category=_pick(row, "category"),
        color=_pick(row, "color"),
        vintage=_pick(row, "vintage"),
        description=_pick(row, "description"),
        roskachestvo_score=_to_float("roskachestvo_score"),
        public_rating=_to_float("public_rating"),
        abv=_pick(row, "abv"),
        serving_temp=_pick(row, "serving_temp"),
        food_pairing=food_pairing,
        image_url=_pick(row, "image_url"),
    )
    parts = [item.name, item.producer, item.region, item.grape, item.category, item.vintage]
    item.search_text = normalize_text(" ".join(p for p in parts if p))
    return item


def load_catalog(path: str) -> List[CatalogItem]:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Файл каталога не найден: {path}. "
            f"Положите дамп каталога «Своё Вино» (CSV или JSON) по этому пути "
            f"(см. volume в docker-compose.yml -> ./backend/data)."
        )

    items: List[CatalogItem] = []
    ext = os.path.splitext(path)[1].lower()

    if ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rows = data if isinstance(data, list) else data.get("items", data.get("data", []))
        for row in rows:
            item = _row_to_item(row)
            if item:
                items.append(item)
    else:  # CSV по умолчанию
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                item = _row_to_item(row)
                if item:
                    items.append(item)

    if not items:
        raise ValueError(
            f"Каталог {path} загружен, но не содержит распознанных позиций. "
            f"Проверьте названия колонок / ALIASES в app/catalog.py."
        )
    return items
