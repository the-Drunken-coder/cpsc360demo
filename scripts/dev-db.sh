#!/usr/bin/env bash
# Start (or reuse) the local Postgres 16 container on 127.0.0.1:5433.
set -euo pipefail
DOCKER="docker"
docker info >/dev/null 2>&1 || DOCKER="sudo docker"
if $DOCKER ps -a --format '{{.Names}}' | grep -qx cpsc360-pg; then
  $DOCKER start cpsc360-pg >/dev/null
else
  $DOCKER run -d --name cpsc360-pg --restart unless-stopped \
    -e POSTGRES_USER=cpsc -e POSTGRES_PASSWORD=cpsc -e POSTGRES_DB=cpsc360 \
    -p 127.0.0.1:5433:5432 -v cpsc360-pgdata:/var/lib/postgresql/data postgres:16 >/dev/null
fi
until $DOCKER exec cpsc360-pg pg_isready -U cpsc -d cpsc360 >/dev/null 2>&1; do sleep 1; done
echo "postgres ready at postgresql://cpsc:cpsc@127.0.0.1:5433/cpsc360"
