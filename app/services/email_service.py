"""Servicio de envío de emails para recuperación de contraseña."""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


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

        logger.info("Email de reseteo enviado a %s", recipient_email)
        return True
    except Exception:
        logger.exception("Error enviando email de reseteo a %s", recipient_email)
        return False
