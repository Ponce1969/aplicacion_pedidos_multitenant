# 🏗️ BarracaPedidos — Sistema Multi-Tenant de Gestión de Pedidos

Sistema de pedidos multi-tenant para barracas y ferreterías con entregas a domicilio.

## Stack

- **Backend**: FastAPI + SQLAlchemy (async) + PostgreSQL
- **Auth**: JWT + Argon2
- **Frontend**: HTMX + Tailwind CSS (CDN)
- **DB Migrations**: Alembic
- **Container**: Docker + Docker Compose

## Quick Start (Docker)

```bash
cd barraca_pedidos
cp .env.example .env
docker-compose up -d
```

La app queda disponible en `http://localhost:8000`

## Onboarding

Primera vez que levantás el sistema, necesitás registrar tu empresa:

```bash
curl -X POST http://localhost:8000/api/onboarding/register \
  -H "Content-Type: application/json" \
  -d '{
    "empresa_nombre": "Mi Barraca",
    "empresa_rut": "12345678-9",
    "email": "admin@tu-barraca.com",
    "password": "TuPassword123!"
  }'
```

Esto crea: Empresa + Usuario Admin + Cliente "Consumidor Final" (TX atómica).

Después usás ese email y password en el login.

## Endpoints Principales

| Ruta | Descripción |
|------|-------------|
| `GET /login` | Login |
| `POST /api/login` | Iniciar sesión |
| `GET /dashboard` | KPIs del mes, últimos pedidos |
| `GET /nuevo-pedido` | Formulario nuevo pedido |
| `GET /pedidos` | Listado de pedidos |
| `GET /pedido/{id}` | Ver detalle |
| `GET /buscar` | Búsqueda por celular o apellido |
| `GET /admin/usuarios` | Gestión de usuarios (admin) |
| `GET /admin/configuracion` | Config visual de empresa |

## Seguridad Multi-Tenant

- **Aislamiento por `empresa_id`**: Todo query filtra por empresa
- **JWT con `empresa_id` en claims**: El token lleva el contexto del tenant
- **Rate limiting**: Login y onboarding tienen límites por IP

## Variables de Entorno (.env)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | (requerido) | `postgresql+asyncpg://user:pass@host/db` |
| `SECRET_KEY` | (requerido) | Min 32 caracteres |
| `APP_ENV` | `development` | `development` o `production` |
| `POSTGRES_USER` | `barraca_user` | Usuario PostgreSQL |
| `POSTGRES_PASSWORD` | `barraca_dev_2024` | Contraseña PostgreSQL |
| `POSTGRES_DB` | `barraca` | Nombre base de datos |

## Desarrollo Local (sin Docker)

```bash
cd barraca_pedidos
uv venv
source .venv/Scripts/activate  # Windows
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Tests

```bash
uv run pytest tests/ -v
```

## Deploy (Orange Pi 5 Plus)

```bash
# En la Orange Pi
cd barraca_pedidos
docker-compose up -d
```

La app optimizada para SQLite local. Para producción usar PostgreSQL y ajustar `DATABASE_POOL_SIZE` según memoria.

## Licencia

MIT