#!/bin/sh
set -eu

if [ -z "${BUSINESS_DB_READONLY_USER:-}" ] || [ -z "${BUSINESS_DB_READONLY_PASSWORD:-}" ]; then
  echo "BUSINESS_DB_READONLY_USER and BUSINESS_DB_READONLY_PASSWORD are required" >&2
  exit 1
fi

psql \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=ON_ERROR_STOP=1 \
  --set=readonly_user="$BUSINESS_DB_READONLY_USER" \
  --set=readonly_password="$BUSINESS_DB_READONLY_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN', :'readonly_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'readonly_user')
\gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'readonly_user', :'readonly_password')
\gexec
SELECT format('ALTER ROLE %I SET default_transaction_read_only = on', :'readonly_user')
\gexec
SELECT format('ALTER ROLE %I SET search_path = northwind', :'readonly_user')
\gexec
SELECT format('ALTER ROLE %I SET statement_timeout = %L', :'readonly_user', '2s')
\gexec

REVOKE ALL ON SCHEMA public FROM PUBLIC;
SELECT format('REVOKE ALL ON SCHEMA restricted FROM %I', :'readonly_user')
\gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'readonly_user')
\gexec
SELECT format('GRANT USAGE ON SCHEMA northwind TO %I', :'readonly_user')
\gexec
SELECT format('GRANT SELECT ON ALL TABLES IN SCHEMA northwind TO %I', :'readonly_user')
\gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA northwind GRANT SELECT ON TABLES TO %I',
  current_user,
  :'readonly_user'
)
\gexec
SQL
