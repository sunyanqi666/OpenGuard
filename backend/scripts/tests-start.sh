#! /usr/bin/env bash
set -e

# Never run destructive test fixtures against the development database.
TEST_DATABASE_URL="${DATABASE_URL%/*}/app_test"
export TEST_DATABASE_URL
python -c 'import os, psycopg; url=os.environ["DATABASE_URL"].rsplit("/", 1)[0] + "/postgres"; conn=psycopg.connect(url, autocommit=True); conn.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()", ("app_test",)); conn.execute("DROP DATABASE IF EXISTS app_test"); conn.execute("CREATE DATABASE app_test"); conn.close()'
DATABASE_URL="$TEST_DATABASE_URL" alembic upgrade head
export DATABASE_URL="$TEST_DATABASE_URL"

bash scripts/test.sh "$@"
