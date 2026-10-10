# Patna inventory

`rag_properties.json` intentionally starts as an empty JSON array. Add genuine
Patna listings through the broker dashboard using
`../../examples/patna-listings-template.csv`. The upload pipeline writes to your
Supabase database directly; it does not populate this optional JSON batch file.

Alternatively, run `python build_rag_documents.py path/to/your-patna-listings.csv`
from the project root to create normalized batch documents offline, then run
enrichment and embedding as described in `../../docs/PATNA.md`.

`areas.csv` is optional. Add only sourced Patna locality coordinates, with columns
`area_name_original,city,state,latitude,longitude,source`. Unknown locations are
looked up using bounded geocoding. No property coordinates are fabricated.
