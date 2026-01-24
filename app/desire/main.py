from fastapi import FastAPI

from .routers.need_card import router as need_card_router

app = FastAPI(
    title="Need Card Service",
    description="대화 로그를 분석해서 8가지 욕구 점수를 계산하고 상위 4개를 돌려주는 서비스",
)

# 욕구카드 라우터 등록
app.include_router(need_card_router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
