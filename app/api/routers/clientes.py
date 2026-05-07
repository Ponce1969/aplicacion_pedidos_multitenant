"""Router para endpoints de clientes e insights.

Este módulo expone endpoints HTMX para consultar información consolidada
de clientes (patrón CQRS - Query side).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Usuario
from app.repositories import cliente_repo
from app.services.queries.cliente_insights_service import get_consolidado, get_pedidos
from app.templates_env import get_templates

router = APIRouter()
templates = get_templates()


@router.get("/api/clientes/{cliente_id}/insights")
async def get_cliente_insights(
    cliente_id: int,
    request: Request,
    type: str = Query(..., pattern="^(consolidado|pedidos)$"),
    dias: int = Query(default=30, ge=1, le=365),
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    """Obtiene insights de un cliente (consolidado o lista de pedidos).

    Args:
        cliente_id: ID del cliente a consultar
        type: Tipo de insight - 'consolidado' o 'pedidos'
        dias: Días hacia atrás para filtrar (1-365)

    Returns:
        HTMLResponse con el partial renderizado via HTMX

    Raises:
        HTTPException 404: Si el cliente no existe o no pertenece a la empresa
    """
    # 1. Verificar que el cliente pertenezca a la empresa del usuario
    cliente = await cliente_repo.get_by_id(db, cliente_id, current_user.empresa_id)
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado",
        )

    # 2. Dispatch al servicio según el tipo solicitado
    try:
        if type == "consolidado":
            data = await get_consolidado(db, cliente_id, current_user.empresa_id, dias)
        else:
            data = await get_pedidos(db, cliente_id, current_user.empresa_id, dias)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    # 3. Renderizar HTMX partial
    return templates.TemplateResponse(
        request,
        "partials/cliente_insights.html",
        {
            "insights": data,
            "type": type,
            "dias": dias,
            "cliente": cliente,
        },
    )
