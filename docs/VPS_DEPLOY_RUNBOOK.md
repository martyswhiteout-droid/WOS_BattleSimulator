# VPS deploy runbook — private staging with OCR (password-gated, pre-Clerk)

> **Written 2026-08-29.** Gets the FULL shell (UI + predictions + OCR ladder + quotas) onto a
> Hostinger VPS at `staging.wostests.com`, protected by a single Caddy password until the
> Clerk/Supabase/Stripe registrations upgrade it to the real paywall. The 2026-08-29
> "Business Web Hosting" site (plum-meerkat…hostingersite.com) is SHARED hosting and cannot
> run this stack — it is not used by this runbook.

## Step 0 — what Martin buys (the only manual part)

1. Hostinger → **VPS** (separate product from website hosting) → **KVM 2** recommended
   (2 vCPU / 8 GB — matches `OCR_CPU_CONCURRENCY=2` + headroom; KVM 1 / 4 GB works for
   personal use). Region: Singapore (nearest to HK).
2. OS image: **Ubuntu 24.04 LTS** (plain, not a panel image).
3. Add your SSH public key during setup (or note the root password). Note the VPS IP.
4. DNS (at the wostests.com registrar): **A record `staging` → the VPS IP.** (TTL low, e.g.
   300, so mistakes heal fast.) Caddy's automatic HTTPS needs this to exist before first boot.

## Step 1 — one-time VPS preparation (paste as root over SSH)

```bash
apt-get update && apt-get install -y ca-certificates curl git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable" > /etc/apt/sources.list.d/docker.list
apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

## Step 2 — get the repo onto the box

If the GitHub repo is private, create a **fine-grained read-only deploy token** (GitHub →
Settings → Developer settings → Fine-grained tokens; repository access = this repo,
Contents: Read) and clone with it:

```bash
git clone https://<TOKEN>@github.com/<user>/<repo>.git /opt/wostests
cd /opt/wostests/shell
```

## Step 3 — configuration

```bash
cp .env.example .env
```

Edit `shell/.env` on the VPS — interim values (password-gated dev mode):

```
ENV=dev                # bypass auth; pro by default — the Caddy password IS the gate
OCR_MOCK=0             # real reads
# GEMINI_API_KEY=...   # optional: enables gap-fill; leave unset for zero-spend RapidOCR-only
```

Edit `shell/Caddyfile` ON THE VPS ONLY (do not commit this edit): in the
`staging.wostests.com` block, add the password gate as the FIRST directive. Generate the
hash, then paste it in:

```bash
docker run --rm caddy:2-alpine caddy hash-password --plaintext 'CHOOSE-A-LONG-PASSWORD'
```

```caddyfile
staging.wostests.com {
	basic_auth {
		martin <PASTE-THE-HASH>
	}
	# ...existing directives unchanged...
}
```

> Why this is safe: in dev mode every visitor would be a pro user (the localhost
> convenience, PRODUCTION_CRITERIA C6) — the Caddy password prevents any visitor existing.
> When Clerk/Supabase/Stripe keys land: set `ENV=staging` + the real keys in `.env`, delete
> the `basic_auth` block, `docker compose up -d` again — the real paywall takes over and C6
> is satisfied the intended way.

## Step 4 — launch

```bash
cd /opt/wostests/shell
docker compose up -d --build     # first build ~3-6 min (installs rapidocr/onnxruntime)
docker compose ps                # both services healthy
docker compose logs app | tail -20
```

## Step 5 — smoke checks (from any machine)

```bash
curl -u martin:PASSWORD https://staging.wostests.com/shell/health
# {"status":"ok","env":"dev",...}
```

Then in a browser: `https://staging.wostests.com` (basic-auth prompt) → hard refresh →
**Fill from screenshots** → run the walkthrough in `docs/OCR_TEST_INSTRUCTIONS.md` §3
(the pro DevTools header is unnecessary — dev mode is pro by default). Expect the
digit-exact table. Real-device mobile pass = the same URL on your phone.

## Updating the deployment later

```bash
cd /opt/wostests && git pull && cd shell && docker compose up -d --build
```

(The Caddyfile basic_auth edit is local to the VPS; `git pull` may conflict on it if the
committed Caddyfile changes — re-apply the block if so.)

## Ops notes

- Logs: `docker compose logs -f app` · restart: `docker compose restart app`.
- The quota DB is in-memory in dev mode (resets on restart) — fine for a password-gated
  single user; Supabase makes it real later.
- Backups/snapshots: enable Hostinger VPS snapshots once things work.
- The engine demo on Vercel is unaffected; retire or redirect it whenever you like.

## INTERIM DEPLOYMENT — LIVE since 2026-08-29 (Cloudflare Tunnel, $0)

The VPS above is DEFERRED (owner choice). What is actually serving today:

- **https://staging.wostests.com** → Cloudflare Tunnel `wos-pc` → `localhost:8200` on the
  owner's PC (app in dev mode, pro-by-default).
- **Gate:** Cloudflare Access self-hosted app "WOS Tests staging" — Allow policy on the
  owner's email only (one-time-PIN login; team domain `cold-morning-ab99.cloudflareaccess.com`).
  Verified: every unauthenticated request 302s to the Access login; the dev pro-default never
  faces the public (C6 posture held by Access instead of Caddy basic_auth).
- **Auto-start:** `%APPDATA%\...\Startup\wos-staging.vbs` → runs
  `C:\Users\Martin\wos-ops\start_app.bat` (uvicorn :8200, --env-file shell/.env) and
  `start_tunnel.bat` (cloudflared with the tunnel token — token lives ONLY in that local file,
  outside every repo; rotate it in Zero Trust → Networks → Tunnels if ever exposed).
- **Limits of this mode:** up only while the PC is on and the owner is logged in; quotas are
  in-memory; keep GEMINI_API_KEY unset here unless fuzzier budget-reset-on-restart is accepted.
- Moving to the VPS later: run the runbook above, then just repoint — either delete the
  tunnel route and add the `A staging → VPS` record, or keep Cloudflare proxying to the VPS.
