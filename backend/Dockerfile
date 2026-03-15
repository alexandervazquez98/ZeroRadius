FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && apt-get install -y default-libmysqlclient-dev pkg-config gcc \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get clean

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
