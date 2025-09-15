FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dependências necessárias para pymssql / FreeTDS
RUN apt-get update && apt-get install -y \
    build-essential \
    freetds-dev freetds-bin unixodbc-dev \
    gcc g++ \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]