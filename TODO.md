# 📋 Próximos pasos (backlog)

Anotado para la próxima sesión. Ver también la sección **Deploy en Producción** en el README.

## 🔴 Sesión siguiente (prioridad alta)
- [x] **Verificar / rotar `SECRET_KEY` en producción**: rotado con `openssl rand -hex 32` y recreado el contenedor `app`. ✅
- [x] **Self-hostear htmx** en `/static/` y eliminar `unpkg.com` del CSP. ✅ Hecho y deployado. Descubrimos y fixeamos que nginx no montaba `app/static` (agregado en `docker-compose.prod.yml`).
- [ ] **Self-hostear Tailwind** (build profesional) y eliminar `cdn.tailwindcss.com` del CSP. → Diferido a sesión futura.

## 🟡 Media
- [ ] Extender rate-limit a `/api/forgot-password` y `/api/reset-password` (hoy solo `/api/login` y `/api/registro` en `nginx.conf`).
- [ ] Estrategia de backups de PostgreSQL (volumen `postgres_data`).
- [ ] Cadencia de auditoría: vulnerability scanner + `pip-audit` periódicamente.

## 🟢 Baja (limpieza) — ✅ resuelto en esta sesión
- [x] README: cambiar el ejemplo `POSTGRES_PASSWORD: barraca_dev_2024` por `<CAMBIAR>` para no tentar a nadie.
- [x] Quitar `cdn.jsdelivr.net` del CSP si se confirma que no se usa.

---

> ⚠️ **Recordatorio de deploy**: tras `git pull` que toque `nginx.conf`, recrear el contenedor
> (`docker compose -f docker-compose.prod.yml up -d --force-recreate nginx`), no solo `reload`.
> `git pull` reemplaza el archivo (nuevo inode) y el bind mount del contenedor en ejecución
> sigue viendo el inode anterior.
