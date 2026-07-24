# Vercel Hobby Demo

This repo is configured for a Vercel Hobby deployment via the root `app.py`
FastAPI entrypoint.

## Deploy

One command (logs in only when needed, then deploys):

```powershell
.\deploy-vercel.ps1
```

Or manually:

```powershell
npx vercel login
npx vercel deploy --prod
```

The Hobby demo is capped at 1,000 simulations per `/api/predict` request at the
API level (direct requests above that get a clean 400). The front-end offers
only 10 / 50 / 100 runs (default 10), and enforces a 1,000-troop minimum in
both Total-troops fields.

## Files

- `app.py` - Vercel FastAPI entrypoint.
- `vercel.json` - install command and 300 second Hobby max duration.
- `requirements-vercel.txt` - runtime-only dependencies.
- `.vercelignore` - excludes the local venv and scratch/dev folders.
