FROM python:3.11.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd -m -u 1000 -s /bin/bash appuser

RUN pip install --no-cache-dir \
    "streamlit==1.39.0" \
    "httpx==0.27.0" \
    "pandas==2.2.2" \
    "psycopg2-binary==2.9.9" \
    "sqlalchemy==2.0.30"

COPY --chown=appuser:appuser app/ ./app/

EXPOSE 8501

USER appuser

CMD ["streamlit", "run", "app/main.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false"]
