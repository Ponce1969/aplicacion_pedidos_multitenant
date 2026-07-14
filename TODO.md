# 📋 Próximos pasos (backlog)

Anotado para la próxima sesión. Ver también la sección **Deploy en Producción** en el README.

## 🔴 Sesión siguiente (prioridad alta)
- [x] **Verificar / rotar `SECRET_KEY` en producción**: rotado con `openssl rand -hex 32` y recreado el contenedor `app`. ✅
- [x] **Self-hostear htmx** en `/static/` y eliminar `unpkg.com` del CSP. ✅ Hecho y deployado. Descubrimos y fixeamos que nginx no montaba `app/static` (agregado en `docker-compose.prod.yml`).
- [x] **Self-hostear Tailwind** (build profesional) y eliminar `cdn.tailwindcss.com` del CSP. ✅ Hecho: standalone CLI en Dockerfile, output en `app/static/css/tailwind.css`.



## 🟢 Baja (limpieza) — ✅ resuelto en esta sesión
- [x] README: cambiar el ejemplo `POSTGRES_PASSWORD: barraca_dev_2024` por `<CAMBIAR>` para no tentar a nadie.
- [x] Quitar `cdn.jsdelivr.net` del CSP si se confirma que no se usa.

> ⚠️ **Recordatorio de deploy**: tras `git pull` que toque `nginx.conf`, recrear el contenedor
> (`docker compose -f docker-compose.prod.yml up -d --force-recreate nginx`), no solo `reload`.
> `git pull` reemplaza el archivo (nuevo inode) y el bind mount del contenedor en ejecución
> sigue viendo el inode anterior.

---

## 🟡 Futuro (diferido a más usuarios/empresas)

> Decisión del equipo: no se implementa hoy porque aún no hay suficientes usuarios/empresas con datos críticos. Se activará cuando el riesgo lo justifique.

- [ ] **Estrategia de backups de PostgreSQL** (volumen `postgres_data`).
  - Definir destino (disco local, USB, S3/Backblaze, etc.), frecuencia y retención.
  - Automatizar con `pg_dump` + cron o servicio de backups.
- [ ] **Cadencia de auditoría de seguridad**.
  - `uv run python scripts/vulnerability_scanner.py` (si existe) o similar.
  - `pip-audit` para detectar dependencias con vulnerabilidades.
  - Definir si corre en CI o como cron en el servidor, y si falla el build o solo reporta.
