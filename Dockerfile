# 1. Берем официальный образ Python 3.11 (как на Raspberry)
FROM python:3.11-slim

# 2. Устанавливаем системные зависимости для OpenCV (они нужны, чтобы картинки открывались)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 3. Указываем рабочую папку внутри контейнера
WORKDIR /app

# 4. Копируем файл со списком библиотек из корня в контейнер
COPY requirements.txt .

# 5. Устанавливаем все библиотеки (OpenCV, numpy и т.д.)
RUN pip install --no-cache-dir -r requirements.txt

# 6. Копируем ВЕСЬ наш проект (все папки: landing, drone и т.д.) в контейнер
COPY . .

# 7. Пока что поставим запуск твоего скрипта посадки по умолчанию
CMD ["python", "landing/aruco_landing.py"]
# тут надо будет поменять, что именно запускается
