# Canonical food identity and conservative consolidation

Shared food identity is separate from an estimate's serving, nutrients,
confidence and meal quantity. `canonical_identity` hashes normalized food/provider
names, market and product identifiers. Known food plurals and punctuation are
normalized; provider foods do not split merely because their classification is
`branded` rather than `restaurant`. Generic leading portion-size wording is
removed, while branded size/SKU names remain distinct.

An explicit product identifier is scoped to its provider and market. Otherwise
an explicitly supplied identity URL, or a source whose hostname starts with the
normalized provider name,
also constrains identity. URL fragments and tracking parameters are ignored;
country paths and meaningful query parameters are preserved. This hostname
heuristic is an identity hint, not proof of domain ownership or official
nutrition provenance. Unmatched third-party source URLs do not define identity.
Unknown versus known identity URLs/markets are
conservatively distinct: adding evidence must not silently merge potentially
different regional products. Unrecognized synonyms and cross-domain provider
aliases need explicit review rather than fuzzy automatic merging.

Within a canonical food, `content_fingerprint` covers the serving definition,
food-specific natural servings, all supported nutrients, pinned component
content/identity/quantities, and research/verification coverage.
Component identity uses the registered canonical key when available; legacy
components derive their identity from the exact pinned version's source URLs,
so a later current version or a same-named regional product cannot replace it.
Source-level official flags and verification evidence are part of content
integrity: a newly verified publication cannot be swallowed by an older unsourced version with the
same nutrients. Meal servings and consumed recipe fractions are instance
quantities and do not create versions. Evidence-equivalent definitions reuse a
version, retain additional source URLs, and append distinct estimation metadata
to `FoodVersionEvidence`. Confidence-only differences and retrieval response IDs
do not split equivalent versions; their complete incoming evidence/source
metadata is retained in that append-only record.
Ordinary citations with `is_official=false` and empty evidence also merge into
the same version rather than changing its content identity; adding a first-party
claim or trust/research evidence remains an immutable version distinction.
Existing version nutrients, provenance, confidence, source evidence and response
metadata remain unchanged.
A materially changed definition or verification coverage creates a new version.
Personal definitions remain owner-specific and are never merged by the
consolidation command.

Current version selection is deterministic: categorical verified parent coverage
wins first (fully verified and source-backed with inferred components, then
partially verified, AI estimate, then legacy/unknown), followed by the count of
verified nutrient fields. Provenance then ranks official, community estimate, AI
estimate, user entered, then user modified; source count, confidence, earliest
version number and primary key break later ties. A legacy official label cannot
displace a newly verified definition. Recency alone cannot displace better
evidence. Exact source/product/region/serving verification follows the merged
[nutrition-integrity contract](NUTRITION-INTEGRITY.md); this selection policy
does not independently validate an AI assertion that a source is official.

## Schema migration

Foods migration `0006_canonical_food_identity`, after main's additive source
evidence migration `0005`, only adds nullable/defaulted
identity, redirect, natural-serving and fingerprint fields and an evidence
table. It performs no data cleanup or historical nutrition rewrite. Existing
version/meal/component/proposal references remain valid. Schema rollback removes
the new metadata; it does not undo an explicitly applied consolidation. Take a
database backup before any later authorized operational cleanup.

## Reviewable duplicate cleanup

No production cleanup is part of this implementation. The owner can later
review actual shared-food IDs and source/market/SKU evidence, then run the
following against a backed-up database under separately authorized operations:

```powershell
# Review only; this is the default and writes nothing.
python backend/manage.py consolidate_foods <first-id> <second-id> <third-id>
# Apply only after examining the proposed canonical ID and source definitions.
python backend/manage.py consolidate_foods <first-id> <second-id> <third-id> --apply
```

The existing McDonald's Hash Browns records are the initial synthetic regression
case. Real IDs are deliberately not embedded or inferred. The command rejects
personal, already archived, missing or differently identified records. It
selects the registered canonical food, otherwise the lowest ID. Equivalent
versions merge evidence; distinct definitions are copied onto the canonical
food with derivation pointing to the retained original version. Duplicate food
records are archived with `merged_into` pointing to the canonical food.

Original versions, source rows and their official/retrieval evidence, derivations,
meal snapshots, component foreign
keys, proposal JSON and revision JSON are not moved or rewritten. Active list
and catalog resolution expose the canonical record. An old alias detail lookup
remains traceable through `merged_into`; pending proposals and saved meals can
still use their exact pinned historical shared versions. A failed cleanup rolls
back atomically. Retained originals support investigation, but restoring active
catalog visibility after a completed cleanup requires a separately reviewed
procedure or backup recovery; do not delete the alias/history rows.
