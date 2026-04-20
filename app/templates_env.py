"""Templates con filtros personalizados para Jinja2.

Centraliza la configuración de Jinja2Templates y registra
filtros globales como format_pesos y format_cantidad.
"""

from fastapi.templating import Jinja2Templates

from app.template_filters import format_cantidad, format_pesos


def get_templates() -> Jinja2Templates:
    """Retorna una instancia de Jinja2Templates con filtros custom registrados."""
    templates = Jinja2Templates(directory="app/templates")
    # Autoescape ON para protección XSS — Jinja2Templates no acepta
    # autoescape como kwarg, se configura en el Environment después de crear
    templates.env.autoescape = True
    templates.env.globals["pesos"] = format_pesos
    templates.env.globals["cantidad"] = format_cantidad
    templates.env.filters["pesos"] = format_pesos
    templates.env.filters["cantidad"] = format_cantidad
    return templates
