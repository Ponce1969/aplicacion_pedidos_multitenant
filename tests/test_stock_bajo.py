"""Tests para M-08: Alerta de stock bajo."""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Producto
from app.repositories import producto_repo


class TestStockMinimoModel:
    """M-08: Verificar que el modelo tiene stock_minimo."""

    def test_producto_tiene_stock_minimo(self, producto_empresa_a):
        """Producto tiene campo stock_minimo."""
        assert hasattr(producto_empresa_a, "stock_minimo")


class TestGetStockBajo:
    """M-08: Query de productos con stock bajo."""

    async def test_producto_con_stock_bajo_aparece_en_resultado(
        self, db_session, empresa_a
    ):
        """Producto con stock < stock_minimo aparece en la lista."""
        producto = Producto(
            nombre="Arena",
            sku="ARENA-25",
            precio_base=Decimal("200"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=Decimal("2"),
            stock_minimo=Decimal("5"),
        )
        db_session.add(producto)
        await db_session.commit()

        resultados = await producto_repo.get_stock_bajo(db_session, empresa_a.id)
        assert len(resultados) == 1
        assert resultados[0].nombre == "Arena"

    async def test_producto_con_stock_suficiente_no_aparece(
        self, db_session, empresa_a
    ):
        """Producto con stock >= stock_minimo NO aparece."""
        producto = Producto(
            nombre="Cemento",
            sku="CEM-50",
            precio_base=Decimal("500"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=Decimal("10"),
            stock_minimo=Decimal("5"),
        )
        db_session.add(producto)
        await db_session.commit()

        resultados = await producto_repo.get_stock_bajo(db_session, empresa_a.id)
        assert len(resultados) == 0

    async def test_producto_sin_stock_minimo_no_aparece(
        self, db_session, empresa_a
    ):
        """Producto sin stock_minimo configurado NO aparece."""
        producto = Producto(
            nombre="Tornillo",
            sku="TORN",
            precio_base=Decimal("10"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=Decimal("0"),
            stock_minimo=None,
        )
        db_session.add(producto)
        await db_session.commit()

        resultados = await producto_repo.get_stock_bajo(db_session, empresa_a.id)
        assert len(resultados) == 0

    async def test_producto_sin_stock_no_aparece(
        self, db_session, empresa_a
    ):
        """Producto con stock=None (sin control) NO aparece."""
        producto = Producto(
            nombre="Servicio",
            sku="SERV",
            precio_base=Decimal("1000"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=None,
            stock_minimo=Decimal("5"),
        )
        db_session.add(producto)
        await db_session.commit()

        resultados = await producto_repo.get_stock_bajo(db_session, empresa_a.id)
        assert len(resultados) == 0

    async def test_producto_igual_al_minimo_aparece(
        self, db_session, empresa_a
    ):
        """Producto con stock == stock_minimo SÍ aparece (<=)."""
        producto = Producto(
            nombre="Pintura",
            sku="PINT-1L",
            precio_base=Decimal("300"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=Decimal("5"),
            stock_minimo=Decimal("5"),
        )
        db_session.add(producto)
        await db_session.commit()

        resultados = await producto_repo.get_stock_bajo(db_session, empresa_a.id)
        assert len(resultados) == 1

    async def test_producto_inactivo_no_aparece(
        self, db_session, empresa_a
    ):
        """Producto inactivo NO aparece aunque tenga stock bajo."""
        producto = Producto(
            nombre="Descontinuado",
            sku="DESC",
            precio_base=Decimal("100"),
            empresa_id=empresa_a.id,
            is_active=False,
            stock=Decimal("0"),
            stock_minimo=Decimal("10"),
        )
        db_session.add(producto)
        await db_session.commit()

        resultados = await producto_repo.get_stock_bajo(db_session, empresa_a.id)
        assert len(resultados) == 0

    async def test_stock_bajo_ordenado_por_stock_asc(
        self, db_session, empresa_a
    ):
        """Resultados ordenados por stock ascendente (el más crítico primero)."""
        prod_a = Producto(
            nombre="Prod A",
            sku="PA",
            precio_base=Decimal("100"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=Decimal("1"),
            stock_minimo=Decimal("10"),
        )
        prod_b = Producto(
            nombre="Prod B",
            sku="PB",
            precio_base=Decimal("200"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=Decimal("3"),
            stock_minimo=Decimal("10"),
        )
        db_session.add_all([prod_a, prod_b])
        await db_session.commit()

        resultados = await producto_repo.get_stock_bajo(db_session, empresa_a.id)
        assert len(resultados) == 2
        assert resultados[0].nombre == "Prod A"  # stock=1 primero
        assert resultados[1].nombre == "Prod B"  # stock=3 después

    async def test_stock_bajo_multi_tenant(
        self, db_session, empresa_a, empresa_b
    ):
        """Solo muestra productos de la empresa del usuario."""
        prod_a = Producto(
            nombre="Prod Empresa A",
            sku="PA",
            precio_base=Decimal("100"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=Decimal("1"),
            stock_minimo=Decimal("10"),
        )
        prod_b = Producto(
            nombre="Prod Empresa B",
            sku="PB",
            precio_base=Decimal("200"),
            empresa_id=empresa_b.id,
            is_active=True,
            stock=Decimal("1"),
            stock_minimo=Decimal("10"),
        )
        db_session.add_all([prod_a, prod_b])
        await db_session.commit()

        resultados_a = await producto_repo.get_stock_bajo(db_session, empresa_a.id)
        resultados_b = await producto_repo.get_stock_bajo(db_session, empresa_b.id)
        assert len(resultados_a) == 1
        assert resultados_a[0].nombre == "Prod Empresa A"
        assert len(resultados_b) == 1
        assert resultados_b[0].nombre == "Prod Empresa B"


class TestCountStockBajo:
    """M-08: Count de productos con stock bajo."""

    async def test_count_productos_stock_bajo(self, db_session, empresa_a):
        """Cuenta correctamente los productos con stock bajo."""
        prod_a = Producto(
            nombre="Prod A",
            sku="PA",
            precio_base=Decimal("100"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=Decimal("1"),
            stock_minimo=Decimal("5"),
        )
        prod_b = Producto(
            nombre="Prod B",
            sku="PB",
            precio_base=Decimal("200"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=Decimal("10"),
            stock_minimo=Decimal("5"),
        )
        db_session.add_all([prod_a, prod_b])
        await db_session.commit()

        count = await producto_repo.count_stock_bajo(db_session, empresa_a.id)
        assert count == 1  # Solo prod_a tiene stock bajo

    async def test_count_cero_si_no_hay_stock_bajo(self, db_session, empresa_a):
        """Retorna 0 si no hay productos con stock bajo."""
        count = await producto_repo.count_stock_bajo(db_session, empresa_a.id)
        assert count == 0
