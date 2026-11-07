# Recall

*Your AI memory and action layer for everything you save.*

> Everyone saves hundreds of posts, videos and docs but almost never acts on them. Recall is a multi-agent AI system that turns saved content into context-aware micro-actions, surfaces the right save at the right moment, and tracks whether your saves actually change your behavior.

**Status:** in active development. Live demo, screenshots, architecture diagrams and eval results will be added as their build phases land; see [the build spec](RECALL_PROJECT_SPEC.md).

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, TanStack Query |
| Backend | FastAPI, Pydantic v2, async SQLAlchemy |
| Database | Supabase Postgres, pgvector, row-level security |
| Auth | Supabase Auth (email and Google), with tokens verified in the API via JWKS |
| Testing | Vitest + Testing Library, pytest + httpx on embedded Postgres, migration tests on PGlite |
| CI | GitHub Actions |

## Local setup

Needs Node 20.9+, [uv](https://docs.astral.sh/uv/), and optionally Docker.

```bash
make setup
```

```bash
make dev-web
```

```bash
make dev-api
```

The web app runs on http://localhost:3000 and the API on http://localhost:8000 (docs at `/docs`).

To run the web app, API and a local Postgres together in Docker instead:

```bash
make up
```

Run lint, type checks and all tests with:

```bash
make check
```

Sign-in needs a free Supabase project; [DEPLOYMENT.md](DEPLOYMENT.md) has the steps. The landing page runs without one.

Configuration lives in environment variables; see [.env.example](.env.example). To deploy, follow [DEPLOYMENT.md](DEPLOYMENT.md).

## Repository layout

```
apps/web/             Next.js frontend
apps/api/             FastAPI backend
supabase/migrations/  SQL schema and row-level security policies (source of truth)
supabase/local/       Stand-in for Supabase's auth schema, for plain Postgres
supabase/tests/       Migration and tenant-isolation tests
```

## Key engineering decisions

- **SQL migrations are the single source of truth for the schema.** They hold pgvector indexes and RLS policies that an ORM autogenerator handles poorly, so SQLAlchemy maps onto the schema rather than generating it.
- **API requests run as the signed-in user.** Each request opens a transaction under the `authenticated` Postgres role with that user's claims, so row-level security applies to the API too. A handler with a missing check still can't read another workspace.
- **The API holds no signing secret.** It verifies tokens against the project's public keys and refuses tokens whose algorithm or issuer doesn't match, which blocks algorithm-confusion attacks.
- **Tenant isolation is enforced by the database, and tested.** Every table has RLS on, and composite foreign keys stop a row carrying a different `workspace_id` than its parent save. `supabase/tests/` proves this with real `SET ROLE` queries, on an in-process Postgres that needs no Docker.

## License

[MIT](LICENSE)
