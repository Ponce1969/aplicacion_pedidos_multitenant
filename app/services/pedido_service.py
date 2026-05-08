from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Pedido, PedidoItem
from app.repositories import pedido_repo, producto_repo, entrega_repo, cliente_repo
from app.repositories.producto_repo import InsufficientStockError

# Estados válidos del pedido (flujo de entrega)
VALID_ESTADOS = {"pendiente", "asignado", "en_camino", "entregado", "no_entregado", "cancelado"}

# Transiciones de estado permitidas
TRANSICIONES_ESTADO: dict[str, set[str]] = {
    "pendiente": {"asignado", "cancelado"},
    "asignado": {"en_camino", "pendiente", "cancelado"},
    "en_camino": {"entregado", "no_entregado", "cancelado"},
    "no_entregado": {"pendiente", "cancelado"},  # Reintento
    "entregado": set(),  # Estado final
    "cancelado": set(),  # Estado final
}


class InvalidEstadoTransition(Exception):
    """Error cuando la transición de estado no es válida."""

    def __init__(self, estado_actual: str, estado_nuevo: str) -> None:
        self.estado_actual = estado_actual
        self.estado_nuevo = estado_nuevo
        super().__init__(
            f"Transición inválida: '{estado_actual}' → '{estado_nuevo}'. "
            f"Transiciones permitidas desde '{estado_actual}': {TRANSICIONES_ESTADO.get(estado_actual, set())}"
        )


async def crear_pedido(db: AsyncSession, pedido: Pedido) -> Pedido:
    """Crea un pedido nuevo en la BD."""
    return await pedido_repo.create(db, pedido)


async def crear_pedido_con_items(
    db: AsyncSession, pedido: Pedido, items: list[dict[str, float | int | str]],
) -> Pedido:
    """Crea un pedido con sus líneas de items.
    
    Calcula el total automáticamente y descuenta stock de cada producto.
    Si el pedido tiene cliente y no está pagado completamente, verifica
    el límite de crédito y actualiza el saldo_pendiente del cliente.
    
    El descuento es atómico: si algún producto no tiene stock suficiente
    o se excede el límite de crédito, no se descuenta ninguno.
    
    Stock None = sin control de stock (no se valida ni descuenta).
    """
    # Fase 1: Validar stock de todos los items ANTES de crear nada
    productos_para_descontar: list[tuple[int, Decimal]] = []  # (producto_id, cantidad_a_descontar)
    
    for item_data in items:
        cantidad = Decimal(str(item_data.get("cantidad", 1)))
        producto_id = item_data.get("producto_id")
        
        if producto_id is None:
            continue  # Línea manual sin producto asociado
        
        producto = await producto_repo.get_by_id(db, int(producto_id), pedido.empresa_id)
        if producto is None:
            continue  # Producto no encontrado, se omite (línea manual con ID inválido)
        
        # Solo validar si el producto tiene control de stock (stock != None)
        if producto.stock is not None:
            if producto.stock < cantidad:
                raise InsufficientStockError(
                    producto.nombre, producto.stock, cantidad
                )
            productos_para_descontar.append((int(producto_id), cantidad))
    
    # Fase 2: Calcular totales y crear items
    subtotal = Decimal("0")
    for item_data in items:
        cantidad = Decimal(str(item_data.get("cantidad", 1)))
        precio = Decimal(str(item_data.get("precio_unitario", 0)))
        item_subtotal = cantidad * precio
        subtotal += item_subtotal

        item = PedidoItem(
            descripcion=item_data["descripcion"],
            cantidad=cantidad,
            precio_unitario=precio,
            subtotal=item_subtotal,
            producto_id=item_data.get("producto_id"),
        )
        pedido.items.append(item)

    pedido.subtotal = subtotal
    pedido.total = subtotal + (pedido.impuestos or Decimal("0"))
    
    # Fase 2.5: Verificar límite de crédito si hay cliente y no está pagado
    if pedido.cliente_id and pedido.estado_pago != "pagado":
        deuda_pedido = pedido.total - (pedido.senia or Decimal("0"))
        if deuda_pedido > 0:
            await cliente_repo.verificar_limite_credito(
                db, pedido.cliente_id, pedido.empresa_id, deuda_pedido
            )
    
    # Fase 3: Descontar stock de cada producto (ya validamos que hay suficiente)
    for producto_id, cantidad in productos_para_descontar:
        producto = await producto_repo.get_by_id(db, producto_id, pedido.empresa_id)
        if producto and producto.stock is not None:
            producto.stock = producto.stock - cantidad
    
    # Fase 4: Persistir todo en una sola transacción
    saved = await pedido_repo.create(db, pedido)
    
    # Fase 5: Actualizar saldo_pendiente del cliente (después de persistir)
    if saved.cliente_id and saved.estado_pago != "pagado":
        deuda = saved.total - (saved.senia or Decimal("0"))
        if deuda > 0:
            await cliente_repo.agregar_deuda(
                db, saved.cliente_id, saved.empresa_id, deuda
            )
    
    return saved


async def actualizar_items_pedido(
    db: AsyncSession,
    pedido_id: int,
    empresa_id: int,
    nuevos_items: list[dict[str, float | int | str]],
) -> Pedido | None:
    """Reemplaza los items de un pedido existente, ajustando stock y total.

    Estrategia segura y atómica:
    1. Restaurar stock de todos los items actuales
    2. Eliminar los items actuales
    3. Validar stock para los nuevos items
    4. Crear los nuevos items y descontar stock
    5. Recalcular total y actualizar saldo pendiente del cliente

    Si algún item no tiene stock suficiente, NO se modifica nada (rollback automático).

    Args:
        db: Sesión de base de datos async
        pedido_id: ID del pedido a actualizar
        empresa_id: ID de la empresa (del JWT)
        nuevos_items: Lista de dicts con descripcion, cantidad, precio_unitario, producto_id

    Returns:
        Pedido actualizado o None si no se encuentra
    """
    pedido = await pedido_repo.get_by_id(db, pedido_id, empresa_id)
    if pedido is None:
        return None

    # Calcular saldo pendiente anterior para ajustar luego
    saldo_anterior = pedido.total - (pedido.senia or Decimal("0"))

    # Fase 1: Restaurar stock de todos los items actuales
    for item in pedido.items:
        if item.producto_id is not None:
            producto = await producto_repo.get_by_id(db, item.producto_id, empresa_id)
            if producto and producto.stock is not None:
                producto.stock = producto.stock + item.cantidad

    # Fase 2: Validar stock de todos los nuevos items ANTES de crear nada
    productos_para_descontar: list[tuple[int, Decimal]] = []
    for item_data in nuevos_items:
        cantidad = Decimal(str(item_data.get("cantidad", 1)))
        producto_id = item_data.get("producto_id")
        if producto_id is None:
            continue
        producto = await producto_repo.get_by_id(db, int(producto_id), empresa_id)
        if producto is None:
            continue
        if producto.stock is not None:
            if producto.stock < cantidad:
                # Rollback: restaurar stock de los items que ya descontamos
                # (SQLAlchemy session maneja el rollback automático si falla)
                raise InsufficientStockError(producto.nombre, producto.stock, cantidad)
            productos_para_descontar.append((int(producto_id), cantidad))

    # Fase 3: Eliminar items actuales y crear los nuevos
    for item in list(pedido.items):
        await db.delete(item)
    pedido.items.clear()

    subtotal = Decimal("0")
    for item_data in nuevos_items:
        cantidad = Decimal(str(item_data.get("cantidad", 1)))
        precio = Decimal(str(item_data.get("precio_unitario", 0)))
        item_subtotal = cantidad * precio
        subtotal += item_subtotal

        item = PedidoItem(
            descripcion=item_data["descripcion"],
            cantidad=cantidad,
            precio_unitario=precio,
            subtotal=item_subtotal,
            producto_id=item_data.get("producto_id"),
        )
        pedido.items.append(item)

    pedido.subtotal = subtotal
    pedido.total = subtotal + (pedido.impuestos or Decimal("0"))

    # Fase 4: Descontar stock de los nuevos items
    for producto_id, cantidad in productos_para_descontar:
        producto = await producto_repo.get_by_id(db, producto_id, empresa_id)
        if producto and producto.stock is not None:
            producto.stock = producto.stock - cantidad

    await db.flush()

    # Fase 5: Ajustar saldo_pendiente del cliente si aplica
    if pedido.cliente_id:
        nuevo_saldo = pedido.total - (pedido.senia or Decimal("0"))
        # Reemplazar saldo anterior por el nuevo
        ajuste = nuevo_saldo - saldo_anterior
        if ajuste != Decimal("0"):
            cliente = await cliente_repo.get_by_id(db, pedido.cliente_id, empresa_id)
            if cliente:
                cliente.saldo_pendiente = (cliente.saldo_pendiente or Decimal("0")) + ajuste

    await db.commit()
    await db.refresh(pedido)
    return pedido


async def cancelar_pedido(db: AsyncSession, pedido_id: int, empresa_id: int) -> Pedido | None:
    """Cancela un pedido y restaura el stock de cada producto."""
    pedido = await pedido_repo.get_by_id(db, pedido_id, empresa_id)
    if pedido is None:
        return None
    
    # Restaurar stock de cada item
    for item in pedido.items:
        if item.producto_id is not None:
            producto = await producto_repo.get_by_id(db, item.producto_id, empresa_id)
            if producto and producto.stock is not None:
                producto.stock = producto.stock + item.cantidad
    
    pedido.estado = "cancelado"
    await db.commit()
    await db.refresh(pedido)
    return pedido


async def buscar_pedidos(db: AsyncSession, termino: str, empresa_id: int) -> list[Pedido]:
    """Busca pedidos por celular o apellido."""
    return await pedido_repo.search_by_celular_or_apellido(db, termino, empresa_id)


async def get_pedido(db: AsyncSession, pedido_id: int, empresa_id: int) -> Pedido | None:
    """Obtiene un pedido por ID verificando empresa_id."""
    return await pedido_repo.get_by_id(db, pedido_id, empresa_id)


async def get_pedido_by_id(db: AsyncSession, pedido_id: int, empresa_id: int) -> Pedido | None:
    """Obtiene un pedido por ID verificando que pertenezca a la empresa."""
    return await pedido_repo.get_by_id(db, pedido_id, empresa_id)


def calcular_top_productos(pedidos: list[Pedido]) -> list[tuple[str, float]]:
    """Parsea pedido_detalle (legacy) para obtener productos más vendidos."""
    productos_vendidos: dict[str, float] = {}
    for pedido in pedidos:
        try:
            lineas: list[str] = pedido.pedido_detalle.split("\n")
            for linea in lineas:
                if "-" in linea:
                    partes: list[str] = linea.split("-", 1)
                    nombre_prod: str = partes[0].strip()
                    try:
                        cantidad_str = partes[1].strip().replace("kg", "").replace("unidad", "").strip()
                        cantidad: float = float(cantidad_str)
                    except (ValueError, IndexError):
                        cantidad = 1.0
                    productos_vendidos[nombre_prod] = productos_vendidos.get(nombre_prod, 0.0) + cantidad
        except (AttributeError, ValueError):
            pass

    return sorted(productos_vendidos.items(), key=lambda x: x[1], reverse=True)[:5]


def calcular_kpis_mes(pedidos: list[Pedido]) -> tuple[float, int]:
    """Calcula total_ventas y cantidad_pedidos de una lista de pedidos."""
    total_ventas = sum(float(pedido.total) for pedido in pedidos)
    cantidad = len(pedidos)
    return total_ventas, cantidad


async def get_pedidos_mes(db: AsyncSession, empresa_id: int) -> list[Pedido]:
    """Obtiene los pedidos del mes actual."""
    hoy: date = datetime.now(UTC).date()
    primer_dia_mes: date = hoy.replace(day=1)
    return await pedido_repo.get_by_month(db, primer_dia_mes, empresa_id)


async def get_pedidos_pendientes(
    db: AsyncSession, empresa_id: int, fecha: date | None = None,
) -> list[Pedido]:
    """Obtiene pedidos pendientes para armado de entregas."""
    return await pedido_repo.get_pending_by_empresa(db, empresa_id, fecha)


async def delete_pedido(db: AsyncSession, pedido_id: int, empresa_id: int) -> bool:
    """Elimina un pedido si pertenece a la empresa del usuario."""
    return await pedido_repo.delete_pedido(db, pedido_id, empresa_id)


async def update_pedido(
    db: AsyncSession, pedido_id: int, empresa_id: int, datos: dict[str, float | int | str | None],
) -> Pedido | None:
    """Actualiza campos de un pedido existente."""
    pedido = await pedido_repo.get_by_id(db, pedido_id, empresa_id)
    if pedido is None:
        return None

    for campo, valor in datos.items():
        if hasattr(pedido, campo) and campo not in ("id", "empresa_id", "fecha_creacion"):
            setattr(pedido, campo, valor)

    await db.commit()
    await db.refresh(pedido)
    return pedido


async def asignar_repartidor(
    db: AsyncSession,
    pedido_id: int,
    repartidor_id: int,
    usuario_id: int,
    empresa_id: int,
) -> Pedido | None:
    """Asigna un repartidor a un pedido y registra el evento."""
    pedido = await pedido_repo.get_by_id(db, pedido_id, empresa_id)
    if pedido is None:
        return None

    estado_anterior = pedido.estado
    pedido.repartidor_id = repartidor_id

    # Si el pedido está pendiente, cambiar a asignado
    if pedido.estado == "pendiente":
        pedido.estado = "asignado"

    await entrega_repo.create(
        db,
        pedido_id=pedido_id,
        usuario_id=usuario_id,
        empresa_id=empresa_id,
        estado_anterior=estado_anterior,
        estado_nuevo=pedido.estado,
        nota=f"Repartidor #{repartidor_id} asignado",
    )

    await db.commit()
    await db.refresh(pedido)
    return pedido


async def cambiar_estado_entrega(
    db: AsyncSession,
    pedido_id: int,
    nuevo_estado: str,
    usuario_id: int,
    empresa_id: int,
    nota: str | None = None,
) -> Pedido:
    """Cambia el estado de un pedido validando las transiciones permitidas.
    
    Si el nuevo estado es 'en_camino' o 'entregado' y el cliente tiene email,
    envía una notificación por email (best-effort, no bloquea el cambio).
    
    Raises:
        InvalidEstadoTransition: Si la transición no es válida.
    """
    pedido = await pedido_repo.get_by_id(db, pedido_id, empresa_id)
    if pedido is None:
        raise InvalidEstadoTransition("desconocido", nuevo_estado)

    estado_actual = pedido.estado

    # Validar que el nuevo estado sea válido
    if nuevo_estado not in VALID_ESTADOS:
        raise InvalidEstadoTransition(estado_actual, nuevo_estado)

    # Validar transición
    transiciones_permitidas = TRANSICIONES_ESTADO.get(estado_actual, set())
    if nuevo_estado not in transiciones_permitidas:
        raise InvalidEstadoTransition(estado_actual, nuevo_estado)

    # Cambiar estado
    pedido.estado = nuevo_estado

    # Registrar evento
    await entrega_repo.create(
        db,
        pedido_id=pedido_id,
        usuario_id=usuario_id,
        empresa_id=empresa_id,
        estado_anterior=estado_actual,
        estado_nuevo=nuevo_estado,
        nota=nota,
    )

    await db.commit()
    await db.refresh(pedido)

    # Notificar al cliente por email (best-effort)
    if nuevo_estado in ("en_camino", "entregado") and pedido.cliente_id:
        await _notificar_cambio_estado(db, pedido, nuevo_estado, empresa_id)

    return pedido


async def _notificar_cambio_estado(
    db: AsyncSession,
    pedido: Pedido,
    nuevo_estado: str,
    empresa_id: int,
) -> None:
    """Envía email de notificación al cliente (best-effort, nunca lanza excepción)."""
    from app.repositories import usuario_repo as usuario_repo_mod
    from app.schemas import EmailTemplateData
    from app.services.email_service import EmailService

    try:
        # Obtener cliente
        from app.models import Cliente, Empresa
        from sqlalchemy import select

        cliente_result = await db.execute(select(Cliente).where(Cliente.id == pedido.cliente_id))
        cliente = cliente_result.scalar_one_or_none()
        if not cliente or not cliente.email:
            return

        # Obtener empresa
        empresa_result = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
        empresa = empresa_result.scalar_one_or_none()
        if not empresa:
            return

        # Preparar datos del template
        items_data = [
            {
                "cantidad": float(item.cantidad),
                "descripcion": item.descripcion,
                "precio_unitario": float(item.precio_unitario),
            }
            for item in pedido.items
        ]

        template_data = EmailTemplateData(
            empresa_nombre=empresa.nombre,
            empresa_logo=empresa.logo_url,
            empresa_color=empresa.color_primario or "#3b82f6",
            email_contacto=empresa.email_contacto,
            telefono_contacto=empresa.telefono_contacto,
            cliente_nombre=f"{cliente.nombre} {cliente.apellido}",
            cliente_email=cliente.email,
            pedido_id=pedido.id,
            pedido_estado=nuevo_estado,
            pedido_total=float(pedido.total) if pedido.total else None,
            pedido_senia=float(pedido.senia) if pedido.senia else None,
            pedido_saldo=float(pedido.total - (pedido.senia or 0)) if pedido.total else None,
            items=items_data,
            fecha_entrega=pedido.fecha_entrega.strftime("%d/%m/%Y") if pedido.fecha_entrega else None,
            hora_entrega=pedido.hora_entrega,
        )

        email_service = EmailService()
        await email_service.send_pedido_update(template_data)

    except Exception:
        logger.exception("Error enviando notificación de email para pedido #%s", pedido.id)


async def get_pedidos_asignados_repartidor(
    db: AsyncSession,
    repartidor_id: int,
    empresa_id: int,
) -> list[Pedido]:
    """Obtiene los pedidos asignados a un repartidor (no cancelados ni entregados)."""
    return await pedido_repo.get_asignados_by_repartidor(db, repartidor_id, empresa_id)
