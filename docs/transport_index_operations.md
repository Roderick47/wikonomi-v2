# Transport Index operations runbook

## Priority status

### Completed through Priority 3

- Outbound WhatsApp sends are logged in `WhatsAppMessageLog` with recipient, message type, status, payload, response, error text, and timestamp.
- LLM fallback logs store `estimated_cost_usd` using configurable per-million token rates.
- The RouterEvent admin change list links to a transport dashboard that shows router-stage counts, outbound WhatsApp counts, and recent LLM cost.
- A Render cron blueprint is included for `mark_stale_cabs_offline`.
- Cab listing, profile, setup, and invalid-token pages now extend the site `base.html`.
- `/cabs/` supports server-side pagination and browser geolocation sorting.
- Driver profile setup validates image type and size and presents richer upload guidance.
- Tests cover WhatsApp send logging, LLM cost estimation, admin dashboard rendering, stale status behavior, listing privacy, contact proxying, and webhook signature handling.

### Remaining priorities

1. Deploy the Render cron job, or equivalent scheduler, and verify it runs every 5-10 minutes in production.
2. Execute real Meta Business webhook and WhatsApp Cloud API sandbox tests with production-like credentials.
3. Add richer visual design polish and SEO/schema markup for cab listing and profile pages.
4. Add map-based browsing and server-assisted distance ordering if browser-side sorting is not sufficient.
5. Add virus scanning or deeper media inspection if driver-upload volume grows.

## Required deployment configuration

### Shared cache for WhatsApp sessions

If production runs more than one worker process, use Django database cache for the transport signup wizard and other cache-backed WhatsApp state:

```bash
python manage.py createcachetable wikonomi_cache
```

Then set:

```bash
DJANGO_CACHE_BACKEND=db
```

### Stale cab cleanup scheduler

A Render cron blueprint is provided in `render.yaml`:

```yaml
services:
  - type: cron
    name: wikonomi-transport-stale-cabs
    schedule: "*/10 * * * *"
    startCommand: cd wikonomi && python manage.py mark_stale_cabs_offline --minutes 20
```

If not using Render, run this command every 5-10 minutes through cron, Celery Beat, or an equivalent scheduler:

```bash
python manage.py mark_stale_cabs_offline --minutes 20
```

The command only updates the database. It does not send outbound WhatsApp messages.

### LLM cost tracking

Set these rates from the current Anthropic pricing page whenever enabling `ANTHROPIC_API_KEY`:

```bash
ANTHROPIC_HAIKU_INPUT_COST_PER_MILLION=<input_cost_usd_per_1m_tokens>
ANTHROPIC_HAIKU_OUTPUT_COST_PER_MILLION=<output_cost_usd_per_1m_tokens>
```

If the rates are not set, token usage is still logged but `estimated_cost_usd` remains zero.

### WhatsApp webhook hardening

Set `WHATSAPP_APP_SECRET` in production so webhook POST requests must include a valid Meta `X-Hub-Signature-256` signature.

## Meta Business sandbox checklist

These steps require real Meta credentials and cannot be completed in a local CI/test-only environment:

1. Configure webhook callback URL `/whatsapp/webhook/` and verify token in Meta Business Manager.
2. Send a personal WhatsApp message to the business number and confirm a `RouterEvent` is created.
3. Send a location pin from a registered driver and confirm `CabStatus` updates to `available`.
4. Send a rider location pin and confirm the user receives an interactive list plus proxied `/cabs/<slug>/contact/` links.
5. Confirm `WhatsAppMessageLog` records both text and interactive outbound sends.
6. Confirm invalid webhook signatures are rejected when `WHATSAPP_APP_SECRET` is set.
