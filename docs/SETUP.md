# Run ApnaGhar locally

Use Python 3.11 or 3.12. These instructions use PowerShell from the project folder.
The web pages can start without external accounts. Property search, AI chat and the
CRM require a configured Supabase database and at least one AI provider.

## 1. Install and create your local configuration

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/setup_local.py
```

The setup script creates `.env` and random broker/JWT/webhook secrets. It preserves
an existing `.env`. Open `.env` in your editor; keep credentials on your computer.
Virtual environment activation is optional because every command specifies Python.

## 2. Connect Supabase

Create a project in [Supabase](https://supabase.com/dashboard). Copy its project URL
and server-side `service_role` key from the API settings into:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVER_ONLY_KEY
```

The current Supabase SDK also supports server secret keys. Keep whichever server
key you use out of browser code. The server bypasses RLS to perform authorized
operations; an anon/publishable key is insufficient for this backend.
See [Supabase API key documentation](https://supabase.com/docs/guides/api/api-keys).

For a new project, open `supabase/setup.sql`, copy its contents into Supabase's
SQL Editor, and click Run. It bundles all six migrations. No credentials belong
in that SQL file. Alternatively, run these individual files in this exact order
(use one approach, not both):

1. `supabase/migrations/001_initial_schema.sql`
2. `supabase/migrations/002_broker_confirmations.sql`
3. `supabase/migrations/003_storage_setup.sql`
4. `supabase/migrations/004_customers_and_pipeline.sql`
5. `supabase/migrations/005_server_access.sql`
6. `supabase/migrations/006_patna_defaults.sql`

This creates pgvector search, listings, brokers, sessions, leads, meetings,
customers, broker confirmations, offer fields and storage buckets. Migration 005
restricts direct client table access. It also removes the original unrestricted
storage upload/delete policies. Property asset buckets are public: upload only
material intended for public listing pages, never identity or private legal files.
The old `supabase/customers.sql` is retained as a historical equivalent; migration
004 already creates that table, so do not run it separately.

To verify the database before configuring an AI provider, run:

```powershell
.\.venv\Scripts\python.exe scripts/verify_services.py --database-only
```

This reads the required tables and checks the property-search function. It does
not call an AI provider, send notifications or add property records.

## 3. Enable one AI provider

You need only one provider. Additional configured providers act as fallbacks.
Account quotas, model availability and billing depend on the provider.

| Provider | Get a key | `.env` setting |
| --- | --- | --- |
| Gemini | [Google AI Studio](https://aistudio.google.com/apikey) | `GEMINI_API_KEY` |
| Groq | [Groq Console](https://console.groq.com/keys) | `GROQ_API_KEY` |
| OpenRouter | [OpenRouter](https://openrouter.ai/settings/keys) | `OPENROUTER_API_KEY` |

Model IDs are configurable through `GEMINI_MODEL`, `GROQ_MODEL`, and
`OPENROUTER_MODEL`. The inherited model defaults are examples; select a currently
available model in your account if a provider reports that a model is unavailable.
The app uses Gemini's generateContent REST endpoint, Groq's chat SDK, and
OpenRouter's OpenAI-compatible chat endpoint. See
[Gemini documentation](https://ai.google.dev/gemini-api/docs),
[Groq quickstart](https://console.groq.com/docs/quickstart), and
[OpenRouter quickstart](https://openrouter.ai/docs/quickstart).

## 4. Add your Patna inventory and register yourself as broker

Patna inventory intentionally starts empty. Add your own genuine property records.
Follow [the Patna import guide](PATNA.md): fill
`examples/patna-listings-template.csv` with your own real records, then use the
broker dashboard CSV import. The upload validates, geocodes, embeds and stores
the listings directly in Supabase. The first embedding downloads the model.

Create your broker record using your own contact details:

```powershell
.\.venv\Scripts\python.exe scripts/fix_broker.py --name "Your Name" --email "you@example.com" --phone "YOUR_PHONE"
```

This upserts only the specified broker ID (default `broker_001`) with Patna
coverage. It does not overwrite whichever broker happens to be first in the
database. A header-only generic template also exists at `examples/properties.csv`.
For an existing database that already ran migrations 001–005, run only migration
006 to update future city defaults; existing rows keep their original cities.

## 5. Check and start

```powershell
.\.venv\Scripts\python.exe scripts/check_config.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Or run `./start.ps1` after installing requirements. Keep the server terminal open.
Stop with Ctrl+C. Restart after editing `.env` because provider settings load at
startup. If PowerShell blocks the script, use the explicit Python command above.

Open [the homepage](http://127.0.0.1:8000),
[chat](http://127.0.0.1:8000/chat),
[listings](http://127.0.0.1:8000/properties/browse), or
[broker login](http://127.0.0.1:8000/broker/login).
Username is `BROKER_USERNAME` (initially `broker`); password is `BROKER_PASSWORD`
in your local `.env`. The API documentation is at
[Swagger UI](http://127.0.0.1:8000/docs).

`/health` checks the server process. `/ready` checks configuration presence only;
it does not prove credentials are valid or migrations have run. For read-only
database checks and a small AI test request, run:

```powershell
.\.venv\Scripts\python.exe scripts/verify_services.py
```

That command reads database schema and makes one small AI completion. It sends no
email, WhatsApp, SMS or Telegram messages, and does not create meetings.

## 6. Optional integrations

| Feature | Required settings | Setup |
| --- | --- | --- |
| Email OTP and email notifications | `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` | Enable Google 2-step verification and create an [app password](https://support.google.com/accounts/answer/185833). Use an app password, not your account password. |
| Google login | `GOOGLE_OAUTH_CLIENT_ID` | Create a Web OAuth client and add `http://127.0.0.1:8000` as an authorized JavaScript origin. |
| Telegram | `TELEGRAM_BOT_TOKEN` | Create your bot with [BotFather](https://t.me/BotFather), then run `.\.venv\Scripts\python.exe interfaces/telegram_bot.py` for local polling. Disable any existing webhook first. |
| WhatsApp | `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN` | Follow [Meta's setup guide](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started). Add your own permitted test recipients. |
| Broker WhatsApp | `BROKER_WHATSAPP_PHONE`, `WHATSAPP_BUSINESS_NUMBER` | Use your own broker and business numbers, with country code. The current routing assumes Indian phone numbers. |
| Google Calendar | `GOOGLE_SERVICE_ACCOUNT_FILE`, `BROKER_GOOGLE_CALENDAR_ID` | Enable Calendar API, download a service-account JSON outside the repository or to the ignored `service_account.json`, and share your actual calendar with its service-account email with event edit permission. Use its real calendar ID. |
| Inline Calendar credentials | `GOOGLE_SERVICE_ACCOUNT_JSON`, `BROKER_GOOGLE_CALENDAR_ID` | Alternative to the file setting. JSON must be a single correctly quoted environment value. |
| SMS | `FAST2SMS_API_KEY` | Configure your own Fast2SMS account; messages depend on provider requirements and credits. |
| n8n | `N8N_LEAD_WEBHOOK_URL`, `N8N_WEBHOOK_SECRET` | Optional workflows are in `n8n/workflows`; review credentials and destinations before activating them. |

For Telegram and WhatsApp webhooks, `127.0.0.1` is not reachable by their servers.
Use your own public HTTPS deployment or a development tunnel. Set
`PUBLIC_BASE_URL` to that URL. Telegram uses `/webhook/telegram` and the
`TELEGRAM_WEBHOOK_SECRET` secret token; WhatsApp uses `/webhook/whatsapp` and
its verification token plus signed payloads. Do not run Telegram polling and a
Telegram webhook for the same bot at the same time.

## Troubleshooting

- **Chat says credentials are missing:** fill the required values and restart.
- **401 from a provider:** check the key in its account dashboard; do not log it.
- **Unknown table / column / RPC:** run all six migrations in order.
- **No homes found:** load embeddings and check that listings are available.
- **OTP request fails:** configure Gmail app password and inspect local logs.
- **Broker login unavailable:** run setup or fill `BROKER_PASSWORD` and `BROKER_TOKEN`.
- **Port 8000 in use:** stop the existing server or use `--port 8001` and update URLs.
- **Dependency install fails:** use Python 3.11/3.12 and verify internet access.
- **CSV conversion fails:** check required columns and ensure records are for Patna, Bihar.

Run one server worker. OTPs and deduplication use process memory; reminders and
broker reply context use `runtime/`. Multiple workers require shared storage and
coordination before deployment. See [deployment notes](DEPLOY.md).
