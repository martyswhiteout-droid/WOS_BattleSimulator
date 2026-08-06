# shell/ — production wrapper around the untouched prototype

The shell adds auth, limits, billing, OCR, and response minimization AROUND
`wos_sim/` + `prototype/` without modifying them. Binding brief:
`shell/ARCHITECTURE.md`; rationale: `PRODUCTION_PLAN.md` §2.

## Dev run (keyless, mocked identity)

From the **repo root** (`shell.app.main` needs the repo root on `sys.path`;
running from the root provides it, and `main.py` also self-inserts it):

```
pip install -r shell/requirements.txt numpy openpyxl
uvicorn shell.app.main:app --port 8200
```

No keys → `DEV_BYPASS` auto-on: every request is `dev_user` (plan via the
`X-Dev-Plan: pro` header). Open http://localhost:8200 — the prototype UI with
the shell's account chip injected at serve time.

## Docker (staging/prod)

```
cd shell
cp .env.example .env      # fill in Clerk/Stripe/Supabase/Anthropic keys
docker compose up -d --build
```

Caddy terminates TLS for `wostests.com` / `staging.wostests.com` and proxies
to the app on 8200. Staging is the same compose file as a second stack with
its own `.env` (`ENV=staging`).

## Tests

```
python -m pytest shell/tests -q
```

All keyless: Clerk is exercised via a locally generated JWKS, Stripe/OCR are
mocked, missing agent modules degrade to no-ops.

## How releases happen (promote.py — Agent D)

`shell/promote.py` is the gate pipeline (PRODUCTION_PLAN §3): it pulls a
**tagged** prototype artifact, runs the prototype-side checks, assembles this
shell + `assets_prod/` + prod config into the Docker image above, deploys to
staging, runs the probe suite, and emits the draft Gate Report. Launch still
requires the independent QA PASS + Martin's sign-off (`PRODUCTION_CRITERIA.md`)
— the shell never ships itself.
