from datetime import datetime

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
    moneda: Mapped[str] = mapped_column(String(10), default="PYG", server_default="PYG")
    zona_horaria: Mapped[str] = mapped_column(String(50), default="America/Asuncion", server_default="America/Asuncion")
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
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
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ultimo_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    # Relationship
    empresa: Mapped["Empresa"] = relationship(back_populates="usuarios", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("empresa_id", "email", name="uq_usuario_empresa_email"),
        Index("idx_usuario_email", "email"),
    )


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    celular: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direccion: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship: un cliente tiene muchos pedidos
    pedidos: Mapped[list["Pedido"]] = relationship(
        back_populates="cliente_rel", lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("empresa_id", "celular", name="uq_cliente_empresa_celular"),
        Index("idx_cliente_celular", "celular"),
    )


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    sku: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    precio_base: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0.0)
    stock: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, default=0.0)
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
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    cliente_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clientes.id"), nullable=True, index=True)

    # Campos legacy (se mantienen para compatibilidad)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    celular: Mapped[str] = mapped_column(String(20), nullable=False)
    direccion: Mapped[str] = mapped_column(String(200), nullable=False)
    hora_entrega: Mapped[str] = mapped_column(String(10), nullable=False)
    pedido_detalle: Mapped[str] = mapped_column(Text, nullable=False)

    # Campos nuevos
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True, default=0.0)
    impuestos: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True, default=0.0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    estado: Mapped[str] = mapped_column(String(20), default="pendiente", server_default="pendiente")
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    fecha_entrega: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    cliente_rel: Mapped["Cliente | None"] = relationship(
        back_populates="pedidos", foreign_keys=[cliente_id],
        lazy="selectin",
    )
    items: Mapped[list["PedidoItem"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_celular", "celular"),
        Index("idx_apellido", "apellido"),
        Index("idx_fecha_creacion", "fecha_creacion"),
        Index("idx_usuario_pedidos", "usuario_id"),
        Index("idx_pedido_cliente", "cliente_id"),
        Index("idx_pedido_empresa", "empresa_id"),
    )


class PedidoItem(Base):
    __tablename__ = "pedido_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pedido_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pedidos.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    producto_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("productos.id"), nullable=True, index=True)
    descripcion: Mapped[str] = mapped_column(String(300), nullable=False)
    cantidad: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=1.0)
    precio_unitario: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0.0)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0.0)

    # Relationships
    pedido: Mapped["Pedido"] = relationship(back_populates="items", lazy="selectin")
    producto: Mapped["Producto | None"] = relationship(back_populates="items", lazy="selectin")

    __table_args__ = (Index("idx_item_pedido", "pedido_id"),)


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
