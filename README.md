# 🏗️ BarracaPedidos

**Sistema Multi-Tenant de Gestión de Pedidos para Barracas y Ferreterías**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=flat&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-24.0-2496ED?style=flat&logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-327%20Passed%20%2B%205%20Skipped-00A000?style=flat&logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

---

## 🎯 Problema que Resuelve

- **Desorganización de pedidos**: Centralizá todos los pedidos en una base de datos
- **Pérdida de información**: Cada pedido queda registrado con todos sus detalles
- **Control de entregas**: Registrá dirección, hora y fecha de entrega
- **Visibilidad de ventas**: Dashboard con ventas del mes y productos más vendidos

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENTE                              │
│                    (HTMX + Tailwind)                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────┐
│                       FASTAPI                                │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────┐ │
│  │   Auth     │  │  Pedidos   │  │ Dashboard  │  │  Admin  │ │
│  │  (JWT)     │  │   (CRUD)   │  │ (Analytics)│  │(Config) │ │
│  └────────────┘  └────────────┘  └────────────┘  └─────────┘ │
│                                                              │
│  ─────────────────────────────────────────────────────────── │
│  🔷 Hexagonal Architecture / Ports & Adapters                │
│  🔷 Strict Typing (Pyright + Mypy strict mode)               │
│  ─────────────────────────────────────────────────────────── │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              SQLAlchemy Async + Alembic                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                     PostgreSQL 16                             │
│         (Multi-tenant isolation por empresa_id)              │
└─────────────────────────────────────────────────────────────┘
```

**Principios técnicos:**
- **Hexagonal Architecture**: Servicios desacoplados del acceso a datos
- **CQRS**: Queries de lectura en `services/queries/` con SQL nativo, separadas de la lógica de escritura
- **Strict Typing**: MyPy strict mode, sin `Any`, sin `Optional` sin razón
- **Async I/O**: SQLAlchemy async + AsyncPG para alto rendimiento
- **HTMX Rules**: SIEMPRE `hx-include` para datos dinámicos, NUNCA `hx-vals="js:..."` (crash silencioso)

---

## ⚡ Stack Tecnológico

| Componente | Tecnología | Propósito |
|:-----------|:-----------|:----------|
| 🐍 **Backend** | FastAPI | API REST asíncrona |
| 🗄️ **Base de Datos** | PostgreSQL 16 | Datos persistentes |
| 🔐 **Auth** | JWT + Argon2 | Tokens y hashing seguro |
| 🎨 **Frontend** | HTMX + Tailwind | UI dinámica sin SPA |
| 📦 **Paquetes** | `uv` | Gestión ultra rápida |
| 🔄 **Migraciones** | Alembic | Control de esquemas |
| 🐳 **Container** | Docker Compose | Entorno reproducible |

---

## ✨ Features Principales

### 🔒 Aislamiento Multi-Tenant
Todo query filtra por `empresa_id` en la capa de repositorio. No hay posibilidad de filtrar accidentalmente datos de otra empresa.

### ⚡ Onboarding Atómico
Registro de empresa + usuario admin + cliente seed en una sola transacción. Si algo falla, rollback completo.

### 🎨 Branding Dinámico
Cada empresa tiene su propio color primario, logo y datos de contacto. El CSS se genera dinámicamente desde la config.

### 📊 Dashboard
- Total vendido del mes
- Cantidad de pedidos
- Top 5 productos más vendidos
- Últimos 10 pedidos

### 🚚 Gestión de Entregas (Con State Machine)
Flujo completo de entregas con máquina de estados estricta:

```
pendiente ──→ asignado ──→ en_camino ──→ entregado ✔
   │              │            │               ✘
   │              │            └──→ no_entregado ──→ pendiente (reintento)
   │              │
   └──→ cancelado (estado final)  ←─── cualquier estado
```

- **Roles**: `owner`, `admin`, `vendedor`, `repartidor` — cada rol ve y hace lo que le corresponde
- **Vista Fleteros** (`/mis-entregas`): Mobile-first con tarjetas, `tel:` para llamar, Google Maps, botones Entregado/No Entregado con HTMX
- **Vista Admin** (`/entregas`): Filtro por fecha, badges de estado dinámicos, tel: y Maps links
- **Auditoría**: Cada transición genera un `EntregaEvento` con estado anterior, nuevo, usuario, nota y timestamp
- **Notificación dual**: Al confirmar entrega se envía email al cliente (si tiene) Y a la empresa
- **Reintentos**: `no_entregado → pendiente` permite reprogramar entregas fallidas
- **Post-login inteligente**: `repartidor` → `/mis-entregas`, `vendedor` → `/nuevo-pedido`, `admin/owner` → `/dashboard`

### 📦 Smart Ingestion JIT (Productos Automáticos)
Cuando un vendedor escribe un producto que no está en el catálogo, el sistema lo crea automáticamente:
- Se marca como `es_automatico=True` (badge `AUTO` en la interfaz)
- Uniqueness: `LOWER(BTRIM(nombre)) + empresa_id` (case-insensitive, trim)
- `INITCAP` normalization: "cemento portland" → "Cemento Portland"
- Auto-promote: al editar un producto AUTO desde Admin, pasa a manual (`es_automatico=False`)
- "Agregar como nuevo" button en la búsqueda cuando un JIT match no es lo que se busca

### 🔍 Búsqueda Híbrida de Productos
CTE SQL que une catálogo e historial de pedidos:
- ⭐ Productos frecuentes (del catálogo del cliente)
- 📦 Productos del catálogo general
- Precio pactado (`ultimo_precio_pactado`) si el cliente ya compró ese producto antes
- Badge AUTO para productos creados automáticamente
- Filtros por cliente (`cliente_id`) vía HTMX (`hx-include`, NUNCA `hx-vals="js:..."`)

### 👥 Módulo Admin Completo
Tab UI con:
- **Usuarios**: CRUD completo (crear, editar, desactivar, reset password) con roles `owner/admin/vendedor/repartidor`
- **Productos**: Alta, edición, desactivación, búsqueda, CSV export, auto-promote JIT
- **Empresa**: Datos, logo, color, RUT, dirección, contacto

### 🧾 Numeración Secuencial por Tenant
`numero_pedido` secuencial por `empresa_id` (no global). Backfill con `ROW_NUMBER()`. UniqueConstraint `(empresa_id, numero_pedido)`.

### 🔐 Validación de RUT Uruguayo
Algoritmo DGI con pesos izquierda→derecha `[4,3,2,9,8,7,6,5,4,3,2]`. Normalización a 12 dígitos.

### 💡 CQRS para Queries de Lectura
Servicios de query nativos (`app/services/queries/`) con SQL directo via `sqlalchemy.text()`, separados de la lógica de escritura. DTOs en `app/schemas/queries/`.

---

## 🚀 Quick Start

### 1. Clonar y entrar

```bash
git clone https://github.com/Ponce1969/aplicacion_pedidos_multitenant.git
cd aplicacion_pedidos_multitenant/barraca_pedidos
```

### 2. Configurar entorno

```bash
cp .env.example .env
# Editar .env con DATABASE_URL y SECRET_KEY
```

### 3. Levantar con Docker

```bash
docker-compose up -d
```

La app queda disponible en `http://localhost:8000`

### 4. Registrar primera empresa

```bash
curl -X POST http://localhost:8000/api/onboarding/register \
  -H "Content-Type: application/json" \
  -d '{
    "nombre_empresa": "Mi Barraca",
    "empresa_rut": "12345678-9",
    "email_admin": "admin@barraca.com",
    "nombre_admin": "Admin",
    "apellido_admin": "Principal",
    "password": "TuPassword123!"
  }'
```

Esto crea: **Empresa + Admin + Cliente "Consumidor Final"** en TX atómica.

---

## 🛠️ Desarrollo Local (sin Docker)

```bash
# Crear venv con uv
uv venv
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate      # Linux/Mac

# Instalar deps
uv sync

# Migraciones
uv run alembic upgrade head

# Correr servidor
uv run uvicorn app.main:app --reload
```

---

## 🧪 Tests

```bash
uv run pytest tests/ -v
```

**327 tests passed, 5 skipped** (producto search CTE uses PostgreSQL-specific syntax, skipped on SQLite).

---

## 📁 Estructura del Proyecto

```
barraca_pedidos/
├── app/
│   ├── api/
│   │   └── routers/
│   │       ├── auth.py          # Login, logout, refresh, post-login redirect por rol
│   │       ├── pedidos.py       # CRUD pedidos, entrega state machine, búsqueda
│   │       ├── dashboard.py     # KPIs, stock bajo
│   │       ├── admin.py         # Tab UI: usuarios, productos, empresa
│   │       ├── configuracion.py # Config visual empresa
│   │       └── onboarding.py   # Registro público (atomic TX)
│   ├── repositories/            # 🔷 Ports (acceso a datos)
│   │   ├── usuario_repo.py
│   │   ├── pedido_repo.py
│   │   ├── cliente_repo.py
│   │   ├── producto_repo.py
│   │   └── entrega_repo.py
│   ├── services/                # 🔷 Domain logic (escritura)
│   │   ├── auth_service.py
│   │   ├── pedido_service.py    # cambiar_estado_entrega(), state machine
│   │   ├── producto_service.py  # find_or_create_producto() JIT
│   │   ├── email_service.py     # Resend API, notificación dual
│   │   ├── configuracion_service.py
│   │   └── onboarding_service.py
│   ├── services/queries/        # 🔷 CQRS read services (SQL nativo)
│   │   ├── producto_search_service.py  # CTE híbrida catálogo + historial
│   │   └── cliente_insights_service.py
│   ├── schemas/queries/         # 🔷 CQRS DTOs
│   │   ├── producto_search.py
│   │   └── cliente_insights.py
│   ├── models.py                # SQLAlchemy models + state machine constants
│   ├── schemas/                 # Pydantic schemas
│   ├── auth.py                  # JWT utilities + require_role()
│   ├── config.py                # Settings
│   ├── csrf.py                  # Pure ASGI CSRF middleware
│   ├── middlewares.py           # Auth middleware
│   ├── rate_limiter.py          # Token bucket por IP
│   ├── security_headers.py      # CSP, no-cache headers (Pure ASGI)
│   ├── templates/               # Jinja2 templates
│   │   ├── mis_entregas.html   # Mobile-first repartidor view
│   │   ├── entregas.html        # Admin delivery view
│   │   ├── nuevo_pedido.html   # Con búsqueda híbrida JIT
│   │   ├── editar_pedido.html   # Con dynamic items + stock
│   │   ├── admin/              # Tab UI
│   │   └── partials/            # HTMX partials
│   └── main.py                  # FastAPI app
├── tests/                      # 332 test cases (327 passing, 5 skipped)
├── alembic/                    # DB migrations (13 migrations)
│   └── versions/
├── docker-compose.yml
├── docker-compose.prod.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## 📐 Guía de Estilo

- **Linting + Formateo**: Ruff (configurado en `pyproject.toml`)
- **Tipado**: MyPy strict mode — sin excusas
- **Imports**: Absolute imports, sin `from .module`
- **Naming**: `snake_case` archivos y funciones, `PascalCase` clases

---

## 🔑 Variables de Entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | *(requerido)* | `postgresql+asyncpg://...` |
| `SECRET_KEY` | *(requerido)* | Min 32 caracteres |
| `APP_ENV` | `development` | `development` o `production` |
| `DEBUG` | `false` | Logs detallados |
| `POSTGRES_USER` | `barraca_user` | Usuario PostgreSQL |
| `POSTGRES_PASSWORD` | `barraca_dev_2024` | Contraseña DB |
| `POSTGRES_DB` | `barraca` | Nombre de la base de datos |
| `RESEND_API_KEY` | *(opcional)* | API key para envío de emails (Resend) |
| `SWAGGER_PASSWORD` | *(opcional)* | Password para acceder a `/docs` en producción |

---

## 🚨 Deploy en Producción (Orange Pi 5 Plus)

```bash
# Build sin cache (el código se copia al image)
docker compose -f docker-compose.prod.yml build --no-cache app
docker compose -f docker-compose.prod.yml up -d

# Migraciones
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

> **Importante**: `up -d` solo NO rebuild. Usá siempre `build --no-cache app` antes del `up -d`.

El backend queda detrás de Cloudflare Tunnel en el puerto 8010 (nginx). HTTPS y cache son manejados por Cloudflare.

---

## 🌐 Deploy (Orange Pi 5 Plus + Cloudflare Tunnel)

```
[Usuario] → Cloudflare Tunnel → [Nginx :8010] → [FastAPI :8000]
                                         ↓
                                  [PostgreSQL :5445]
```

El backend queda protegido detrás del tunnel. Solo el frontend es accesible desde internet.

---

## 📄 Licencia

MIT — Uso libre para proyectos personales y comerciales.

---

**¿Dudas o Issues?** Abrí un ticket en GitHub. Las PRs son bienvenidas.