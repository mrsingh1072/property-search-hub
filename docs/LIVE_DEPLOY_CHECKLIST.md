# Live integration checklist

Complete [SETUP.md](SETUP.md). Check only features enabled for your own accounts.

- [ ] Required configuration check passes; no placeholder keys remain.
- [ ] All seven SQL migrations ran successfully.
- [ ] `scripts/verify_services.py` passes database and AI checks.
- [ ] Sample data is labelled; real inventory is owned, accurate and authorized.
- [ ] Automated tests and `pip check` pass.
- [ ] Local homepage, listings, broker login and chat work.
- [ ] Buyer search returns real matching listings.
- [ ] Broker CSV upload and lead updates persist.
- [ ] Email OTP arrives and can be used only once, if email is enabled.
- [ ] Telegram polling OR webhook works with your own bot, if enabled.
- [ ] WhatsApp signatures, permitted test recipients and delivery work, if enabled.
- [ ] Calendar service account can read availability and create a test visit, if enabled.
- [ ] One worker is configured and runtime state is persisted for deployment.
- [ ] Secrets, runtime data and private contacts are excluded from publication.

The automated suite mocks external services. This checklist requires actual
account-level checks and does not pass automatically when the tests pass.
