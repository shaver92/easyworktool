FROM python:3.12-slim

WORKDIR /app

COPY requirements-bot.txt .
RUN pip install --no-cache-dir -r requirements-bot.txt

COPY bot/ ./bot/
COPY shared/ ./shared/
COPY config.toml .

RUN mkdir -p /app/data

EXPOSE 8000
CMD ["uvicorn", "bot.main:app", "--host", "0.0.0.0", "--port", "8000"]
