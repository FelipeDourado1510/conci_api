FROM python:3.11-slim

# Evita perguntas interativas durante instalação
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
    pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Cria diretório de trabalho
WORKDIR /app

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação
COPY . .

# Cria diretório para arquivos e define permissões
RUN mkdir -p /data && chmod 755 /data

# Cria volume
VOLUME ["/data"]

# Expõe porta
EXPOSE 5000

# Comando de inicialização
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "app:app"]
