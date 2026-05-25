# 🤖 AGENTS.md - Directrices de Desarrollo y Roles

Este archivo define el alcance, límites y jerarquía de permisos del sistema para guiar el desarrollo de agentes de IA sin alterar las reglas de negocio existentes.

## 1. Jerarquía Estricta de Roles

El sistema opera bajo un esquema multi-tenant donde los privilegios están blindados por rol. Al realizar modificaciones o refactorizaciones, se deben mantener estas reglas:

### 👑 Administrador / Owner (`admin`, `owner`)
- **Control Total:** Tiene control absoluto sobre su Tenant (`empresa_id`). Puede crear, editar y eliminar usuarios, productos y configuraciones.
- **Autogestión de Logística:** El Administrador debe gestionar su flota de fleteros y asignar pedidos desde el panel de administración HTML5 (Tab UI). **NUNCA** debe depender de llamadas externas (cURL/Swagger) ni intervención del programador para el alta de roles de logística.
- **Preservación de Privilegios:** Ninguna actualización de UI o backend puede remover, limitar o mitigar los accesos de gestión total del administrador.

### 🚚 Fletero / Repartidor (`repartidor`)
- **Alcance Limitado:** Únicamente tiene acceso a la vista mobile-first `/mis-entregas`.
- **Aislamiento de Datos:** Solo puede visualizar los pedidos específicos que le fueron asignados por el administrador de su respectiva barraca. No tiene visibilidad del catálogo, de otros fleteros ni del dashboard.
- **Acción Única:** Su única interacción permitida con el estado del pedido es accionar los botones de la State Machine (**Entregado** / **No Entregado**) vía HTMX. Al marcar como "Entregado", el pedido baja automáticamente de estado `pendiente`/`en_camino` a `entregado` de manera reactiva, impactando en el panel del administrador.
- **🚫 PROHIBIDO Resumen Acumulado para Fleteros (No Avivar Giles):** El fletero puede ver el total y la seña de CADA pedido individual (necesita cobrar al entregar). PERO la aplicación **NUNCA** debe mostrarle al fletero: totales acumulados, resúmenes diarios/semanales/mensuales, sumas de entregas por período, ni ningún tipo de reporte que facilite saber cuánto dinero movió en total. Esa información es exclusiva del Administrador/Owner. Si el fletero quiere saber cuánto entregó, que lo sume a mano — la app no se lo facilita.

## 2. Reglas Técnicas Críticas para el Agente

Cuando implementes o audites código en este proyecto, debés cumplir obligatoriamente con los siguientes estándares:

- **Clean/Hexagonal Architecture:** Mantener el desacoplamiento total. Los controladores (routers) llaman a servicios de dominio, y estos interactúan con los repositorios.
- **Strict Typing:** No usar `Any`. Respetar el tipado estricto verificado por Mypy/Pyright.
- **CQRS para Lecturas:** Las consultas de las vistas y tablas deben ir en `app/services/queries/` utilizando SQL nativo (`sqlalchemy.text()`).
- **Manejo de Dinero:** Todos los montos y costos de envío deben usar estrictamente el tipo `Decimal`, jamás `float`.
- **HTMX Rules:** Para enviar datos dinámicos a las vistas parciales, utilizar siempre `hx-include`. Queda terminantemente prohibido usar `hx-vals="js:...` debido a fallos silenciosos en el flujo.

## 3. Restricciones de Edición de Código (Anti-Corrupción)

- **PROHIBIDO EL USO DE REPLACE ALL:** El agente tiene terminantemente prohibido aplicar técnicas de reemplazo masivo o ciego (`Replace All`) en archivos de lógica compleja, rutas o modelos (como `admin.py`). Esto corrompe indentaciones, elimina endpoints hermanos y destruye código operativo.
- **Edición Quirúrgica y Contextual:** Toda modificación de código debe realizarse bloque por bloque, manteniendo el contexto único de la línea a modificar y asegurando que las líneas circundantes queden intactas.
- **Validación Post-Commit Obligatoria:** Antes de dar una tarea por finalizada o sugerir un despliegue, el agente debe verificar localmente que el conteo de líneas sea coherente (`(Get-Content archivo).Count`) y correr la suite de pruebas (`uv run pytest`) para garantizar que la refactorización no generó efectos colaterales dañinos.

- **PROHIBIDO EL USO DE HX-REFRESH PARA REPETIR CONFIGURACIONES DE ESTADO:** Queda prohibido forzar la recarga completa de la página (`HX-Refresh: true`) para actualizar cambios de estado en listas o tablas (ej. cambiar a 'Entregado'). 
- **Filosofía SPA con Partials:** Los endpoints que procesen acciones de HTMX deben retornar el partial correspondiente (o la fila/badge modificada) y usar el `hx-target` y `hx-swap` adecuados para actualizar la UI de manera reactiva y sin parpadeos.

- **SCRIPT DE AUDITORÍA DE RUTAS (`Script/audit_routes.py`):** El proyecto cuenta con una herramienta de ejecución estricta para detectar endpoints duplicados o enmascarados de FastAPI que rompan la reactividad de HTMX. Cada vez que el agente agregue, modifique o refactorice cualquier router en `app/api/routers/`, está **ESTRICTAMENTE OBLIGADO** a ejecutar el script desde la raíz del proyecto usando el entorno virtual:
  ```bash
  uv run python Script/audit_routes.py