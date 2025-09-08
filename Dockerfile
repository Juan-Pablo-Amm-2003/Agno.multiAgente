FROM python:3.12-slim

# + estabilidad de logs y bytecode
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Curl para el HEALTHCHECK (muy útil en Render)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala deps primero para cacheo eficiente
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir -r requirements.txt

# Código
COPY . .

# Usuario no root (opcional pero recomendado)
RUN useradd -m appuser
USER appuser

# Render inyecta $PORT; exponemos 8000 como valor por defecto
EXPOSE 8000

# Arranque: siempre usa $PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]

# Healthcheck interno (Render también hace su healthcheck, esto ayuda al diagnóstico)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT}/health || exit 1
