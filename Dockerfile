FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -U pip && pip install -r requirements.txt

COPY . .

# Render expone el puerto en $PORT. No hardcodees el 8000.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
