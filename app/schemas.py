from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# Auth Schemas
class UsuarioCreate(BaseModel):
    email: EmailStr
    nombre: str = Field(min_length=2, max_length=100)
    apellido: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        msg_upper = "La contraseña debe tener al menos una mayúscula"
        msg_digit = "La contraseña debe tener al menos un número"
        if not any(c.isupper() for c in v):
            raise ValueError(msg_upper)
        if not any(c.isdigit() for c in v):
            raise ValueError(msg_digit)
        return v


class UsuarioLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600  # 60 minutos en segundos


class UsuarioResponse(BaseModel):
    id: int
    email: EmailStr
    nombre: str
    apellido: str
    is_admin: bool

    model_config = {"from_attributes": True}


# Pedido Schemas
class PedidoBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    apellido: str = Field(min_length=2, max_length=100)
    celular: str = Field(pattern=r"^\+?[0-9]{8,15}$")
    direccion: str = Field(min_length=5, max_length=200)
    hora_entrega: str = Field(pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    fecha_entrega: date
    pedido_detalle: str
    total: float = Field(gt=0)


class PedidoCreate(PedidoBase):
    pass


class PedidoResponse(PedidoBase):
    id: int
    usuario_id: int
    fecha_creacion: datetime
    estado: str

    model_config = {"from_attributes": True}
