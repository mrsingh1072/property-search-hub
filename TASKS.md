# ApnaGhar local readiness

- [x] Rename source/UI to ApnaGhar and preserve upstream credit.
- [x] Add missing runtime dependencies and separate optional collection packages.
- [x] Generate unique local secrets without overwriting credentials.
- [x] Document all API settings and database migration order.
- [x] Include customer schema, CRM offer columns and server-side access restrictions.
- [x] Correct OTP delivery reporting, random generation and resend cooldown.
- [x] Add configuration readiness, API tests and GitHub CI.
- [ ] Supply your own Supabase and AI provider credentials.
- [ ] Run migrations in your own Supabase project and load listings.
- [ ] Verify live database and AI services.
- [ ] Connect optional channels using your own accounts.
- [ ] Publish only when explicitly requested.

Instructions: [docs/SETUP.md](docs/SETUP.md).

## Patna rollout

- [x] Switch buyer-facing content, broker forms and search to Patna/Bihar.
- [x] Keep the project, inventory templates and map configuration Patna-only.
- [x] Prepare empty Patna inventory and a header-only broker CSV template.
- [x] Add bounded geocoding, actual POI lookup and unknown-distance handling.
- [x] Add migration 006 (future city defaults only).
- [ ] Add your own genuine Patna inventory and verify live integrations.

See [docs/PATNA.md](docs/PATNA.md).
