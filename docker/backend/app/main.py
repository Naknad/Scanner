import logging
import os
import time

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.catalog import load_catalog
from app.config import settings
from app.matcher import CatalogIndex
from app.ocr import extract_and_normalize
from app.schemas import CandidateScore, FlatPrediction, ScanResponse, WineCard

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scanner")

app = FastAPI(title="Своё Вино — сканер этикеток (MVP, OCR)", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_index: CatalogIndex | None = None


@app.on_event("startup")
def _startup() -> None:
    global _index
    try:
        items = load_catalog(settings.CATALOG_PATH)
        _index = CatalogIndex(items)
        logger.info("Каталог загружен: %d позиций из %s", len(items), settings.CATALOG_PATH)
    except Exception as exc:  # noqa: BLE001
        # Не роняем контейнер: /api/health отдаст статус, сканирование вернёт 503
        logger.error("Не удалось загрузить каталог: %s", exc)
        _index = None


def _require_index() -> CatalogIndex:
    if _index is None:
        raise HTTPException(
            status_code=503,
            detail="Каталог не загружен. Проверьте CATALOG_PATH и volume ./backend/data.",
        )
    return _index


@app.get("/api/health")
def health():
    return {
        "status": "ok" if _index is not None else "catalog_missing",
        "catalog_size": len(_index.items) if _index else 0,
    }


def _build_response(query_text: str, candidates: list[CandidateScore], started_at: float) -> ScanResponse:
    idx = _require_index()
    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 1)

    if not candidates:
        return ScanResponse(
            status="not_found",
            query_text=query_text,
            top5=[],
            response_time_ms=elapsed_ms,
        )

    top1 = candidates[0]
    gap = round(top1.score - candidates[1].score, 2) if len(candidates) > 1 else top1.score

    # Ниже порога уверенности -> не считаем найденным, предлагаем похожие
    if top1.score < settings.MATCH_MIN_SCORE:
        similar_items = []
        for c in candidates:
            item = idx.get_by_slug(c.slug)
            if item:
                similar_items.append(WineCard(**item.to_card_dict()))
        return ScanResponse(
            status="not_found",
            query_text=query_text,
            top1=top1,
            top5=candidates,
            gap=gap,
            similar=similar_items,
            response_time_ms=elapsed_ms,
        )

    item = idx.get_by_slug(top1.slug)
    card = WineCard(**item.to_card_dict()) if item else None

    # Отрыв top1/top2 недостаточен -> отдаём карточку, но помечаем как ambiguous,
    # чтобы фронтенд при желании мог показать альтернативы (см. ТЗ: при стабильно
    # высоком F1 экран выбора не нужен вовсе).
    status = "found" if gap >= settings.MATCH_GAP_THRESHOLD else "ambiguous"

    return ScanResponse(
        status=status,
        query_text=query_text,
        top1=top1,
        top5=candidates,
        gap=gap,
        card=card,
        response_time_ms=elapsed_ms,
    )


@app.post("/api/scan", response_model=ScanResponse)
async def scan(file: UploadFile = File(...)):
    """Полный ответ для веб-интерфейса: карточка + метрики уверенности."""
    started = time.perf_counter()
    idx = _require_index()
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Пустой файл изображения.")

    query_text = extract_and_normalize(image_bytes)
    candidates = idx.search(query_text)
    return _build_response(query_text, candidates, started)


@app.post("/api/predict", response_model=FlatPrediction)
async def predict(file: UploadFile = File(...)):
    """
    Плоский формат для скрипта оценки кейсодержателя:
    {"slug": "wine-slug"} — всегда один лучший результат, без обёрток.
    """
    idx = _require_index()
    image_bytes = await file.read()
    query_text = extract_and_normalize(image_bytes)
    candidates = idx.search(query_text, top_k=1)
    slug = candidates[0].slug if candidates else ""
    return JSONResponse({"slug": slug})


@app.get("/api/card/{slug}", response_model=WineCard)
def get_card(slug: str):
    idx = _require_index()
    item = idx.get_by_slug(slug)
    if not item:
        raise HTTPException(status_code=404, detail="Позиция не найдена в каталоге.")
    return WineCard(**item.to_card_dict())


@app.get("/api/sommelier/{slug}")
def sommelier(slug: str, occasion: str | None = None, dish: str | None = None):
    """
    MVP-версия «Цифрового сомелье» (фича удержания после поиска).
    Правило-ориентированная логика поверх уже имеющихся полей каталога —
    без внешних LLM-вызовов, чтобы не тянуть сетевые зависимости в MVP.
    Точка расширения: замените тело функции вызовом LLM (см. ARCHITECTURE.md).
    """
    idx = _require_index()
    item = idx.get_by_slug(slug)
    if not item:
        raise HTTPException(status_code=404, detail="Позиция не найдена в каталоге.")

    tips = []
    if item.food_pairing:
        tips.append(f"К этому вину рекомендуют: {', '.join(item.food_pairing)}.")
    if dish:
        tips.append(
            f"Для блюда «{dish}» это вино подойдёт, если вы цените "
            f"{(item.grape or 'выбранный сорт')} из региона {(item.region or 'производителя')}."
        )
    if occasion:
        tips.append(f"Для повода «{occasion}» обратите внимание на категорию: {item.category or 'уточняется'}.")
    if not tips:
        tips.append("Для этого вина пока нет расширенных гастро-рекомендаций в каталоге.")

    # Похожие позиции той же категории/сорта — «аналоги из других виноделен»
    analogs = [
        WineCard(**other.to_card_dict())
        for other in idx.items
        if other.slug != item.slug
        and other.grape
        and item.grape
        and other.grape.lower() == item.grape.lower()
    ][:5]

    return {"tips": tips, "analogs": [a.model_dump() for a in analogs]}


# --- Статика фронтенда (mobile-first интерфейс в стилистике «Своё Вино») ---
_frontend_dir = settings.FRONTEND_DIR
if os.path.isdir(_frontend_dir):
    app.mount("/static", StaticFiles(directory=os.path.join(_frontend_dir, "static")), name="static")

    @app.get("/")
    def index_page():
        return FileResponse(os.path.join(_frontend_dir, "index.html"))

    @app.get("/card")
    def card_page():
        return FileResponse(os.path.join(_frontend_dir, "card.html"))
