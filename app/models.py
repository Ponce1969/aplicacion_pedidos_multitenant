from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ultimo_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    __table_args__ = (Index("idx_usuario_email", "email"),)


class Pedido(Base):
    __tablename__ = "pedidos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    celular: Mapped[str] = mapped_column(String(20), nullable=False)
    direccion: Mapped[str] = mapped_column(String(200), nullable=False)
    hora_entrega: Mapped[str] = mapped_column(String(10), nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    fecha_entrega: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pedido_detalle: Mapped[str] = mapped_column(Text, nullable=False)
    total: Mapped[float] = mapped_column(Float, default=0.0)
    estado: Mapped[str] = mapped_column(String(20), default="pendiente", server_default="pendiente")

    __table_args__ = (
        Index("idx_celular", "celular"),
        Index("idx_apellido", "apellido"),
        Index("idx_fecha_creacion", "fecha_creacion"),
        Index("idx_usuario_pedidos", "usuario_id"),
    )


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    expiracion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
