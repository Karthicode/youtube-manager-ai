---
name: supabase-alembic-remote-migrations
description: Apply staged Alembic schema changes to a remote Supabase database safely by generating offline SQL and pushing through Supabase CLI migrations, including handling Alembic revision mismatch between local files and remote DB.
---

# Supabase Alembic Remote Migrations

Use this skill when:
- Alembic revisions exist in `backend/alembic/versions`.
- Target database is remote Supabase.
- `supabase/migrations` is the deployment path.
- Alembic direct remote upgrade may fail due to revision mismatch.

## Workflow

1. Ensure Supabase remote is linked and local migration history is synced.

```bash
supabase link --project-ref <project_ref> -p '<db_password>'
supabase migration fetch --linked
supabase migration list --linked
```

2. Run Alembic in offline SQL mode for the staged revision range.

```bash
cd backend
DATABASE_URL='postgresql://postgres.<project_ref>:<password>@<pooler-host>:6543/postgres?sslmode=require' \
poetry run alembic upgrade <from_revision>:<to_revision> --sql
```

3. Create a Supabase migration and apply equivalent SQL there.

```bash
cd ..
supabase migration new <descriptive_name>
```

4. Push migration to remote and verify.

```bash
supabase db push --linked --yes
supabase migration list --linked
```

## Guardrails

- Do not rely on `backend/app/config.py` defaults alone. `backend/.env` may override `DATABASE_URL`.
- For remote commands, set `DATABASE_URL` inline.
- Percent-encode special characters in DB password if used in URL.
- If Alembic errors with unknown remote revision (for example `Can't locate revision identified by ...`), do not force Alembic online migration. Use offline SQL + Supabase migration push.

## Repo reference

For concrete commands and known-good example in this repository, see:
- `docs/supabase-alembic-migration-workflow.md`

