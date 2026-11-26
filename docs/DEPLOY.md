# Deploy ApnaGhar when local checks pass

Finish [local setup](SETUP.md) first. Deployment is optional; the local workflow
never pushes code or publishes a site.

1. Create your own deployment using a Python host capable of running the ONNX
   embedding model. `Procfile` and `railway.toml` provide a start command.
2. Install `requirements.txt`. Use Python 3.11 or 3.12. Model download requires
   network access and sufficient disk/RAM; hosting quotas and prices vary.
3. Configure secrets using the host's environment manager. Do not upload `.env`
   or service-account JSON to a public repository.
4. Run all seven database migrations in the order in `SETUP.md` and load inventory.
5. Set `PUBLIC_BASE_URL` to your own HTTPS domain. Set `CORS_ORIGINS` only if a
   separate frontend origin is needed. Same-origin pages need no CORS override.
6. Run `uvicorn api.main:app --host 0.0.0.0 --port $PORT --workers 1`.
7. `/health` is process liveness; `/ready` checks configuration presence. Also
   test actual search, broker login and your optional services.

Use one worker. OTPs and message deduplication are in memory; reminder state and
broker context are stored under `runtime/`. Mount a persistent private volume at
that directory, or migrate it to a shared store before scaling. Persist the model
cache to avoid downloads on each restart. Do not run two independent reminder
schedulers against the same inventory. `ENABLE_SCHEDULER=false` disables it.

Before public use, add ingress rate limiting, review session ownership and broker
shared-account limitations, and verify real listing consent and accuracy. Public
storage buckets are for public listing images/documents only. This maintenance
pass is not a full public-production security audit.

For Telegram register `/webhook/telegram` using `TELEGRAM_WEBHOOK_SECRET` as the
Bot API secret token. Stop polling before enabling the webhook. For WhatsApp,
register `/webhook/whatsapp` using your own Meta app credentials and verification
token. Neither provider can call localhost without a public HTTPS tunnel.

See [the live checklist](LIVE_DEPLOY_CHECKLIST.md). No deployment URL or bot from
the original project is your deployment.
