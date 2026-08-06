# Privacy Policy — WOSTests.com

> **DRAFT — lawyer review before launch. Not yet in force.**
> Prepared 2026-08-04 (PRODUCTION_CRITERIA F4). Framed for the Hong Kong
> Personal Data (Privacy) Ordinance (PDPO) and written to be GDPR-aware,
> since EU players can sign up.

**Data user / controller:** [Martin Ling / legal entity TBD], Hong Kong SAR
**Contact:** [privacy email TBD]

## 1. The short version

We store as little as we can: your email (through our sign-in provider),
your subscription state (through Stripe), the battle setups you run, and —
if you use screenshot import — your uploaded screenshots for a limited time.
We do not sell personal data. We do not show your uploads to anyone else.

## 2. What we collect and why

| Data | Where it lives | Why (purpose) | Kept for |
|---|---|---|---|
| Email address, sign-in identity | **Clerk** (our auth provider); mirrored in our database for account joins | Account creation, login, email verification, service notices | Life of the account + [30] days |
| Subscription and payment status (plan, period end, Stripe customer ID) | **Stripe** and our database | Billing, entitlements. **We never see or store card numbers** — Stripe handles all card data | Life of the account + statutory accounting periods |
| Usage events (endpoint called, timestamp, hashed IP, hashed request fingerprint, troop totals) | Our database (Supabase Postgres) | Quota enforcement, abuse and model-extraction detection (ToS §6), service health | [12] months, then aggregated or deleted |
| Battle setups / saved scenarios you create | Our database | So the tool works and you can revisit your scenarios | Until you delete them or close the account |
| Uploaded battle-report screenshots + extracted fields | Our storage + database | To read the battle data out of the image for you (the OCR feature) | **Screenshots deleted after [30] days** ("N days" — final number set at launch and stated here); extracted fields kept with your scenario |
| Basic server logs (IP, user agent, status codes) | Our VPS | Security, debugging | [30] days |

We do **not** collect: card numbers, precise location, contacts, advertising
identifiers. We run no third-party advertising or tracking pixels.

## 3. Legal bases (GDPR-aware)

Where GDPR applies: contract performance (running the Service, billing),
legitimate interests (abuse prevention, security, protecting the prediction
model from extraction — balanced against your rights), and consent where
required (e.g. non-essential emails). Under the PDPO, collection is limited
to what is necessary for these stated purposes, and we will not use personal
data for a new purpose without consent.

## 4. Processors we rely on

- **Clerk** — authentication and user management.
- **Stripe** — payments (PCI compliance stays with Stripe).
- **Supabase** — managed Postgres database hosting.
- **Anthropic** (and possibly Google as fallback) — the vision model that
  reads your uploaded screenshot. The image is sent for extraction only; we
  have API terms that do not permit these providers to train on it.
- **Hostinger** — server hosting. [Cloudflare — DDoS protection, if enabled.]

Some of these process data outside Hong Kong (typically the US/EU). We rely
on the providers' standard contractual safeguards; details available on
request.

## 5. Your rights

- **PDPO:** you may request access to, and correction of, your personal
  data. We may charge only what the PDPO permits for access requests.
- **GDPR (where it applies):** access, rectification, erasure, restriction,
  portability, and objection (including to legitimate-interest processing);
  complaint to your supervisory authority.
- Practical version for everyone: email [privacy email TBD] and we will
  show you what we hold, fix it, or delete your account and its data —
  normally within 30 days.

## 6. Security

Transport is HTTPS-only. Secrets live in server environment variables, not
code. Database access is server-side only with row-level security as
defense-in-depth. IPs in usage events are stored hashed. Backups are
encrypted at the provider. No system is perfectly secure; if a breach
creates real risk to you, we will notify you and the Privacy Commissioner /
relevant authority as required.

## 7. Children

The Service is not directed at children under 16, and we do not knowingly
collect their data. If you believe a child has an account, contact us and
we will delete it.

## 8. Changes

We will post changes here and, for material changes, notify you in the app
or by email at least 14 days in advance.

---

*Draft notes for counsel (delete before publication):*
- *Replace bracketed retention numbers with final values; "N days" for
  screenshots must match the implemented deletion job before launch.*
- *Confirm PDPO data-user identification requirements and whether a formal
  Personal Information Collection Statement (PICS) must be shown at signup.*
- *Verify Anthropic/Google API data-use terms still say no-training at
  launch, and whether cross-border transfer language needs strengthening if
  PDPO s.33 is brought into force.*
