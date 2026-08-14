# THIRD_PARTY_SETUP — accounts Martin must register (agents cannot do these)

Work through top to bottom; ~60–90 min total. Paste each key into `shell/.env` (copy `shell/.env.example`). **Never commit `.env`.**

## Required (blocking real integrations)

| # | Service | What to do | Keys → `.env` | Cost | Alternatives |
|---|---|---|---|---|---|
| 1 | **Hostinger** (you have) | **FIRST: verify plan type.** hPanel → your plan. Must be a **VPS** (KVM, root SSH). Shared/Cloud website hosting CANNOT run FastAPI/Docker → if shared, decide: buy Hostinger VPS (~US$5–10/mo) or switch (Fly.io, Cloud Run — image is portable) | `VPS_HOST`, SSH key | existing | Fly.io, Cloud Run, any Docker VPS |
| 2 | **Clerk** — clerk.com | Create application "WOS Tests" → gives DEV instance now, PROD instance when domain verified. Enable email+password (+ Google social login recommended). Copy keys for dev instance first | `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_JWKS_URL` | free ≤10k MAU | Supabase Auth, Auth0, Firebase Auth |
| 3 | **Supabase** — supabase.com | Create TWO projects: `wostests-staging`, `wostests-prod`. Region: Singapore. From each: Settings→API → URL + service_role key; Settings→Database → connection string. Run `shell/db/migrations/*.sql` in the SQL editor (staging first) | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL` | free → $25/mo | Neon, Railway Postgres |
| 4 | **Stripe** — stripe.com | Create account (HK supported). Stay in TEST mode. Create product "WOS Tests Pro" US$7.99/mo (placeholder — change freely). Add webhook endpoint later when staging URL exists (URL is `https://<staging-host>/shell/webhook/stripe` — this is the ONLY path the app registers; a typo'd or guessed URL like `/shell/billing/webhook` will 401 every delivery with no visible error, see EVAL_ROUND_1.md F10); copy signing secret | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_PRO` | 2.9%+fees | Paddle (merchant of record — handles global tax), Airwallex |
| 5 | **Anthropic API** — console.anthropic.com | Create API key, set a monthly spend limit (suggest US$25 to start) — powers OCR | `ANTHROPIC_API_KEY` | pay-per-use | Google Gemini (`GEMINI_API_KEY` slot exists), OpenAI |
| 6 | **Domain DNS** (wostests.com registrar) | A records: `wostests.com` and `staging.wostests.com` → VPS IP | — | existing | — |

## Recommended

| # | Service | Why | Cost |
|---|---|---|---|
| 7 | **Cloudflare** — cloudflare.com | Put DNS behind Cloudflare (free): DDoS protection, WAF, hides VPS IP. The only realistic DDoS answer for a single VPS | free |
| 8 | **GitHub** (private repo) | Push the repo; enables CI later and offsite backup of code | free |

## Optional (defer until after launch)

| # | Service | Why |
|---|---|---|
| 9 | Sentry | Error monitoring with context; plain logs are fine at first |
| 10 | UptimeRobot | Free downtime alerts on wostests.com |
| 11 | Resend/Postmark | Custom transactional email — NOT needed initially (Clerk sends auth emails, Stripe sends receipts) |

## After keys exist (in order)

1. `shell/.env` filled (staging values) → `docker compose up` on VPS → staging.wostests.com live.
2. Stripe webhook endpoint added pointing at staging → test checkout with card `4242 4242 4242 4242`.
3. Run `python shell/probes/run_probes.py --base https://staging.wostests.com` — all must pass.
4. Then and only then: QA gate report → your sign-off → production promote.
