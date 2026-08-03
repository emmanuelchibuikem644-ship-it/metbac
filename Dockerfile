FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

# Daphne serves both HTTP and WebSocket traffic (needed once Channels
# messaging is added); swap to gunicorn if you never add WebSockets.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
