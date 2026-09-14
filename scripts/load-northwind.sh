#!/bin/sh
set -eu

if [ -f .env ]; then
  compose_env_file=.env
else
  compose_env_file=.env.example
fi

for migration in \
  010-northwind-schema.sql \
  020-northwind-data.sql
do
  docker compose --env-file "$compose_env_file" exec -T business-db \
    sh -eu -c '
      psql \
        --username "$POSTGRES_USER" \
        --dbname "$POSTGRES_DB" \
        --set=ON_ERROR_STOP=1 \
        --file "$1"
    ' sh "/docker-entrypoint-initdb.d/$migration"
done

docker compose --env-file "$compose_env_file" exec -T business-db \
  /docker-entrypoint-initdb.d/090-create-readonly-user.sh

echo "northwind-compact-v1 loaded"
