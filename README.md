# 🏗️ BarracaPedidos

**Sistema Multi-Tenant de Gestión de Pedidos para Barracas y Ferreterías**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=flat&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-24.0-2496ED?style=flat&logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-332%20Passing-00A000?style=flat&logo=pytest&logoColor=white)
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
- **Strict Typing**: MyPy strict mode, sin `Any`, sin `Optional` sin razón
- **Async I/O**: SQLAlchemy async + AsyncPG para alto rendimiento

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

### 🚚 Gestión de Entregas
Estado machine: `pendiente → asignado → en_camino → entregado / no_entregado`

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

**332 tests** cubriendo auth, pedidos, multi-tenant, CRUD completo.

---

## 📁 Estructura del Proyecto

```
barraca_pedidos/
├── app/
│   ├── api/
│   │   └── routers/
│   │       ├── auth.py          # Login, logout, refresh
│   │       ├── pedidos.py       # CRUD pedidos, búsqueda
│   │       ├── dashboard.py     # KPIs, stock bajo
│   │       ├── admin.py         # Gestión de usuarios
│   │       ├── configuracion.py # Config visual empresa
│   │       └── onboarding.py   # Registro público
│   ├── repositories/            # 🔷 Ports (acceso a datos)
│   │   ├── usuario_repo.py
│   │   ├── pedido_repo.py
│   │   ├── cliente_repo.py
│   │   ├── producto_repo.py
│   │   └── entrega_repo.py
│   ├── services/                # 🔷 Domain logic
│   │   ├── auth_service.py
│   │   ├── pedido_service.py
│   │   ├── configuracion_service.py
│   │   └── onboarding_service.py
│   ├── models.py                # SQLAlchemy models
│   ├── schemas.py               # Pydantic schemas
│   ├── auth.py                  # JWT utilities
│   ├── config.py                # Settings
│   ├── middlewares.py           # Auth middleware
│   ├── rate_limiter.py         # Token bucket por IP
│   ├── security_headers.py      # CSP headers
│   ├── templates/               # Jinja2 templates
│   └── main.py                  # FastAPI app
├── tests/                      # Test suite
├── alembic/                    # DB migrations
│   └── versions/
├── docker-compose.yml
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

---

## 🌐 Deploy (Orange Pi 5 Plus + Cloudflare Tunnel)

```
[Usuario] → Cloudflare Tunnel → [Frontend en Orange Pi]
                                    ↓
                             [Backend/API] (solo interno)
```

El backend queda protegido detrás del tunnel. Solo el frontend es accesible desde internet.

---

## 📄 Licencia

MIT — Uso libre para proyectos personales y comerciales.

---

**¿Dudas o Issues?** Abrí un ticket en GitHub. Las PRs son bienvenidas.