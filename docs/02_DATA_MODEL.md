# ApnaGhar data model — Patna

SQL migrations in `supabase/migrations/` are authoritative. A new installation can
run the generated `supabase/setup.sql`; an existing installation should apply only
missing migrations in sequence.

| Table | Purpose |
| --- | --- |
| properties | Normalized listing JSON, 384-dimensional embedding, metadata and status |
| brokers | Broker contact details and locality coverage |
| sessions | Conversation messages, requirements and stage |
| leads | Buyer requirements, contact information, pipeline state and offer notes |
| meetings | Visit schedule, status, reminders and outcome |
| customers | Email/Google account details and saved property IDs |
| broker_confirmations | Pending broker acceptance and rescheduling context |

New property and lead city defaults are Patna. Uploads and database write helpers
require explicit Patna inventory; the upload pipeline assigns Bihar. `match_properties`
is called with the Patna filter. Displayed favourites and featured listings are
also scoped to Patna.

A normalized document includes `doc_id`, `source_ids`, `location`,
`property_profile`, `pricing`, `amenities`, `connectivity`, `transaction` and
`metadata`. Example location shape:

```json
{"city":"Patna","state":"Bihar","area_name":"Boring Road"}
```

That is a schema illustration, not a listing. Inventory starts empty. A missing
distance is JSON null, never zero or a fabricated number. Real property assets
are stored in the configured public buckets; upload only material intended for
public listing pages.

See [Patna import instructions](PATNA.md).
