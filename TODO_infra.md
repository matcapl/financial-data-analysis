# TODO — Infrastructure

Date: 2026-01-27

## Supabase Postgres (move off localhost)

Goal: switch the repo’s default database connection from local Postgres (`localhost`) to the Supabase free tier Postgres.

Context:
- `.env` currently contains both:
  - Local: `DATABASE_URL="postgresql://a:fordhouse@localhost:5432/finance"`
  - Supabase (commented): `DATABASE_URL=postgresql://...supabase.com:6543/postgres?sslmode=require`

TODOs:
- Decide whether Supabase becomes the default `DATABASE_URL` or remains optional behind an env/profile switch.
- Ensure migrations run cleanly against Supabase (schema, extensions, permissions).
- Confirm connection pool settings are appropriate for Supabase (pooler port `6543` currently noted).
- Verify any SSL settings needed (`sslmode=require` etc.).

What I need from A (if not already available):
- Confirm the Supabase connection string to use (host/user/password/dbname), or confirm the one in `.env` is current.
- Confirm whether we should:
  - store it only in local `.env` (not committed), or
  - introduce an `.env.example` entry / config flag and keep secrets out of git.
