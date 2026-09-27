import os


class Settings:
    CATALOG_PATH: str = os.getenv("CATALOG_PATH", "/app/data/catalog.csv")
    OCR_LANGS: str = os.getenv("OCR_LANGS", "rus+eng")
    # Порог, ниже которого top-1 считается ненадёжным -> "не найдено" / похожие
    MATCH_MIN_SCORE: float = float(os.getenv("MATCH_MIN_SCORE", "55"))
    # Требуемый отрыв (в баллах rapidfuzz, 0-100) между top-1 и top-2,
    # чтобы не показывать экран выбора и сразу отдавать финальную карточку
    MATCH_GAP_THRESHOLD: float = float(os.getenv("MATCH_GAP_THRESHOLD", "8"))
    TOP_K: int = int(os.getenv("TOP_K", "5"))
    FRONTEND_DIR: str = os.getenv("FRONTEND_DIR", "/app/frontend")


settings = Settings()
