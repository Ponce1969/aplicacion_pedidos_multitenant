# Especificación de Arquitectura v2: Refactorización y Escalabilidad

## 1. Contexto y Motivación
La aplicación "BarracaPedidos" fue construida como un MVP funcional utilizando tecnologías modernas (FastAPI, SQLAlchemy 2.0 Async, HTMX, Tailwind). Sin embargo, el diseño inicial presenta acoplamiento de responsabilidades (monolito en `main.py`) y un modelo de datos desnormalizado (el detalle del pedido y los datos del cliente se guardan como texto libre en la tabla `Pedido`).

**Objetivo de la v2:** 
Transformar la aplicación en un sistema genérico de toma de pedidos (SaaS / Marca Blanca), agnóstico del rubro (sirve para barracas, fábricas de alfajores, pizzerías, etc.). Para lograr esto, el sistema debe ser altamente escalable, mantenible y estar estructurado en capas.

---

## 2. Nueva Estructura de Directorios (Clean Architecture)
Para separar responsabilidades (Transporte HTTP vs Lógica de Negocio vs Acceso a Datos), el proyecto adoptará la siguiente estructura:

```text
app/
├── api/
│   ├── routers/           # Endpoints de FastAPI (auth, pedidos, clientes, admin)
│   └── dependencies.py    # Dependencias de inyección (get_db, current_user)
├── services/              # Lógica de negocio (Cálculo de totales, validación de stock)
├── repositories/          # Lógica de acceso a datos (Queries de SQLAlchemy)
├── models/                # Definición de tablas de Base de Datos (SQLAlchemy)
├── schemas/               # Modelos de validación de datos (Pydantic)
├── templates/             # Vistas HTMX/Jinja2
├── core/                  # Configuraciones (config.py, security.py)
└── main.py                # Punto de entrada mínimo (solo inicializa FastAPI y monta routers)
```

**Reglas para Desarrolladores:**
1. **Routers**: Solo reciben la request, validan con schemas (Pydantic), llaman a un `Service` y devuelven la respuesta HTTP/HTML. NO DEBEN tener consultas SQL.
2. **Services**: Contienen el "Core" del negocio. Reciben datos limpios, aplican reglas y llaman a los `Repositories`.
3. **Repositories**: Los únicos que importan `sqlalchemy`. Reciben y devuelven instancias de `models`.

---

## 3. Evolución del Modelo de Datos (Relacional Normalizado)
Se abandonará el campo `pedido_detalle` (texto) a favor de un esquema normalizado:

*   **`Usuario`**: Empleados/Administradores del sistema (sin cambios).
*   **`Cliente` (NUEVO)**: Entidad separada (`nombre`, `apellido`, `celular`, `direccion`, `email_opcional`).
*   **`Producto` / `Articulo` (NUEVO)**: Catálogo (`sku`, `nombre`, `descripcion`, `precio_base`, `categoria_id`, `stock`).
*   **`Pedido` (ACTUALIZADO)**: Cabecera del pedido (`cliente_id`, `usuario_id`, `estado`, `fecha_entrega`, `subtotal`, `impuestos`, `total_final`).
*   **`PedidoItem` (NUEVO)**: Líneas del pedido (`pedido_id`, `producto_id`, `cantidad`, `precio_unitario`, `subtotal`).
*   **`Configuracion` (NUEVO)**: Permite Marca Blanca (`nombre_empresa`, `simbolo_moneda`, `rubro`, `zona_horaria`).

---

## 4. Hoja de Ruta (Roadmap de Refactorización)

La transición se realizará en las siguientes fases estrictas para no romper el sistema actual de golpe:

### Fase 1: Control de Infraestructura (Migraciones)
- Instalar e inicializar **Alembic**.
- Configurar entorno asíncrono para Alembic.
- Generar la migración inicial (`001_initial`) basada en el modelo de datos actual.
- *Meta: Capacidad de modificar tablas sin perder datos.*

### Fase 2: Desacoplamiento HTTP (Routers)
- Crear el directorio `app/api/routers/`.
- Mover las rutas de `main.py` a `auth.py`, `pedidos.py`, `dashboard.py`, `admin.py`.
- Registrar los routers en `main.py` usando `app.include_router()`.
- *Meta: `main.py` queda con menos de 50 líneas. Sin cambios en la base de datos.*

### Fase 3: Nuevo Modelo de Datos (DB)
- Crear las clases `Cliente`, `Producto` y `PedidoItem` en `app/models.py`.
- Modificar la clase `Pedido` para incluir llaves foráneas (`cliente_id`) y eliminar campos viejos.
- Generar migración con Alembic y aplicarla.
- Actualizar `app/schemas.py` para soportar las nuevas entidades.
- *Meta: Base de datos lista para soportar E-commerce genérico.*

### Fase 4: Capas de Negocio (Servicios y Repositorios)
- Crear `app/repositories/` y mover las consultas de SQLAlchemy allí.
- Crear `app/services/` para manejar la creación de pedidos (Ej: calcular el total sumando `PedidoItem`, verificar existencia del cliente).
- Actualizar los routers de la Fase 2 para usar los servicios en lugar de llamar a `db.execute()` directamente.
- *Meta: Arquitectura limpia y código testeable.*

### Fase 5: Actualización de Interfaz (UI/HTMX)
- Modificar `nuevo_pedido.html` para incluir:
  - Búsqueda/Autocompletado de Clientes existentes.
  - Agregado dinámico de líneas de productos (Buscador de productos del catálogo).
- Eliminar referencias hardcodeadas ("Barraca") y usar la tabla `Configuracion` o variables de entorno.
- *Meta: UI genérica, 100% funcional y adaptada al nuevo modelo de datos.*

---

## 5. Stack Tecnológico a Mantener
- **Backend:** Python 3.11+, FastAPI.
- **ORM:** SQLAlchemy 2.0 (Patrón AsyncSession + Mapped).
- **Frontend:** HTMX (AJAX declarativo) + Tailwind CSS (Estilos) + Jinja2 (SSR).
- **BD:** PostgreSQL (con driver asíncrono `asyncpg`).
- **Paquetería:** UV.
- **Despliegue:** Docker multi-stage + Docker Compose.
