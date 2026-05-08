from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# ==================== TENANT (EMPRESA) ====================


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    rubro: Mapped[str | None] = mapped_column(String(100), nullable=True)
    moneda: Mapped[str] = mapped_column(String(10), default="UYU", server_default="UYU")
    zona_horaria: Mapped[str] = mapped_column(
        String(50), default="America/Montevideo", server_default="America/Montevideo"
    )
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email_contacto: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telefono_contacto: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color_primario: Mapped[str] = mapped_column(String(7), default="#3b82f6", server_default="#3b82f6")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="empresa", lazy="selectin")

    __table_args__ = (Index("idx_empresa_slug", "slug"),)


# ==================== MODELOS DE NEGOCIO ====================


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    rol: Mapped[str] = mapped_column(String(20), default="operador", server_default="operador")
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ultimo_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    # Relationship
    empresa: Mapped["Empresa"] = relationship(back_populates="usuarios", lazy="selectin")
    # Pedidos asignados a este repartidor
    entregas_asignadas: Mapped[list["Pedido"]] = relationship(
        back_populates="repartidor",
        foreign_keys="Pedido.repartidor_id",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("empresa_id", "email", name="uq_usuario_empresa_email"),
        Index("idx_usuario_email", "email"),
    )


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    ci: Mapped[str | None] = mapped_column(String(20), nullable=True)  # Cédula de identidad — única por empresa
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    celular: Mapped[str] = mapped_column(String(20), nullable=False)
    direccion: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Cuenta corriente
    saldo_pendiente: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")
    limite_credito: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Flag para identificar clientes de sistema (ej. "Consumidor Final")
    # que el usuario no debe poder eliminar o modificar fácilmente.
    es_sistema_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Relationship: un cliente tiene muchos pedidos
    pedidos: Mapped[list["Pedido"]] = relationship(
        back_populates="cliente_rel",
        lazy="selectin",
    )
    # Relationship: un cliente tiene muchas direcciones guardadas
    direcciones: Mapped[list["ClienteDireccion"]] = relationship(
        back_populates="cliente",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    # Relationship: un cliente tiene muchos pagos
    pagos: Mapped[list["Pago"]] = relationship(
        back_populates="cliente",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("empresa_id", "celular", name="uq_cliente_empresa_celular"),
        UniqueConstraint("empresa_id", "ci", name="uq_cliente_empresa_ci"),
        Index("idx_cliente_celular", "celular"),
    )


class ClienteDireccion(Base):
    """Direcciones guardadas de un cliente (casa, trabajo, depósito, etc.)."""

    __tablename__ = "cliente_direcciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    descripcion: Mapped[str] = mapped_column(String(100), nullable=False)  # ej: "Casa", "Trabajo"
    direccion: Mapped[str] = mapped_column(Text, nullable=False)  # texto completo de la dirección
    es_principal: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    cliente: Mapped["Cliente"] = relationship(back_populates="direcciones", lazy="selectin")

    __table_args__ = (
        Index("idx_dir_cliente", "cliente_id"),
        Index("idx_dir_empresa", "empresa_id"),
    )


class Pago(Base):
    """Registro de pagos realizados por un cliente (cuenta corriente).

    Tabla append-only: los pagos no se editan ni eliminan.
    Cada pago reduce el saldo_pendiente del cliente.
    """

    __tablename__ = "pagos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clientes.id"), nullable=False, index=True
    )
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    pedido_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pedidos.id"), nullable=True, index=True
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    metodo_pago: Mapped[str] = mapped_column(
        String(30), default="efectivo", server_default="efectivo"
    )  # efectivo, transferencia, tarjeta, otro
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)
    registrado_por: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    cliente: Mapped["Cliente"] = relationship(back_populates="pagos", lazy="selectin")

    __table_args__ = (
        Index("idx_pago_cliente", "cliente_id"),
        Index("idx_pago_empresa", "empresa_id"),
        Index("idx_pago_pedido", "pedido_id"),
    )


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    sku: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    precio_base: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    stock: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    stock_minimo: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    unidad_medida: Mapped[str] = mapped_column(String(20), default="unidad", server_default="unidad")
    categoria: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship: un producto aparece en muchas líneas de pedido
    items: Mapped[list["PedidoItem"]] = relationship(back_populates="producto", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("empresa_id", "sku", name="uq_producto_empresa_sku"),
        Index("idx_producto_nombre", "nombre"),
    )


class Pedido(Base):
    __tablename__ = "pedidos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    numero_pedido: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    cliente_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clientes.id"), nullable=True, index=True)

    # Campos legacy (se mantienen para compatibilidad)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    celular: Mapped[str] = mapped_column(String(20), nullable=False)
    ci: Mapped[str | None] = mapped_column(String(20), nullable=True)  # Cédula de identidad del cliente
    direccion: Mapped[str] = mapped_column(String(200), nullable=False)
    hora_entrega: Mapped[str | None] = mapped_column(String(10), nullable=True, default=None)
    pedido_detalle: Mapped[str] = mapped_column(Text, nullable=False)

    # Campos nuevos — Decimal para precisión monetaria
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True, default=Decimal("0"))
    impuestos: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    
    # Seña/Adelanto
    senia: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True, default=Decimal("0"))
    estado_pago: Mapped[str] = mapped_column(String(20), default="pendiente", server_default="pendiente")
    
    estado: Mapped[str] = mapped_column(String(20), default="pendiente", server_default="pendiente")
    repartidor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    fecha_entrega: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    cliente_rel: Mapped["Cliente | None"] = relationship(
        back_populates="pedidos",
        foreign_keys=[cliente_id],
        lazy="selectin",
    )
    repartidor: Mapped["Usuario | None"] = relationship(
        back_populates="entregas_asignadas",
        foreign_keys=[repartidor_id],
        lazy="selectin",
    )
    items: Mapped[list["PedidoItem"]] = relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_celular", "celular"),
        Index("idx_apellido", "apellido"),
        Index("idx_fecha_creacion", "fecha_creacion"),
        Index("idx_usuario_pedidos", "usuario_id"),
        Index("idx_pedido_cliente", "cliente_id"),
        Index("idx_pedido_empresa", "empresa_id"),
        Index("idx_pedido_repartidor", "repartidor_id"),
        UniqueConstraint("empresa_id", "numero_pedido", name="uq_pedido_empresa_numero"),
    )


class PedidoItem(Base):
    __tablename__ = "pedido_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pedido_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("pedidos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    producto_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("productos.id"), nullable=True, index=True)
    descripcion: Mapped[str] = mapped_column(String(300), nullable=False)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("1"))
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))

    # Relationships
    pedido: Mapped["Pedido"] = relationship(back_populates="items", lazy="selectin")
    producto: Mapped["Producto | None"] = relationship(back_populates="items", lazy="selectin")

    __table_args__ = (Index("idx_item_pedido", "pedido_id"),)


class EntregaEvento(Base):
    """Registro de cambios de estado de entrega (auditoría)."""

    __tablename__ = "entrega_eventos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pedido_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("pedidos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False)
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    estado_anterior: Mapped[str | None] = mapped_column(String(30), nullable=True)
    estado_nuevo: Mapped[str] = mapped_column(String(30), nullable=False)
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_evento_pedido", "pedido_id"),
        Index("idx_evento_empresa", "empresa_id"),
    )


class Configuracion(Base):
    __tablename__ = "configuracion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    clave: Mapped[str] = mapped_column(String(100), nullable=False)
    valor: Mapped[str] = mapped_column(String(500), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        UniqueConstraint("empresa_id", "clave", name="uq_config_empresa_clave"),
        Index("idx_config_clave", "clave"),
    )


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    expiracion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    expiracion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
