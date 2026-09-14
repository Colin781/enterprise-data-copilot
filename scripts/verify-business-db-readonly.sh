#!/bin/sh
set -eu

if [ -f .env ]; then
  compose_env_file=.env
else
  compose_env_file=.env.example
fi

docker compose --env-file "$compose_env_file" exec -T business-db sh -eu -c '
  export PGPASSWORD="$BUSINESS_DB_READONLY_PASSWORD"

  readonly_psql() {
    psql \
      --username "$BUSINESS_DB_READONLY_USER" \
      --dbname "$POSTGRES_DB" \
      --set=ON_ERROR_STOP=1 \
      "$@"
  }

  readonly_psql --command "SELECT dataset_version FROM northwind.dataset_manifest"
  readonly_psql --tuples-only --command "SHOW default_transaction_read_only" \
    | tr -d "[:space:]" \
    | grep -qx "on"
  readonly_psql --tuples-only --command "SHOW search_path" \
    | tr -d "[:space:]" \
    | grep -qx "northwind"

  if readonly_psql --command "CREATE TABLE northwind.p2_readonly_probe(id integer);"; then
    echo "read-only verification failed: CREATE TABLE unexpectedly succeeded" >&2
    exit 1
  fi

  if readonly_psql --command "SELECT * FROM restricted.private_notes;"; then
    echo "schema boundary verification failed: restricted schema was readable" >&2
    exit 1
  fi

  if readonly_psql --command "SELECT pg_sleep(3);"; then
    echo "timeout verification failed: three-second query unexpectedly completed" >&2
    exit 1
  fi

  echo "read-only, schema boundary, and timeout verification passed"
'
