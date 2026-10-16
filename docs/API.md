# ApnaGhar API

Start the local server and open [Swagger UI](http://127.0.0.1:8000/docs) for the
complete route list, request schemas and interactive examples. The machine-readable
schema is at `/openapi.json`. The application source is `api/main.py`.

## Common routes

| Method and route | Purpose | Access |
| --- | --- | --- |
| `GET /health` | Server liveness | Public |
| `GET /ready` | Configuration presence only | Public, no keys returned |
| `GET /chat` | Browser chat page | Public |
| `POST /chat` | Send a buyer message | Session ID; required server configuration |
| `GET /properties` | Search inventory | Public |
| `GET /api/properties/browse` | Filter listing cards | Public |
| `POST /shortlist` | Save a listing in a conversation session | Session ID |
| `GET /shortlist/{session_id}` | Read saved listings | Session ID |
| `DELETE /shortlist` | Remove a saved listing | Session ID |
| `POST /auth/otp/request` | Email a login code | Email integration required |
| `POST /auth/otp/verify` | Verify a single-use code and issue JWT | Email/code |
| `POST /auth/google` | Verify Google Identity credential | Google client configured |
| `GET /me` | Customer account details | `Authorization: Bearer <JWT>` |
| `POST /broker/auth` | Broker username/password sign-in | Returns shared broker token |
| `GET /broker/leads` | Broker lead list | Broker token |
| `POST /upload` | Import broker CSV | Multipart file and broker token |
| `GET /webhook/whatsapp` | Meta verification challenge | Verify token |
| `POST /webhook/whatsapp` | Incoming WhatsApp updates | Meta payload signature |
| `POST /webhook/telegram` | Incoming Telegram updates | Telegram secret header |
| `POST /webhook/n8n/lead` | Update a lead | Shared n8n secret |
| `POST /webhook/n8n/meeting` | Save a meeting | Shared n8n secret |

Broker endpoints use the `token` request field or query parameter shown in their
Swagger schema. The current UI stores this shared token in browser storage.
Customer JWTs and broker tokens are separate credentials. Do not expose either
in public screenshots, copied URLs or access logs.

## Chat example

```powershell
$message = @{
    session_id = 'web_my_random_session_id'
    message = 'Show me 2 BHK flats in Boring Road under 50 lakh'
    platform = 'web'
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat `
    -ContentType application/json -Body $message
```

Response shape:

```json
{"session_id":"web_my_random_session_id","reply":"Assistant reply","properties":[]}
```

Responses depend on your inventory and providers. An empty property array is
valid for greetings and non-search turns. Chat returns 503 with setup guidance
when database or AI credentials are absent; malformed input returns 422.

## Webhook setup

Telegram's `X-Telegram-Bot-Api-Secret-Token` header must match
`TELEGRAM_WEBHOOK_SECRET`. WhatsApp's `X-Hub-Signature-256` must be the HMAC-SHA256
signature of the exact raw request bytes using `WHATSAPP_APP_SECRET`. Meta's
verification token is a separate setting. n8n payloads contain a `secret` field
matching `N8N_WEBHOOK_SECRET`.

Account provisioning and public HTTPS callbacks are described in [SETUP.md](SETUP.md).
The API tests use mocks; they do not prove delivery to real recipients.

## Local scope

Session IDs currently act as bearer identifiers for anonymous conversations and
shortlists. Use unguessable IDs, and review ownership checks before public use.
The current broker account is shared across the installation. Multi-tenant broker
isolation, distributed OTP storage and ingress rate limits need further work for
a public production service.

The current market is Patna, Bihar. Public inventory and search stay city-scoped;
see [the Patna rollout](PATNA.md) for CSV imports and migration 006.
