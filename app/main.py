# app/main.py  (통합 엔트리포인트 - 새 파일)
from dotenv import load_dotenv

# 루트 .env 로딩 (backend가 dotenv를 직접 안 쓰는 구조라서 여기서 한 번에 로딩하는 게 안전함)
load_dotenv()

# backend를 메인 앱으로 사용
from app.backend.main import app as app  # noqa: E402

# 나머지 두 서비스는 서브앱으로 mount
from app.desire.main import app as desire_app  # noqa: E402
from app.analyze.main import app as analyze_app  # noqa: E402

app.mount("/desire", desire_app)
app.mount("/analyze", analyze_app)
