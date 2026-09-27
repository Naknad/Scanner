from typing import List, Optional
from pydantic import BaseModel


class WineCard(BaseModel):
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
    public_rating: Optional[float] = None  # «Народный рейтинг», 0–5, как на vino-svoe.ru
    abv: Optional[str] = None  # Крепость вина, напр. "13%"
    serving_temp: Optional[str] = None  # Температура подачи, напр. "10–12°C"
    food_pairing: List[str] = []  # Сочетание с блюдами — список, как на карточке сайта
    image_url: Optional[str] = None


class CandidateScore(BaseModel):
    slug: str
    name: str
    score: float


class ScanResponse(BaseModel):
    status: str  # "found" | "not_found" | "ambiguous"
    query_text: Optional[str] = None
    top1: Optional[CandidateScore] = None
    top5: List[CandidateScore] = []
    gap: Optional[float] = None
    card: Optional[WineCard] = None
    similar: List[WineCard] = []
    response_time_ms: Optional[float] = None


class FlatPrediction(BaseModel):
    slug: str
