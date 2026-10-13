# ApnaGhar product plan — Patna

ApnaGhar helps buyers discover properties in Patna, Bihar, and helps brokers
manage listings, leads and site visits.

## Current scope

- Patna locality recognition, budgets, property types and buyer preferences.
- Web chat, property browsing, saved listings and a broker console.
- Broker-supplied CSV and manual property entry.
- Patna-only retrieval, bounded geocoding and approximate straight-line distances.
- Optional AI providers, messaging, email, Calendar, SMS and n8n integrations.

## Readiness

The repository starts with an empty Patna inventory. Real listings, account keys,
database setup and live integration checks are required before using it with
buyers. Automated tests use mocked external services.

## Next milestones

1. Add and verify genuine Patna inventory.
2. Test search, broker confirmation and notifications against configured accounts.
3. Add public-deployment rate limits and stronger account/session ownership checks.
4. Replace process-local coordination before multiple workers or instances.

See [Patna setup](PATNA.md), [architecture](01_ARCHITECTURE.md), and
[backlog](05_BACKLOG.md).
