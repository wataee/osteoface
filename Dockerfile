FROM python:3.11-slim

# Установка системных зависимостей для работы с БД
RUN apt-get update && apt-get install -if-y sqlite3

WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код
COPY . .

# Команда запуска бота
CMD ["python", "bot.py"]
