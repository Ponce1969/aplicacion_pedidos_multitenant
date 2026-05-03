# Barraca Pedidos — Sistema Multi-Tenant de Gestión de Pedidos

Sistema de gestión de pedidos multi-tenant construido con FastAPI, SQLAlchemy (async) y SQLite.

## Características

### Módulos implementados

| Módulo | Descripción |
|--------|-------------|
| **M-01** | Onboarding de empresas — Registro público con TX atómica (Empresa + Admin + Cliente seed) |
| **M-02** | Repartidores — Estado machine (pendiente → asignado → en_camino → entregado) |
| **M-03** | Descuento stock — Atomico, solo si todos los items tienen stock suficiente |
| **M-04** | Auditoría — Tabla append-only `entrega_eventos` para tracking de estados |
| **M-05** | Múltiples direcciones — ClienteDireccion con principal/alternativas, snapshot en pedido |
| **M-06** | Unidades de medida — Campo `unidad_medida` en productos |
| **M-07** | Email notificaciones — Integración con Resend API para estados de pedido |
| **M-08** | Alerta stock bajo — Widget dashboard + página `/stock-bajo` |
| **M-12** | Cuenta corriente — Saldo pendiente, límite de crédito, registro de pagos |
| **M-21** | Configuración visual — Color primario, logo, datos de contacto por empresa |

### Seguridad multi-tenant

- **Aislamiento por `empresa_id`**: Todos los repos filtran explícitamente por empresa en cada query
- **get_by_id con filtro obligatorio**: `get_by_id(db, id, empresa_id)` — sin excepción
- **JWT con `empresa_id` en claims**: El token lleva el contexto del tenant
- **Rate limiting por IP**: Login, registro y onboarding tienen límites diferenciados

### Stack técnico

```
FastAPI + SQLAlchemy (async) + Alembic + SQLite
Pydantic v2 + python-dotenv
HTMX + Tailwind CSS (CDN)
Argon2 para hashing de contraseñas
JWT (python-jose) para auth
```

## Instalación

### 1. Clonar y crear entorno virtual

```bash
git clone https://github.com/Ponce1969/aplicacion_pedidos_multitenant.git
cd aplicacion_pedidos_multitenant/barraca_pedidos
uv venv
source .venv/Scripts/activate  # Windows
# o source .venv/bin/activate  # Linux/Mac
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con los valores deseados
```

**Variables requeridas en `.env`:**

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | URL de conexión a la base de datos |
| `SECRET_KEY` | Clave secreta para JWT (min 32 caracteres) |
| `RESEND_API_KEY` | API key de Resend para emails (opcional) |
| `SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD` | Configuración SMTP (opcional) |

### 3. Instalar dependencias

```bash
uv sync
```

### 4. Crear base de datos y ejecutar migraciones

```bash
uv run alembic upgrade head
```

### 5. Ejecutar el servidor

```bash
uv run uvicorn app.main:app --reload --port 8000
```

La aplicación estará disponible en `http://localhost:8000`

## Desarrollo

### Ejecutar tests

```bash
uv run pytest tests/ -v
```

### Estructura de directorios

```
barraca_pedidos/
├── app/
│   ├── api/
│   │   └── routers/          # Endpoints organizados por dominio
│   │       ├── auth.py       # Login, logout, refresh, password reset
│   │       ├── pedidos.py    # CRUD pedidos, búsqueda, filtrado
│   │       ├── dashboard.py   # KPIs, stock bajo, deudores
│   │       ├── admin.py      # Gestión de usuarios
│   │       ├── configuracion.py  # Config visual de empresa
│   │       └── onboarding.py # Registro público de empresas
│   ├── models.py             # Modelos SQLAlchemy
│   ├── repositories/         # Capa de acceso a datos
│   │   ├── cliente_repo.py
│   │   ├── pedido_repo.py
│   │   ├── producto_repo.py
│   │   ├── usuario_repo.py
│   │   ├── empresa_repo.py
│   │   └── entrega_repo.py
│   ├── services/             # Lógica de negocio
│   │   ├── auth_service.py
│   │   ├── pedido_service.py
│   │   ├── email_service.py
│   │   ├── configuracion_service.py
│   │   └── onboarding_service.py
│   ├── templates/           # Templates Jinja2
│   ├── static/              # CSS, JS estático
│   ├── auth.py              # JWT utilities, get_current_user
│   ├── config.py            # Settings de Pydantic
│   ├── rate_limiter.py      # Token bucket por IP
│   └── main.py              # FastAPI app + lifespan
├── tests/                   # Tests de integración
├── alembic/                 # Migraciones de BD
├── .env.example             # Template de variables de entorno
└── pyproject.toml           # Dependencias del proyecto
```

## Endpoints principales

### Auth (públicos)
- `GET /login` — Página de login
- `POST /api/login` — Iniciar sesión
- `POST /api/logout` — Cerrar sesión
- `POST /api/refresh-token` — Refrescar access token

### Onboarding (público)
- `POST /api/onboarding/register` — Registrar nueva empresa

### Pedidos (requiere auth)
- `GET /dashboard` — Dashboard con KPIs
- `GET /nuevo-pedido` — Formulario nuevo pedido
- `GET /pedidos` — Listado de pedidos
- `GET /pedido/{id}` — Ver detalle de pedido
- `GET /editar-pedido/{id}` — Editar pedido
- `POST /guardar-pedido` — Crear/actualizar pedido
- `POST /api/pedido/{id}/cancelar` — Cancelar pedido
- `POST /api/pedido/{id}/asignar` — Asignar repartidor
- `POST /api/pedido/{id}/estado` — Cambiar estado de entrega

### Admin (requiere auth + rol admin)
- `GET /admin/usuarios` — Listado de usuarios
- `POST /api/registro` — Crear nuevo usuario
- `GET /admin/configuracion` — Configuración visual de empresa
- `POST /admin/configuracion/actualizar` — Guardar configuración

### API JSON (requiere auth)
- `GET /api/pedidos/buscar?q=` — Buscar pedidos
- `GET /api/clientes/buscar?q=` — Buscar clientes
- `GET /api/productos/buscar?q=` — Buscar productos
- `GET /stock-bajo` — Página de stock bajo
- `GET /admin/configuracion/api/config` — Config como JSON

## Modelo de datos

### Empresa (tenant raíz)
- `nombre`, `slug`, `rubro`, `moneda`
- `logo_url`, `color_primario`, `email_contacto`, `telefono_contacto`
- `is_active`, `fecha_creacion`

### Usuario
- `empresa_id`, `email` (único por empresa), `nombre`, `apellido`
- `password_hash` (Argon2), `rol` (admin/operador/repartidor)
- `is_admin`, `is_active`, `ultimo_login`

### Cliente
- `empresa_id`, `nombre`, `apellido`, `celular` (único por empresa)
- `direccion`, `email`, `nota`
- `saldo_pendiente`, `limite_credito`
- `es_sistema_default` (para "Consumidor Final")
- Relaciones: pedidos, direcciones, pagos

### ClienteDireccion
- `cliente_id`, `empresa_id`, `descripcion`, `direccion`, `es_principal`

### Producto
- `empresa_id`, `sku` (único por empresa), `nombre`
- `precio_base`, `stock`, `stock_minimo`
- `unidad_medida`, `categoria`, `is_active`

### Pedido
- `empresa_id`, `usuario_id`, `cliente_id` (nullable)
- Campos legacy: `nombre`, `apellido`, `celular`, `direccion`, `hora_entrega`, `pedido_detalle`
- Campos nuevos: `subtotal`, `impuestos`, `total`, `senia`
- `estado_pago` (pendiente/parcial/pagado)
- `estado` (pendiente/asignado/en_camino/entregado/no_entregado/cancelado)
- `repartidor_id`, `fecha_entrega`

### Pago (append-only, auditoría)
- `cliente_id`, `empresa_id`, `pedido_id` (nullable)
- `monto`, `metodo_pago`, `nota`, `registrado_por`, `created_at`

### EntregaEvento (append-only, auditoría)
- `pedido_id`, `usuario_id`, `empresa_id`
- `estado_anterior`, `estado_nuevo`, `nota`, `created_at`

## Environment variables

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | (requerido) | `sqlite+aiosqlite:///:memory:` para tests |
| `SECRET_KEY` | `dev-secret...` | JWT signing key |
| `APP_ENV` | `development` | `development` o `production` |
| `DEBUG` | `false` | Activa logs detallados |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Duración del access token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Duración del refresh token |
| `RESEND_API_KEY` | `` | API key de Resend |
| `SMTP_HOST` | `smtp.gmail.com` | Servidor SMTP |
| `SMTP_PORT` | `587` | Puerto SMTP |
| `SMTP_USER` | `` | Usuario SMTP |
| `SMTP_PASSWORD` | `` | Contraseña SMTP |

## Deploy

### Requisitos
- Python 3.11+
- SQLite o PostgreSQL

### Pasos
1. Configurar `.env` con `APP_ENV=production` y `DEBUG=false`
2. Ejecutar migraciones: `uv run alembic upgrade head`
3. Iniciar con gunicorn/uvicorn:
   ```bash
   uv run gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
   ```

### Orange Pi 5 Plus
La aplicación está optimizada para correr en Orange Pi 5 Plus con SQLite local.
Configurar `DATABASE_URL=sqlite+aiosqlite:///./pedidos.db` y ajustar workers según memoria disponible.

## Licencia

MIT