# ApnaGhar retrieval pipeline — Patna

## Ingestion

Use broker CSV upload or manual Add property. A batch CSV can also be converted
with `build_rag_documents.py` into `data/patna/rag_properties.json`.
Required CSV fields are `property_type`, `price_inr` and `address`.

Validation rejects unsupported cities and states. Normalization assigns Patna and
Bihar. Stable external references are scoped to the broker and active market.
Geocoding and POI enrichment run only for accepted Patna coordinates. The semantic
text is embedded with a local 384-dimensional FastEmbed model, then stored in
Supabase with listing metadata.

## Retrieval

1. Extract grounded buyer criteria and normalize Patna locality aliases.
2. Reject an explicitly unsupported city.
3. Embed the query and call `match_properties` with `filter_city=Patna`.
4. If needed, broaden area/BHK criteria while retaining Patna.
5. Deduplicate and exclude already-shown IDs.
6. Apply named-landmark distances, ranking and connectivity preferences.
7. Format actual listing fields for grounded assistant replies and cards.

## Map data

The geocoder uses a bounded Patna search, cached Photon/Nominatim results and
optional sourced locality coordinates. City-centre fallbacks are rejected.
Nearby POIs are queried through Overpass, cached, and checked against the market
search envelope. Distances are approximate straight-line kilometres. Missing
coordinates, failed requests and unavailable POIs remain unknown.

The search envelope is an application coverage setting, not an administrative
boundary. Map metadata does not establish transport operating status or legal
property verification. See [Patna setup](PATNA.md) for provider settings and usage
limits.

No property documents are shipped as live inventory. Add genuine records before
expecting search results.
