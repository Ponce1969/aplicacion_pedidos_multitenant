from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Cliente, ClienteDireccion, Pago


async def get_by_id(db: AsyncSession, cliente_id: int, empresa_id: int) -> Cliente | None:
    """Obtiene un cliente por ID verificando que pertenezca a la empresa."""
    result = await db.execute(
        select(Cliente).where(Cliente.id == cliente_id, Cliente.empresa_id == empresa_id)
    )
    return result.scalar_one_or_none()


async def get_by_celular(db: AsyncSession, celular: str, empresa_id: int) -> Cliente | None:
    result = await db.execute(
        select(Cliente).where(Cliente.celular == celular, Cliente.empresa_id == empresa_id),
    )
    return result.scalar_one_or_none()


async def search(db: AsyncSession, termino: str, empresa_id: int) -> list[Cliente]:
    """Busca clientes por celular, CI, apellido, nombre o nombre completo."""
    from sqlalchemy import func

    query = (
        select(Cliente)
        .where(
            Cliente.empresa_id == empresa_id,
            (Cliente.celular.contains(termino))
            | (Cliente.ci.contains(termino))
            | (Cliente.apellido.ilike(f"%{termino}%"))
            | (Cliente.nombre.ilike(f"%{termino}%"))
            | (func.concat(Cliente.nombre, " ", Cliente.apellido).ilike(f"%{termino}%")),
        )
        .order_by(Cliente.apellido)
        .limit(20)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def create(db: AsyncSession, cliente: Cliente) -> Cliente:
    db.add(cliente)
    await db.commit()
    await db.refresh(cliente)
    return cliente


async def create_or_get_by_celular(db: AsyncSession, cliente: Cliente) -> Cliente:
    existing = await get_by_celular(db, cliente.celular, cliente.empresa_id)
    if existing is not None:
        return existing
    return await create(db, cliente)


# ==================== DIRECCIONES ====================


async def get_direcciones(db: AsyncSession, cliente_id: int, empresa_id: int) -> list[ClienteDireccion]:
    """Obtiene todas las direcciones de un cliente, principal primero."""
    query = (
        select(ClienteDireccion)
        .where(
            ClienteDireccion.cliente_id == cliente_id,
            ClienteDireccion.empresa_id == empresa_id,
        )
        .order_by(ClienteDireccion.es_principal.desc(), ClienteDireccion.created_at.asc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_direccion_principal(
    db: AsyncSession, cliente_id: int, empresa_id: int,
) -> ClienteDireccion | None:
    """Obtiene la dirección principal de un cliente."""
    query = select(ClienteDireccion).where(
        ClienteDireccion.cliente_id == cliente_id,
        ClienteDireccion.empresa_id == empresa_id,
        ClienteDireccion.es_principal == True,  # noqa: E712
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_direccion(db: AsyncSession, direccion: ClienteDireccion) -> ClienteDireccion:
    """Crea una nueva dirección para un cliente."""
    db.add(direccion)
    await db.commit()
    await db.refresh(direccion)
    return direccion


async def set_principal(db: AsyncSession, direccion_id: int, cliente_id: int, empresa_id: int) -> None:
    """Marca una dirección como principal y desmarca las demás."""
    # Desmarcar todas las direcciones del cliente
    direcciones = await get_direcciones(db, cliente_id, empresa_id)
    for d in direcciones:
        d.es_principal = (d.id == direccion_id)
    await db.commit()


# ==================== CUENTA CORRIENTE ====================


class LimiteCreditoExcedido(Exception):
    """Error cuando el pedido excede el límite de crédito del cliente."""

    def __init__(
        self,
        cliente_nombre: str,
        saldo_actual: Decimal,
        monto_pedido: Decimal,
        limite: Decimal,
    ) -> None:
        self.cliente_nombre = cliente_nombre
        self.saldo_actual = saldo_actual
        self.monto_pedido = monto_pedido
        self.limite = limite
        super().__init__(
            f"Límite de crédito excedido para '{cliente_nombre}': "
            f"saldo actual ${saldo_actual}, pedido ${monto_pedido}, "
            f"límite ${limite}"
        )


async def agregar_deuda(
    db: AsyncSession,
    cliente_id: int,
    empresa_id: int,
    monto: Decimal,
) -> Cliente | None:
    """Agrega deuda al saldo_pendiente del cliente (al confirmar un pedido).
    
    Retorna el cliente actualizado o None si no existe.
    """
    cliente = await get_by_id(db, cliente_id, empresa_id)
    if cliente is None:
        return None
    cliente.saldo_pendiente = (cliente.saldo_pendiente or Decimal("0")) + monto
    await db.commit()
    await db.refresh(cliente)
    return cliente


async def registrar_pago(
    db: AsyncSession,
    cliente_id: int,
    empresa_id: int,
    monto: Decimal,
    usuario_id: int,
    pedido_id: int | None = None,
    metodo_pago: str = "efectivo",
    nota: str | None = None,
) -> tuple[Pago, Cliente]:
    """Registra un pago y reduce el saldo_pendiente del cliente.
    
    Retorna (pago, cliente_actualizado).
    
    Raises:
        ValueError: Si el monto es <= 0 o el cliente no existe.
    """
    cliente = await get_by_id(db, cliente_id, empresa_id)
    if cliente is None:
        raise ValueError("Cliente no encontrado")

    if monto <= 0:
        raise ValueError("El monto del pago debe ser mayor a 0")

    # Crear registro de pago
    pago = Pago(
        cliente_id=cliente_id,
        empresa_id=empresa_id,
        pedido_id=pedido_id,
        monto=monto,
        metodo_pago=metodo_pago,
        nota=nota,
        registrado_por=usuario_id,
    )
    db.add(pago)

    # Reducir saldo pendiente (no puede ser negativo)
    cliente.saldo_pendiente = max(Decimal("0"), (cliente.saldo_pendiente or Decimal("0")) - monto)

    await db.commit()
    await db.refresh(pago)
    await db.refresh(cliente)
    return pago, cliente


async def verificar_limite_credito(
    db: AsyncSession,
    cliente_id: int,
    empresa_id: int,
    monto_pedido: Decimal,
) -> None:
    """Verifica que el pedido no exceda el límite de crédito del cliente.
    
    Si el cliente no tiene límite configurado, no hay restricción.
    
    Raises:
        LimiteCreditoExcedido: Si el pedido excede el límite.
    """
    cliente = await get_by_id(db, cliente_id, empresa_id)
    if cliente is None:
        return  # Sin cliente, no hay validación

    if cliente.limite_credito is None:
        return  # Sin límite configurado

    saldo_actual = cliente.saldo_pendiente or Decimal("0")
    if saldo_actual + monto_pedido > cliente.limite_credito:
        raise LimiteCreditoExcedido(
            f"{cliente.nombre} {cliente.apellido}",
            saldo_actual,
            monto_pedido,
            cliente.limite_credito,
        )


async def get_pagos_cliente(
    db: AsyncSession,
    cliente_id: int,
    empresa_id: int,
) -> list[Pago]:
    """Obtiene todos los pagos de un cliente, ordenados cronológicamente descendente."""
    query = (
        select(Pago)
        .where(Pago.cliente_id == cliente_id, Pago.empresa_id == empresa_id)
        .order_by(Pago.created_at.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_top_deudores(
    db: AsyncSession,
    empresa_id: int,
    limit: int = 10,
) -> list[Cliente]:
    """Obtiene los clientes con mayor saldo pendiente."""
    query = (
        select(Cliente)
        .where(
            Cliente.empresa_id == empresa_id,
            Cliente.saldo_pendiente > 0,
        )
        .order_by(Cliente.saldo_pendiente.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())
