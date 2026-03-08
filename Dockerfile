FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update     && apt-get install -y --no-install-recommends build-essential libpq-dev     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip     && pip install -r requirements.txt

COPY . .

EXPOSE 8082

CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8082", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
