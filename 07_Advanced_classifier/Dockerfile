FROM python:3.11-slim

WORKDIR /app

# 의존성 먼저 설치 (레이어 캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY schemas.py auth.py indexing.py retrieval.py main.py ./

# token.json / credentials.json 은 볼륨으로 주입 (빌드에 포함하지 않음)
VOLUME ["/app/token.json", "/app/credentials.json"]

CMD ["python", "main.py"]