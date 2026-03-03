# Supabase Remote Migration Workflow (Alembic + Supabase CLI)

This runbook captures the exact flow that worked in this repo on 2026-03-03.

## Why this flow

- Remote Supabase migration history is tracked by `supabase_migrations.schema_migrations`.
- Backend schema changes are authored as Alembic revisions.
- In this repo, remote `alembic_version` can diverge from local Alembic files (for example: `Can't locate revision identified by 'a3e9f5d82c12'`), so applying Alembic directly to remote may fail.
- Reliable path: generate SQL from Alembic offline, then apply via Supabase CLI migration.

## Prerequisites

- Supabase CLI installed and logged in.
- Repo linked to remote project:

```bash
supabase link --project-ref <project_ref> -p '<db_password>'
```

- Sync local `supabase/migrations` from remote before any new push:

```bash
supabase migration fetch --linked
supabase migration list --linked
```

## Important environment rule

`backend/.env` overrides `backend/app/config.py`.  
If `.env` has localhost `DATABASE_URL`, Alembic will target localhost unless you override it inline.

Always run remote Alembic commands like this:

```bash
cd backend
DATABASE_URL='postgresql://postgres.<project_ref>:<password>@<pooler-host>:6543/postgres?sslmode=require' \
poetry run alembic <command>
```

If password has reserved URL characters (`#`, `@`, `:` etc.), percent-encode it.

## Apply a staged Alembic revision to remote Supabase

Example below uses:
- from: `b80597d81f11`
- to: `c3a1f5e8d201`

1. Generate SQL from Alembic revision range (offline mode):

```bash
cd backend
DATABASE_URL='postgresql://postgres.<project_ref>:<password>@<pooler-host>:6543/postgres?sslmode=require' \
poetry run alembic upgrade b80597d81f11:c3a1f5e8d201 --sql
```

2. Create Supabase migration file:

```bash
cd ..
supabase migration new add_api_key_to_users_from_alembic_c3a1f5e8d201
```

3. Paste SQL into the new file under `supabase/migrations/`.
   - Keep schema DDL required by the Alembic change.
   - Make statements idempotent where possible (`if exists` / `if not exists`).
   - Optional but recommended in this repo: update `public.alembic_version` to the new Alembic revision.

4. Push to remote:

```bash
supabase db push --linked --yes
```

5. Verify:

```bash
supabase migration list --linked

cd backend
DATABASE_URL='postgresql://postgres.<project_ref>:<password>@<pooler-host>:6543/postgres?sslmode=require' \
poetry run alembic current
```

## What worked in this run

- Created and pushed:
  - `supabase/migrations/20260303171235_add_api_key_to_users_from_alembic_c3a1f5e8d201.sql`
- Verified on remote:
  - `users.api_key` column exists
  - `ix_users_api_key` index exists
  - `alembic_version` is `c3a1f5e8d201`
  - `supabase migration list --linked` shows `20260303171235` in both local and remote

