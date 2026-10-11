#!/usr/bin/env bash
# Invoked from the application deployment directory after staging .*.env.next.
set -euo pipefail
umask 077
exec 9>.deploy.lock
flock -n 9 || { echo 'Another MacroMapper deployment is running.'; exit 1; }

for file in .env.next .backend.env.next; do
  [ -f "$file" ] && [ ! -L "$file" ] || { echo "Missing regular staged file: $file"; exit 1; }
  chmod 600 "$file"
done
for file in .env .backend.env db.sqlite3 backups; do
  [ ! -L "$file" ] || { echo "Refusing symlink: $file"; exit 1; }
done
if [ -e db.sqlite3 ] && [ ! -f db.sqlite3 ]; then
  echo 'db.sqlite3 must be a regular file, not a directory.'
  exit 1
fi
docker network inspect macromapper-ingress >/dev/null
docker inspect notoli-proxy --format '{{range .Mounts}}{{if eq .Destination "/etc/nginx/conf.d/macromapper.conf"}}{{.Source}}{{end}}{{end}}' \
  | grep -Fx "$PWD/nginx-shared.conf" >/dev/null || {
    echo 'Install the persistent Notoli override with the correct vhost path first.'
    exit 1
  }
docker exec notoli-proxy nginx -t

compose_next() {
  MACROMAPPER_BACKEND_ENV_FILE=.backend.env.next docker compose --env-file .env.next \
    -f docker-compose.yml -f docker-compose.shared.yml "$@"
}
compose() {
  docker compose -f docker-compose.yml -f docker-compose.shared.yml "$@"
}

compose_next config --quiet
compose_next pull macromapper-backend macromapper-frontend
# Only initialize a missing file. Existing data is never truncated.
if [ ! -e db.sqlite3 ]; then
  : > db.sqlite3
fi
chmod 600 db.sqlite3
mkdir -p backups
chmod 700 backups
recovery="$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir "backups/$recovery"
for file in .env .backend.env; do
  if [ -f "$file" ]; then
    chmod 600 "$file"
    cp -p "$file" "backups/$recovery/$file"
  fi
done
# Stop writers before taking a consistent SQLite backup and running migrations.
compose_next stop macromapper-backend
if [ -s db.sqlite3 ]; then
  compose_next run --rm --no-deps -T -v "$PWD/backups/$recovery:/recovery" macromapper-backend python - <<'PY'
import sqlite3
with sqlite3.connect("file:/backend/db.sqlite3?mode=ro", uri=True) as source:
    with sqlite3.connect("/recovery/db.sqlite3") as destination:
        source.backup(destination)
        if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Recovery database failed its integrity check.")
PY
  chmod 600 "backups/$recovery/db.sqlite3"
fi
mv .env.next .env
mv .backend.env.next .backend.env
compose run --rm --no-deps -T macromapper-backend python manage.py check --deploy
compose run --rm --no-deps -T macromapper-backend python manage.py migrate --noinput
compose up -d macromapper-backend macromapper-frontend
docker exec notoli-proxy nginx -t
docker exec notoli-proxy nginx -s reload
cp .env deployed-release.env
chmod 600 deployed-release.env
echo "Recovery files: $PWD/backups/$recovery"
echo 'Deployment started. Complete the documented HTTPS and application smoke tests.'
