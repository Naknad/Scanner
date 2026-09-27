"""
Сопоставление нормализованного OCR-текста с каталогом.

MVP-подход: классический fuzzy string matching (rapidfuzz) по
конкатенированному нормализованному тексту позиции (название + производитель +
регион + сорт + категория). Для MVP этого достаточно и не требует GPU/обучения.

Точка расширения (см. ARCHITECTURE.md): здесь же в будущем подключается
CV-эмбеддинг (например SigLIP) для сравнения по изображению, а OCR остаётся
как усиливающий сигнал — как и рекомендовано в ТЗ.
"""

from typing import List

from rapidfuzz import fuzz, process

from app.catalog import CatalogItem
from app.config import settings
from app.schemas import CandidateScore


class CatalogIndex:
    def __init__(self, items: List[CatalogItem]):
        self.items = items
        self._choices = [item.search_text for item in items]

    def search(self, query_text: str, top_k: int = None) -> List[CandidateScore]:
        top_k = top_k or settings.TOP_K
        if not query_text:
            return []

        results = process.extract(
            query_text,
            self._choices,
            scorer=fuzz.token_sort_ratio,
            limit=top_k,
        )
        # results: List[Tuple[choice_str, score, index]]
        candidates = []
        for _, score, idx in results:
            item = self.items[idx]
            candidates.append(CandidateScore(slug=item.slug, name=item.name, score=round(score, 2)))
        return candidates

    def get_by_slug(self, slug: str) -> CatalogItem | None:
        for item in self.items:
            if item.slug == slug:
                return item
        return None
