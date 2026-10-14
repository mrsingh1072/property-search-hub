# ApnaGhar conversation flow — Patna

1. Greet the buyer and collect the necessary profile details.
2. Extract budget, locality, bedrooms/property type, amenities and proximity needs.
3. Ask for missing criteria before searching.
4. Retrieve and rank matching Patna listings.
5. Show grounded property details and save the buyer's favourites when requested.
6. Collect visit intent and contact information.
7. Request broker confirmation, then confirm or negotiate a new time.

The intent extractor recognizes Patna localities such as Boring Road,
Kankarbagh, Bailey Road, Danapur and Patliputra Colony, including spelling aliases.
A locality belongs in `area`, not `city` or `named_landmark`. A specific named
institution belongs in `named_landmark` only when grounded in the buyer's message.

Changing locality clears stale location constraints. Asking for more areas broadens
the search within Patna. A request outside the supported market returns no results
rather than silently changing its city.

Example conversation, with no availability implied:

- Buyer: “2 BHK in Boring Road under 70 lakh.”
- Assistant: Search actual inventory and report matches or the absence of matches.
- Buyer: “What about Kankarbagh?”
- Assistant: Switch locality and drop any stale landmark from the earlier query.

Browser conversations and saved-listing IDs use a Patna-specific storage namespace.
Optional messaging channels use their configured adapters. External service
behavior requires live account testing.
