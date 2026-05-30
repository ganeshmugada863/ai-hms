FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/hospital_management_system

RUN python manage.py collectstatic --noinput --clear

EXPOSE 7860

CMD ["gunicorn", "--bind", "0.0.0.0:7860", "hospital_management_system.wsgi:application"]
