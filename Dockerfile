FROM python:3.11-slim

WORKDIR /app

# نصب پکیج‌های پیش‌نیاز سیستم برای بیلد psycopg2 و argon2 در صورت نیاز
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
