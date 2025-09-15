FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala dependências do sistema necessárias para pymssql
RUN apt-get update && apt-get install -y \
    build-essential \
    freetds-dev \
    freetds-bin \
    unixodbc-dev \
    gcc \
    g++ \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Cria diretório de trabalho
WORKDIR /app

# Instala dependências Python diretamente
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    Flask==2.3.3 \
    gunicorn==21.2.0 \
    SQLAlchemy==2.0.21 \
    pandas==2.1.1 \
    pymssql==2.2.8

# Copia código da aplicação
COPY . .

# Cria diretório para arquivos
RUN mkdir -p /data && chmod 755 /data

# Volume
VOLUME ["/data"]

# Expõe porta
EXPOSE 5000

# Comando de inicialização
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "app:app"]
