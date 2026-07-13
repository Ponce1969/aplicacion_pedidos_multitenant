# 📋 Próximos pasos (backlog)

Anotado para la próxima sesión. Ver también la sección **Deploy en Producción** en el README.

## 🔴 Sesión siguiente (prioridad alta)
- [ ] **Verificar / rotar `SECRET_KEY` en producción**: el app arranca Healthy, así que ya NO es el default de dev (lo garantiza el guard en `app/config.py`). Confirmar que el valor en `.env` del server es fuerte; si no, generar con `openssl rand -hex 32` y recrear el contenedor `app`.
- [ ] **Self-hostear htmx + Tailwind** en `/static/` y eliminar `unpkg.com` / `cdn.tailwindcss.com` / `cdn.jsdelivr.net` del CSP (`app/security_headers.py`). Reduce superficie de ataque y elimina dependencia de CDN.

## 🟡 Media
- [ ] Extender rate-limit a `/api/forgot-password` y `/api/reset-password` (hoy solo `/api/login` y `/api/registro` en `nginx.conf`).
- [ ] Estrategia de backups de PostgreSQL (volumen `postgres_data`).
- [ ] Cadencia de auditoría: vulnerability scanner + `pip-audit` periódicamente.

## 🟢 Baja (limpieza)
- [ ] README: cambiar el ejemplo `POSTGRES_PASSWORD: barraca_dev_2024` por `<CAMBIAR>` para no tentar a nadie.
- [ ] Quitar `cdn.jsdelivr.net` del CSP si se confirma que no se usa.

---

> ⚠️ **Recordatorio de deploy**: tras `git pull` que toque `nginx.conf`, recrear el contenedor
> (`docker compose -f docker-compose.prod.yml up -d --force-recreate nginx`), no solo `reload`.
> `git pull` reemplaza el archivo (nuevo inode) y el bind mount del contenedor en ejecución
> sigue viendo el inode anterior.
