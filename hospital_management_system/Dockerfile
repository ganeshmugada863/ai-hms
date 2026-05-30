FROM python:3.13-slim

# Ensure UTF-8 locale and Python handling
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUTF8=1

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=hospital_management_system.settings
ENV SECRET_KEY=dummy_secret_key

WORKDIR /app

# System dependencies for building psycopg2 & static handling
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure staticfiles directory exists before collectstatic
RUN mkdir -p staticfiles

# Collect static files (build‑time only). The dummy SECRET_KEY is already set via ENV.
RUN python manage.py collectstatic --noinput

EXPOSE 7860

CMD python manage.py migrate && \
    gunicorn hospital_management_system.wsgi:application --bind 0.0.0.0:7860
