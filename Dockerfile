# Stage 1: Install UV and dependencies
FROM python:3.11-slim AS builder

# Instalar UV (package manager rápido)
RUN pip install uv

WORKDIR /app

# Copiar solo archivos de dependencias para cache
COPY pyproject.toml ./

# Compilar requirements a archivo
RUN uv pip compile pyproject.toml -o requirements.txt

# Instalar dependencias con UV
RUN uv pip install --system -r requirements.txt

# Stage 2: Runtime image
FROM python:3.11-slim

WORKDIR /app

# Copiar dependencias instaladas desde builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copiar todo el proyecto (estructura: /app/app/main.py, /app/app/templates/, etc.)
COPY . .

# Exponer puerto
EXPOSE 8000

# Variables de entorno por defecto
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production
ENV PYTHONPATH=/app

# Ejecutar con uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
