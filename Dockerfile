FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# deps primero para cache
COPY requirements.txt .
RUN pip install -U pip && pip install -r requirements.txt

# copia TODO el proyecto (incluye app/, agents/, etc.)
COPY . .

# el command lo define compose; acá dejamos un no-op
CMD ["python", "-c", "print('image ready')"]
