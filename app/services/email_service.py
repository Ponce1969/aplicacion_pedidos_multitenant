"""Servicio de envío de emails multi-tenant.

Incluye:
- Password reset (legacy SMTP)
- Notificaciones de pedido (Resend API)
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

import httpx
from fastapi import BackgroundTasks
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

from app.config import settings
from app.schemas import EmailTemplateData

logger = logging.getLogger(__name__)

# Directorio de templates de email
TEMPLATES_DIR = Path(__file__).parent / "templates" / "email"


def send_password_reset_email(recipient_email: str, token: str, user_name: str) -> bool:
    """Envía email con link de reseteo de contraseña.

    Retorna True si se envió correctamente, False si falló.
    Si SMTP no está configurado, loguea el link y retorna True (modo dev).
    """
    reset_url = f"{settings.BASE_URL}/reset-password?token={token}"

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2563eb;">Recuperación de Contraseña</h2>
        <p>Hola <strong>{user_name}</strong>,</p>
        <p>Recibimos una solicitud para restablecer tu contraseña.</p>
        <p>Hacé clic en el botón de abajo para crear una nueva contraseña:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}"
               style="background-color: #2563eb; color: white; padding: 12px 24px;
                      text-decoration: none; border-radius: 8px; font-weight: bold;">
                Restablecer Contraseña
            </a>
        </div>
        <p style="color: #6b7280; font-size: 14px;">
            Este link expira en {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutos.
            Si no solicitaste este cambio, ignorá este email.
        </p>
        <p style="color: #6b7280; font-size: 14px;">
            Si el botón no funciona, copiá este link en tu navegador:<br>
            <a href="{reset_url}">{reset_url}</a>
        </p>
    </div>
    """

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP no configurado — link de reseteo: %s", reset_url)
        return True  # Modo desarrollo: no envía email pero funciona

    try:
        msg = MIMEText(html_body, "html")
        msg["Subject"] = "Recuperación de Contraseña"
        msg["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
        msg["To"] = recipient_email

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception:
        logger.exception("Error enviando email de reseteo a %s", recipient_email)
        return False
    else:
        logger.info("Email de reseteo enviado a %s", recipient_email)
        return True


class EmailService:
    """Servicio de envío de emails con templates personalizados por tenant.
    
    Usa Resend API para el envío. Si no hay API key configurada,
    retorna False silenciosamente (graceful degradation).
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.RESEND_API_KEY
        self.sender = settings.RESEND_FROM_EMAIL
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )

    async def send_pedido_update(
        self,
        template_data: EmailTemplateData,
        background_tasks: BackgroundTasks | None = None,
    ) -> bool:
        """Envía notificación de cambio de estado de pedido.

        Args:
            template_data: Datos validados para la plantilla
            background_tasks: Si se provee, encola el envío. Si no, envía sync.

        Returns:
            True si se encoló/envió correctamente, False en caso contrario.
        """
        if not self.api_key:
            logger.debug("RESEND_API_KEY no configurada — email no enviado")
            return False

        # 1. Renderizar template HTML
        html_content = self._render_template("pedido_update.html", template_data)

        # 2. Configurar payload
        payload = {
            "from": self.sender,
            "to": [template_data.cliente_email],
            "reply_to": template_data.email_contacto or self.sender,
            "subject": f"Tu pedido #{template_data.pedido_id} está {template_data.pedido_estado}",
            "html": html_content,
        }

        # 3. Enviar o encolar
        if background_tasks:
            background_tasks.add_task(self._send_via_resend, payload)
            return True
        return await self._send_via_resend(payload)

    def _render_template(self, template_name: str, data: EmailTemplateData) -> str:
        """Renderiza template Jinja2 con los datos proporcionados."""
        template = self.jinja_env.get_template(template_name)
        return template.render(**data.model_dump())

    async def _send_via_resend(self, payload: dict[str, object]) -> bool:
        """Llama a la API de Resend. Retorna True/False, nunca lanza excepción."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception:
            logger.exception("Failed to send email via Resend")
            return False
