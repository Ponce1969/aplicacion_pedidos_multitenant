"""Dependencias compartidas de la aplicación."""

from app.dependencies.auth_dep import AuthRequiredException, require_auth

__all__ = ["AuthRequiredException", "require_auth"]
