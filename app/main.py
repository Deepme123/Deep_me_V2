# app/main.py  (통합 엔트리포인트 - 새 파일)
from dotenv import load_dotenv

load_dotenv()

from app.backend.main import app as app  # noqa: E402

from app.analyze.routers import cards as cards_router  # noqa: E402
from app.analyze.routers import summaries as summaries_router  # noqa: E402
from app.desire.routers.need_card import router as need_card_router  # noqa: E402

app.include_router(cards_router.router, prefix="/analyze")
app.include_router(summaries_router.router, prefix="/analyze")
app.include_router(need_card_router, prefix="/desire")

