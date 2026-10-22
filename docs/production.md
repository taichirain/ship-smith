# Production Deployment

This document covers the production Compose profile and ShipSmith's own backup/restore path.

## 1. Prepare secrets

Copy `.env.production.example` to `.env.production` and replace every placeholder:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
openssl rand -base64 48   # JWT_SECRET_KEY
openssl rand -base64 48   # GIT_CREDENTIALS_SECRET_KEY
openssl rand -base64 48   # ADMIN_PASSWORD
openssl rand -base64 48   # POSTGRES_PASSWORD
```

`ENV=production` makes the API fail closed when defaults, short secrets, placeholders, `example.com` values, wildcard CORS, or a non-HTTPS `PUBLIC_CORE_URL` are used.

## 2. Start the stack

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Only the API and web ports bind to `127.0.0.1`. Put a TLS-terminating reverse proxy in front of them. Example Caddy:

```caddy
shipsmith.example.com {
    reverse_proxy 127.0.0.1:3000
}
api.shipsmith.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Set `CORS_ORIGINS` to the exact web origin(s), and `PUBLIC_CORE_URL` / `INSTALL_SCRIPT_URL` to the public HTTPS URLs.

## 3. Migrations

Production starts with `RUN_MIGRATIONS=0`; migrations are explicit:

```bash
# take a backup first
./scripts/backup_shipsmith.sh

# run migrations with the new image
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm api alembic upgrade head
```

## 4. Backups

```bash
./scripts/backup_shipsmith.sh
```

The script writes a PostgreSQL custom-format dump, globals, manifest and SHA256SUMS under `backups/<timestamp>/`, and keeps the newest 7 by default. Set `SHIPSMITH_BACKUP_MIRROR_DIR` for a second copy on another disk.

Schedule it with cron or a systemd timer, for example daily at 03:10. Keep at least one copy outside the host.

## 5. Verify a backup

```bash
./scripts/verify_shipsmith_backup.sh backups/<timestamp>
```

This restores the dump into a throwaway Postgres container and prints row counts. It never touches the production database.

## 6. Restore

Restore into a fresh PostgreSQL volume, not the live one:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml stop api web
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm \
  -v "$PWD/backups/<timestamp>:/backup:ro" postgres \
  sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists /backup/shipsmith.dump'
```


## 7. Recovery expectations

- The control plane can be rebuilt from a PostgreSQL backup; agents and deployed applications keep running while ShipSmith is down.
- Agents buffer deployment results and logs when Core is unreachable, then retry after reconnect.
- Restore drills should be run before relying on backups.

## 8. Multi-worker note

The offline monitor runs in the API process. Use one API worker or add a database advisory lock before scaling the API to multiple workers.
