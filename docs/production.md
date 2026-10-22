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

## 2. Build, migrate, then start

**Never start new application containers before migrations have run.** The order is:

```bash
# 1. build images (no containers are started)
docker compose --env-file .env.production -f docker-compose.prod.yml build

# 2. back up the existing database (skip only for a first-time install)
./scripts/backup_shipsmith.sh

# 3. run migrations with the new image; postgres is started automatically
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm api migrate

# 4. start the stack
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
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

Production runs with `RUN_MIGRATIONS=0`; migrations are explicit and run with the **new** image before new containers start. The `migrate` entrypoint subcommand enters the database package directory and runs Alembic:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm api migrate
```

Use the same command for a first-time install and for upgrades. Always back up before migrating an existing database.

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

For a first isolated Core drill, run `bash scripts/drill_shipsmith_core.sh`. It creates a uniquely named Compose project and temporary PostgreSQL volume, then checks build, migration, API health, backup, isolated restore, and a repeated migration. It removes only that temporary project and volume on exit. The drill does **not** test an application rollback or a real Agent process losing its connection; test those separately in staging before a production release. The in-process Core outage/reconnect regression is `pytest apps/api/tests/test_outbox_reconnect.py`.

## 6. Disaster restore (never use for a drill)

The following procedure **deletes and replaces the target database**. It is for actual disaster recovery, not rehearsal. Before running it, record the exact Compose project and database names, confirm that the backup belongs to that environment, run `./scripts/verify_shipsmith_backup.sh backups/<timestamp>`, and get an operator approval. For a rehearsal use Section 5 instead. Stop the application containers first, then restore into the running postgres service:

```bash
# 1. stop app containers; postgres keeps running
docker compose --env-file .env.production -f docker-compose.prod.yml stop api web

# 2. copy the dump into the postgres container
docker compose --env-file .env.production -f docker-compose.prod.yml cp backups/<timestamp>/shipsmith.dump postgres:/tmp/shipsmith.dump

# 3. recreate the database and restore; note sh -c quoting so variables expand inside the container
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T postgres \
  sh -c 'dropdb --if-exists --force -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T postgres \
  sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error /tmp/shipsmith.dump'

# 4. start the app again
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

After restore, verify `alembic_version`, project/deployment row counts, login, and Agent reconnect before allowing new deployments. If restore fails, leave API and web stopped; do not start them against a partially restored database.

If you are restoring onto a completely new PostgreSQL instance, restore globals first with `psql` (the `shipsmith-globals.sql` file is plain SQL), then restore the data dump with `pg_restore`. Do not run a restore against a database that still contains data you need.

## 7. Recovery expectations

- The control plane can be rebuilt from a PostgreSQL backup; agents and deployed applications keep running while ShipSmith is down.
- Agents buffer deployment results and logs when Core is unreachable, then retry after reconnect.
- **Rollback is a re-deploy of an earlier commit/image; it never undoes database migrations.** Database migrations must stay backward-compatible.
- **A failed health check marks the deployment as failed; it does not roll back containers automatically.** Recover with a manual rollback or a new deployment.
- Restore drills should be run before relying on backups.

## 8. Multi-worker note

The offline monitor runs in the API process. Use one API worker or add a database advisory lock before scaling the API to multiple workers.
