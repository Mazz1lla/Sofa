# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости и приложение
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Указываем переменную окружения для Flask
ENV FLASK_APP=app.py

# Указываем порт (Railway использует переменную PORT)
ENV PORT=5000

# Запускаем Flask на нужном порту
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
