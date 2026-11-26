# Patna rollout

ApnaGhar now serves **Patna, Bihar**. There are intentionally **no Patna listings**
in the repository yet. This project contains only the Patna application, empty
inventory files, and templates for your own real records.

## What changed

- Web pages, chat prompts, examples, broker forms, notifications and Calendar
  locations use Patna.
- Patna neighbourhoods and spelling aliases are recognized in intent extraction.
- Search, fallback search, public browse, featured homes and displayed favourites
  stay scoped to Patna. Explicit requests for another city return no results;
  they are not silently rewritten to Patna.
- New CSV uploads default to Patna/Bihar and reject an explicit different city
  or state. Stable import IDs include Patna and the broker ID, avoiding collisions
  with listings that use the same reference under a different broker.
- `city_config.py` defines the active city, localities, geocoding search envelope
  and current batch-inventory path. It is a single-market deployment.
- New browser conversation and saved-listing keys use a Patna namespace, leaving
  the previous browser data in place.
- Coordinates outside the configured Patna search envelope are rejected. Optional
  locality coordinates must be sourced and declared as Patna.
- Nearby POIs come from OpenStreetMap queries around the actual coordinates.
  Missing POIs or service failures leave distances null. Distances are approximate
  straight-line measurements, not route distances or travel times. OSM tags are
  not proof of transit operating status; check a transport operator before relying
  on service availability.

## Add your first real listings

1. Connect your own Supabase project and AI provider as described in [SETUP.md](SETUP.md).
2. For a new database run `supabase/setup.sql`. If migrations 001–005 were already
   applied, run only `supabase/migrations/006_patna_defaults.sql`. It changes future
   defaults, not existing property or lead rows. Also apply migration 007 for
   individual broker accounts if it is not installed. No remote migration was applied
   automatically by this local change.
3. Copy `examples/patna-listings-template.csv` and add genuine listing rows.
   `property_type`, `price_inr` and `address` are required; `bhk`, `city`,
   `area_sqft`, `furnishing`, `amenities` and broker details are optional.
   Fill `city` with `Patna` or leave it blank to use Patna. Prices are full rupees,
   not lakh/crore units. Put comma-separated amenities inside CSV quotes.
4. Apply at `/broker/apply` and obtain admin approval first ([broker guide](BROKERS.md)).
   Then use `/broker/login` → CSV import or Add property. Broker uploads validate,
   geocode, embed and write directly to Supabase. You do not need to copy uploaded
   rows into the local JSON batch file.
5. Verify the uploaded listing in `/properties/browse` and try a search such as
   “2 BHK in Boring Road under 70 lakh.” This is an example query, not a claim
   that a listing at that price exists.

For registration checks use the official
[Bihar RERA registered-project directory](https://rera.bihar.gov.in/RegisteredPP.aspx).
Registration is not a live listing, an availability guarantee, or a substitute for
checking the actual property's details. Only add sourced and checked listing
records; generated text is not verified inventory.

## Optional batch JSON inventory

`data/patna/rag_properties.json` starts as `[]`. Advanced users may populate it
with normalized, sourced Patna property documents and run:

```powershell
.\.venv\Scripts\python.exe enrichment/enrich_properties.py --limit 5
.\.venv\Scripts\python.exe embeddings/generate_embeddings.py --limit 5
```

Both scripts read the Patna file and reject other-city records. With an empty
inventory, embedding exits without accessing Supabase or downloading a model.
To build normalized JSON from a filled Patna CSV without contacting external
services, run:

```powershell
.\.venv\Scripts\python.exe build_rag_documents.py path/to/your-patna-listings.csv
```

The converter validates all rows before replacing the batch JSON file. A CSV
with only headers produces an empty JSON array. Broker dashboard uploads remain
the direct route to storing and indexing real listings in Supabase.

Check normalized JSON without changing files or contacting services:

```powershell
.\.venv\Scripts\python.exe scripts/validate_data.py
```

## Map-service operation

Review the [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/)
before real imports. Its public server permits at most one request per second,
requires an identifying user agent, attribution and cached results, and is not
for heavy or regular bulk geocoding. The code spaces Nominatim calls by at least
1.1 seconds and persists successful lookups under ignored `runtime/`.
Use one process/machine for imports and avoid concurrent app/CLI geocoding.
Use your own provider for sustained ingestion. `NOMINATIM_DOMAIN`, `PHOTON_URL`,
`OVERPASS_URL` and `GEOCODER_USER_AGENT` can be changed in `.env` without a code
change. Add appropriate contact information to your user agent for deployment.

Photon and Overpass queries use public map-service endpoints and depend on their
availability and data completeness. POI results are cached for seven days.
No live map, AI or database request is required by the automated Patna tests;
all network boundaries are mocked. Real listing ingestion remains to be tested
once your own inventory and credentials are supplied.
