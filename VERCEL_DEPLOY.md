# Vercel Hobby Demo

This repo is configured for a Vercel Hobby deployment via the root `app.py`
FastAPI entrypoint.

## Deploy

```powershell
npx vercel login
npx vercel deploy --prod
```

The Hobby demo is capped at 1,000 simulations per `/api/predict` request. The
front-end only offers 1,000 runs, and the API rejects direct requests above that
limit with a clean 400.

## Files

- `app.py` - Vercel FastAPI entrypoint.
- `vercel.json` - install command and 300 second Hobby max duration.
- `requirements-vercel.txt` - runtime-only dependencies.
- `.vercelignore` - excludes the local venv and scratch/dev folders.
