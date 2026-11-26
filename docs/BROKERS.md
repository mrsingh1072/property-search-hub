# Verified broker accounts

ApnaGhar verifies brokers. Approved brokers publish their own Patna listings
immediately; properties do not enter an approval queue.

## Finish an existing installation

1. In Supabase SQL Editor, run `supabase/migrations/007_verified_broker_accounts.sql`
   after migrations 001–006. A new project can run `supabase/setup.sql` instead.
2. Run `python scripts/setup_local.py` to add any missing local admin settings.
   Existing database and AI credentials are preserved.
3. Restart the server. Open `/admin/login` and use `ADMIN_USERNAME` and
   `ADMIN_PASSWORD` from your local `.env`. Keep these values private.
4. Open `/broker/apply` and submit the broker's real name, email, Indian phone,
   agency and verification reference. No broker password is required.
5. At `/admin`, inspect the application and verify identity, contact ownership
   and business details through your own verification process. Only then approve
   the broker. The application itself is not proof of identity.
6. The broker signs in at `/broker/login` with a one-time code sent to their approved email address. They can
   add a property, upload a CSV, and manage their own listings, leads and visits.

Registration creates a passwordless Supabase Auth identity and a pending,
inactive broker record. It sends no email. Admin approval activates the broker
through an audited database operation. Sign-in then requires a six-digit code
sent through the same Gmail SMTP configuration used for buyer codes.

Configure `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` in local `.env`. Enable Google
2-Step Verification and create an app password at
[Google App passwords](https://myaccount.google.com/apppasswords).
Use the generated app password rather than your Google account password.
See [Google's instructions](https://support.google.com/accounts/answer/185833).
Restart the server after editing settings.

Codes expire after 10 minutes, work once, and are invalidated after five wrong
attempts. Resend has a 60-second cooldown, and endpoints also limit requests per
IP. Buyer and broker codes are isolated. Email delivery failures never issue a
session. Existing approved brokers can use email codes without reapplying.
Existing password-based broker sessions must sign in again with a code.

Broker sessions are server-signed, expire after one hour, and check the linked
broker's current approval on every private request. They have a separate audience
from both customer and admin sessions. Admin credentials remain local.

The code store is process-local: run one Uvicorn worker for this local setup.
Restarting the app invalidates pending codes. Before scaling to multiple workers
or hosts, replace the store and rate limits with shared persistent storage.

## Admin account

Only these admin settings belong in local `.env`:

```dotenv
ADMIN_USERNAME=admin
ADMIN_PASSWORD=YOUR_PRIVATE_PASSWORD_AT_LEAST_12_CHARACTERS
ADMIN_SESSION_SECRET=YOUR_PRIVATE_RANDOM_SECRET_AT_LEAST_32_CHARACTERS
```

Setup generates strong private values. Do not paste them into chat, commit them,
or put the service key in browser code. Existing customer `JWT_SECRET` remains
separate. Old `BROKER_TOKEN`, `BROKER_USERNAME` and `BROKER_PASSWORD` credentials
no longer authorize broker access. Changing the admin password invalidates prior
admin sessions after the server reloads its environment.

## Access and suspension

- Pending, rejected, suspended and inactive accounts cannot access the console.
- Every staff request checks the broker's current approval, including existing sessions.
- Suspending a broker blocks further dashboard/API use; reactivation requires admin review.
- Brokers cannot read or change another broker's listings, leads, meetings, import
  jobs, image management or document management endpoints.
- Broker messaging commands require an approved active broker phone and run under
  that broker's ownership scope. Optional channel accounts still need configuration.
- Leads for selected listings go to that listing's approved owner. Meetings retain
  broker ownership. Two brokers can receive separate leads for the same buyer.
- Suspension blocks broker access; it does not automatically remove published
  properties. Admin can manage existing listings from the console.

Property images/documents are public listing assets. Do not upload identity
proofs to those buckets. A verification reference is plain text, not a private
identity-document upload facility.

Existing legacy profiles do not become approved automatically. Their brokers
must apply for individual accounts. Listings without an identifiable existing
owner stay unassigned; assign them deliberately rather than claiming another
broker's inventory. The legacy `scripts/fix_broker.py` only prints this workflow.

## Verify

```powershell
.\.venv\Scripts\python.exe scripts/verify_services.py --database-only
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Database verification checks eight tables and the property-search RPC without
sending notifications. Automated broker tests use isolated fake accounts and
database adapters; they do not create public listings or contact real people.
