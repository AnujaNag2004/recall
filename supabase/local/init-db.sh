#!/bin/sh
# Runs once, when the docker-compose database volume is first created.
set -e

run_sql() {
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$1"
}

run_sql /supabase/local/auth_stub.sql
for migration in /supabase/migrations/*.sql; do
  run_sql "$migration"
done
