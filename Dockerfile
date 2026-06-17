FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости системы, если они нужны (например, для компиляции пакетов)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем и устанавливаем Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код проекта
COPY . .

# Команда для запуска объединенного лаунчера (FastAPI + Discord Bot)
CMD ["python", "run.py"]
