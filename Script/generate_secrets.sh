#!/bin/bash
# =============================================================================
# BarracaPedidos - Generador de Secrets para Producción (Orange Pi 5 Plus)
# =============================================================================
# Uso:
#   ./Script/generate_secrets.sh              # Genera y muestra secrets
#   ./Script/generate_secrets.sh --save        # Genera y guarda en .env
#   ./Script/generate_secrets.sh --show        # Solo muestra los secrets
# =============================================================================
# Requiere: openssl, python3
# =============================================================================

set -uo pipefail

# --- Colores ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- Directorios ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# =============================================================================
# Generadores de secrets seguros
# =============================================================================

generate_pg_password() {
    openssl rand -base64 32 | tr -d '\n' | tr -d '=' | tr '+/' '-_'
}

generate_secret_key() {
    python3 -c "import secrets; print(secrets.token_urlsafe(64))"
}

generate_jwt_secret() {
    openssl rand -hex 32
}

# =============================================================================
# Mostrar secrets generados
# =============================================================================

print_secrets() {
    local pg_pass="$1"
    local secret_key="$2"
    local jwt_secret="$3"

    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}              🔐  SECRETOS GENERADOS 🔐  ${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}📦 POSTGRES_PASSWORD (32 chars, base64 safe):${NC}"
    echo "   $pg_pass"
    echo ""
    echo -e "${YELLOW}🔑 SECRET_KEY (JWT, 64 chars):${NC}"
    echo "   $secret_key"
    echo ""
    echo -e "${YELLOW}🛡️  JWT_SECRET (256 bits, hex):${NC}"
    echo "   $jwt_secret"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
}

# =============================================================================
# Generar archivo .env completo para producción
# =============================================================================

generate_prod_env() {
    local pg_pass="$1"
    local secret_key="$2"
    local jwt_secret="$3"
    local output_file="$PROJECT_ROOT/.env"

    cat > "$output_file" << EOF
# =============================================================================
# BarracaPedidos - Producción
# Generado: $(date)
# ⚠️  NUNCA COMMITEAR ESTE ARCHIVO
# =============================================================================

# --- Database ---
POSTGRES_USER=barraca_user
POSTGRES_PASSWORD=${pg_pass}
POSTGRES_DB=barraca

# --- Security ---
SECRET_KEY=${secret_key}

# --- App ---
APP_ENV=production
DEBUG=false
BASE_URL=https://pedidos-generales.loquinto.com

# --- JWT ---
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# --- Database Pool (Orange Pi 5 Plus tiene 8GB RAM) ---
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# --- Email (opcional) ---
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_USE_TLS=true
EOF

    echo -e "${GREEN}✅ .env generado en: ${output_file}${NC}"
    echo -e "${YELLOW}⚠️  RECORDÁ:${NC}"
    echo "   1. Guardá estos secrets en un password manager"
    echo "   2. Nunca subas .env a Git"
    echo "   3. En producción, la DB está en 5445 (solo accesible internamente)"
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    local mode="${1:-show}"

    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║   BarracaPedidos - Generador de Secrets para Orange Pi  ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    # Verificar dependencias
    if ! command -v openssl &> /dev/null; then
        echo -e "${RED}❌ Error: openssl no instalado${NC}"
        echo "   sudo apt install openssl"
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Error: python3 no instalado${NC}"
        exit 1
    fi

    # Generar secrets
    PG_PASSWORD=$(generate_pg_password)
    SECRET_KEY=$(generate_secret_key)
    JWT_SECRET=$(generate_jwt_secret)

    case "$mode" in
        --save|save)
            print_secrets "$PG_PASSWORD" "$SECRET_KEY" "$JWT_SECRET"
            echo ""
            echo -e "${YELLOW}Generando .env en el proyecto...${NC}"
            generate_prod_env "$PG_PASSWORD" "$SECRET_KEY" "$JWT_SECRET"
            echo ""
            echo -e "${GREEN}✓ Listo para usar docker-compose -f docker-compose.prod.yml up -d${NC}"
            ;;
        --show|show)
            print_secrets "$PG_PASSWORD" "$SECRET_KEY" "$JWT_SECRET"
            echo ""
            echo -e "${BLUE}💡 Para guardar en .env: ./Script/generate_secrets.sh --save${NC}"
            ;;
        --help|-h)
            echo "Uso: $0 [--save|--show|--help]"
            echo ""
            echo "  (sin args)   Muestra los secrets generados"
            echo "  --save       Genera y guarda en .env del proyecto"
            echo "  --show       Solo muestra los secrets (igual que sin args)"
            echo "  --help       Muestra esta ayuda"
            ;;
        *)
            echo -e "${RED}Argumento desconocido: $mode${NC}"
            echo "Usa --help para ver las opciones."
            exit 1
            ;;
    esac
}

main "$@"