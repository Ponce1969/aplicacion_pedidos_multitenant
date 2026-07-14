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

# Build Tailwind CSS con el standalone CLI (detecta arquitectura: x86_64 / aarch64)
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ]; then TAILWIND_ARCH=arm64; elif [ "$ARCH" = "x86_64" ]; then TAILWIND_ARCH=x64; else echo "Unsupported architecture: $ARCH"; exit 1; fi && \
    python -c "import urllib.request, sys; urllib.request.urlretrieve(sys.argv[1], '/usr/local/bin/tailwindcss')" "https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.6/tailwindcss-linux-${TAILWIND_ARCH}" && \
    chmod +x /usr/local/bin/tailwindcss && \
    tailwindcss -c ./tailwind.config.js -i ./app/static/css/tailwind-input.css -o ./app/static/css/tailwind.css --minify --content "./app/templates/**/*.html" && \
    rm -f /usr/local/bin/tailwindcss

# Exponer puerto
EXPOSE 8000

# Variables de entorno por defecto
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production
ENV PYTHONPATH=/app

# Entrypoint: ejecutar migraciones + uvicorn
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
