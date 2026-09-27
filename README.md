# ApnaGhar — AI Property Assistant

A conversational property discovery and broker CRM application for Patna,
India. Buyers search listings in natural language, save favourites, and request
site visits. Brokers manage inventory, leads, offers and visit confirmations.

**Stack:** Python 3.11 · FastAPI · Supabase/PostgreSQL + pgvector · FastEmbed/ONNX ·
Gemini/Groq/OpenRouter · HTML/CSS/JavaScript.

[Patna rollout and listings](docs/PATNA.md) · [Local setup and API keys](docs/SETUP.md) · [API guide](docs/API.md) ·
[Architecture](docs/01_ARCHITECTURE.md) · [Deployment](docs/DEPLOY.md) ·
[Attribution](NOTICE.md)

## Features

- Natural-language property search with local 384-dimensional embeddings,
  metadata filters, hybrid retrieval and ranking.
- Browser chat, property cards, browse filters and saved favourites.
- Buyer requirement collection and lead capture.
- Broker dashboard, lead pipeline, offer notes, analytics and CSV imports.
- Broker confirmation and rescheduling flows for property visits.
- Optional WhatsApp, Telegram, email, Google login, Calendar, SMS and n8n adapters.
- Provider fallback: Gemini → Groq → OpenRouter, using your own account keys.

Patna inventory intentionally starts empty. Add your genuine listings using
`examples/patna-listings-template.csv` through the broker dashboard. Validate listings, images, prices
and legal details before using them with real buyers. Optional services require their own accounts;
this repository contains no working production API keys or deployed demo.

## Run locally (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/setup_local.py
```

Open `.env` and add `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and at least one
of `GEMINI_API_KEY`, `GROQ_API_KEY`, or `OPENROUTER_API_KEY`.
Run the six SQL migrations listed in [the setup guide](docs/SETUP.md), then:

```powershell
.\.venv\Scripts\python.exe scripts/check_config.py
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

On macOS/Linux, use `python3 -m venv .venv` and `.venv/bin/python` instead.
The first real listing import downloads an embedding model; later imports use its
local cache. See the Patna guide for broker uploads and optional JSON batch imports.
The pages and API documentation start without keys; chat explains missing
configuration until database and AI settings are present.

| Page | Local URL |
| --- | --- |
| Home | http://127.0.0.1:8000/ |
| Chat | http://127.0.0.1:8000/chat |
| Listings | http://127.0.0.1:8000/properties/browse |
| Broker login | http://127.0.0.1:8000/broker/login |
| Interactive API docs | http://127.0.0.1:8000/docs |
| Process health | http://127.0.0.1:8000/health |
| Configuration readiness | http://127.0.0.1:8000/ready |

Broker username defaults to `broker`; use the generated `BROKER_PASSWORD` in
`.env`. Restart after changing environment values. You can use `./start.ps1`
for later launches after installing dependencies.

## Configuration

| Integration | Requirement |
| --- | --- |
| Supabase | Required for inventory, sessions, customers and CRM |
| Gemini, Groq or OpenRouter | At least one for AI chat and extraction |
| FastEmbed | Local model downloaded on first embedding/search operation |
| Gmail | Optional email OTP and email alerts |
| Google OAuth client | Optional browser Google login |
| WhatsApp Cloud API | Optional WhatsApp channel; public HTTPS webhook required |
| Telegram | Optional bot; local polling or public HTTPS webhook |
| Google Calendar | Optional service-account calendar access |
| Fast2SMS / n8n | Optional SMS and workflow integrations |

`.env.example` documents all settings. `scripts/setup_local.py` generates local
secrets and never overwrites an existing `.env`. `scripts/check_config.py` reports
configuration without printing keys. `scripts/verify_services.py` reads the schema
and makes a small AI request; it sends no notifications.

## Verify changes

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The automated suite covers broker authorization, upload validation, browse
validation, CRM analytics, meeting confirmation/rescheduling, location enrichment,
OTP delivery/lockout, setup secrets, configuration readiness, AI fallback, Patna
city isolation, locality aliases, bounded geocoding and unknown-distance behavior.
External requests in these test cases are mocked. Passing tests do not verify
your live accounts, deployed webhook delivery or a real calendar booking.
GitHub Actions runs the suite on Python 3.11 and 3.12 when you later publish.

All Patna CSV conversion and validation tools use the runtime requirements.
The optional requirements alias remains available:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-data.txt
```

## Project layout

```text
api/                 FastAPI routes, customer authentication, HTML templates
agent/               Conversation, intent extraction, lead and visit workflows
broker/              CSV validation, ingestion and listing management
database/            Supabase queries and persistence
embeddings/          Local model and inventory embedding pipeline
rag/                 Retrieval, ranking and grounded conversation prompts
enrichment/          Geocoding and nearby points of interest
notifications/       Email, WhatsApp, SMS, Calendar and reminders
interfaces/          Telegram polling client
supabase/migrations/ Ordered database setup and access restrictions
city_config.py       Active Patna market and geocoding configuration
data/patna/          Empty Patna batch inventory and optional locality coordinates
examples/            Minimal listing CSV example
scripts/             Local setup, diagnostics and optional collection tools
tests/               Automated tests
.github/workflows/   CI configuration
```

## Operating limits

Run a single worker. OTP and message deduplication state is held in memory;
reminders and broker reply context persist under ignored `runtime/`. This design
needs shared state before horizontal scaling. The broker console uses one shared
broker account, not a complete multi-tenant authorization system. Add deployment
rate limiting and review session ownership before opening it to public traffic.

Secrets, OAuth tokens, runtime state and the virtual environment are ignored by
Git. Property asset buckets are public; use them only for public listing assets.
Provider availability, quotas and charges are controlled by their respective
services. The project does not guarantee legal verification of listings.

## Your GitHub version

Suggested repository name: `apnaghar-ai`. Keep credentials in `.env`, preserve
[contributor attribution](NOTICE.md), and review the file list before publishing.
No GitHub push is required to run or test locally. Nothing in the setup scripts
creates a repository or pushes code. See [the later publishing guide](docs/GITHUB.md).
