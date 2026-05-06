"""
Backfill: crea registros en 'clientes' para pedidos que no tienen cliente_id.

Recorre todos los pedidos con cliente_id=NULL y:
1. Busca si ya existe un cliente con ese celular en la misma empresa
2. Si existe → le asigna el cliente_id al pedido
3. Si no existe → crea el cliente y le asigna el cliente_id

Uso:
    docker compose -f docker-compose.prod.yml exec app python scripts/backfill_clientes.py
"""

import asyncio
import os
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models import Cliente, Pedido


async def backfill() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("❌ DATABASE_URL no configurada")
        return

    # Asegurar que use asyncpg
    if "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Buscar todos los pedidos sin cliente_id
        result = await db.execute(
            select(Pedido).where(Pedido.cliente_id.is_(None)).order_by(Pedido.empresa_id, Pedido.id)
        )
        pedidos_sin_cliente = list(result.scalars().all())

        if not pedidos_sin_cliente:
            print("✅ Todos los pedidos ya tienen cliente_id. Nada que hacer.")
            await engine.dispose()
            return

        print(f"📋 Encontrados {len(pedidos_sin_cliente)} pedidos sin cliente_id\n")

        creados = 0
        vinculados = 0
        saltados = 0

        for pedido in pedidos_sin_cliente:
            # Buscar cliente existente por celular + empresa
            existing = await db.execute(
                select(Cliente).where(
                    Cliente.empresa_id == pedido.empresa_id,
                    Cliente.celular == pedido.celular,
                )
            )
            cliente_existente = existing.scalar_one_or_none()

            if cliente_existente:
                # Ya existe → vincular
                pedido.cliente_id = cliente_existente.id
                vinculados += 1
                print(f"  🔗 Vinculado: Pedido #{pedido.id} → Cliente existente "
                      f"'{cliente_existente.nombre} {cliente_existente.apellido}' (id={cliente_existente.id})")
            else:
                # No crear clientes con celular default o vacío
                if pedido.celular in ("000000000", ""):
                    saltados += 1
                    print(f"  ⏭️  Saltado: Pedido #{pedido.id} — celular default/vacío "
                          f"({pedido.celular}) nombre='{pedido.nombre} {pedido.apellido}'")
                    continue

                nuevo_cliente = Cliente(
                    empresa_id=pedido.empresa_id,
                    nombre=pedido.nombre or "Sin nombre",
                    apellido=pedido.apellido or "",
                    celular=pedido.celular,
                    direccion=pedido.direccion or "Sin dirección",
                )
                db.add(nuevo_cliente)
                await db.flush()  # Obtener el ID sin commit todavía
                pedido.cliente_id = nuevo_cliente.id
                creados += 1
                print(f"  ✨ Creado: Cliente '{nuevo_cliente.nombre} {nuevo_cliente.apellido}' "
                      f"celular={nuevo_cliente.celular} (id={nuevo_cliente.id}) → Pedido #{pedido.id}")

        await db.commit()

    print(f"\n📊 Resumen:")
    print(f"   Clientes nuevos creados: {creados}")
    print(f"   Pedidos vinculados a existentes: {vinculados}")
    print(f"   Pedidos saltados (celular default): {saltados}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(backfill())