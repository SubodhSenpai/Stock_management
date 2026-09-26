-- One-time local database setup. Safe to re-run.
-- Run as the PostgreSQL superuser, choosing the app password on the command line:
--   psql -U postgres -h localhost -v app_password=<password> -f scripts/create_local_db.sql
-- Then use the same password in backend/.env (DATABASE_URL and TEST_DATABASE_URL).

\set ON_ERROR_STOP on

SELECT format('CREATE ROLE stocksense LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'stocksense')\gexec

SELECT 'CREATE DATABASE stocksense OWNER stocksense'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'stocksense')\gexec

SELECT 'CREATE DATABASE stocksense_test OWNER stocksense'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'stocksense_test')\gexec
