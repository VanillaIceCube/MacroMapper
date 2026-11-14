# Nutrition catalog integrity (Batch 3)

Implementation for #92, #77 and #69. Production data repair and deployment require
separate owner authorization. This document does not authorize either action.

## Lifecycle and shared causes

Description parsing and intent extraction first reuse visible catalog versions.
Unmatched foods use `OpenAIMealEstimationProvider`, then pass publication validation,
immutable shared versions, proposal review, and finally pinned diary snapshots.

- **#92:** Nullable structured nutrients were accepted independently, without a
  minimum usable payload, before recursive shared publication. All-null leaves
  could therefore be published. The composite serialization defect discussed on
  the issue is already fixed on main and remains covered by existing tests.
- **#77:** Supplying a web tool allowed the model to skip it. Neither tool outcomes
  nor per-food retrieval status were retained. A muffin citation did not establish
  research for pizza in the same response.
- **#69:** Source `is_official` was discarded during publication and reconstructed
  later from parent provenance. Component rollups also replaced direct restaurant
  values. Confidence never established evidence, but missing source coverage made
  that distinction impossible to inspect.

## Publication and research

`foods.evidence.usable_nutrition` accepts any finite nonnegative known nutrient,
including zero. Nulls mean unknown. Empty leaves fail publication with a visible
unresolved error before any shared food is written. Usable partial records and
containers with populated components remain valid. The shared creation service
also guards non-provider publication. Failed provider validation does not replace
the user's existing draft or diary.

The existing Responses web tool is required for initial estimation. Each branded
parent without matching retrieved evidence gets a separate focused research pass
under the **same existing deadline and worker limit**. There is no new service,
credential, or unbounded retry. These research passes add potential provider/tool
cost to an already-authorized estimate; tests never make live paid requests.
Follow-up additions use the same evidence processing. Quantity-only follow-ups
do not force online research.

Search telemetry supplies the actually consulted URLs. A structured source alone
cannot claim retrieval. Evidence retains document title, publisher, URL, first-party
status, publication date when available, retrieval response ID, product, brand,
region, serving quantity/unit/label/weight, and explicitly published nutrients.
The backend never directly fetches model-supplied URLs. Existing public URL,
text/privacy, decimal, depth and size publication gates remain in force.

Verification requires retrieved evidence matching the exact product, brand,
region and serving, plus equality for each displayed nutrient. Unknown or mismatched
context remains an estimate. Search/extraction is still provider-mediated; these
checks are not an independent human audit of a nutrition document. No production
or paid-model acceptance run has been performed for this change.

`research_status` distinguishes `found`, `no_source_found`, `failed`,
`not_attempted`, and legacy `not_recorded`. An unrelated frozen pizza, different
market, whole pizza or another serving cannot verify a food-court slice. A source
is attached only to its own food; parents do not supply evidence for components.
Existing catalog hits remain reusable without new paid calls. Legacy unsourced
records require separately reviewed re-research/replacement; reuse does not
retroactively manufacture verification.

## Compatible evidence contract

Existing `provenance` and `source_kind` enums remain unchanged. Additive `evidence`
on versions, proposal items and diary responses has these canonical statuses:

| Status | Meaning |
| --- | --- |
| `official_verified` | All populated parent fields directly supported |
| `source_backed_ai_components` | Verified parent values with inferred components |
| `partially_source_backed` | Only some displayed parent fields directly supported |
| `ai_estimate` | No verified parent fields |
| `user_modified_estimate` | Reviewed definition changed; original sources retained as lineage |
| `legacy_unverified` | Historical coverage was not recorded |

`evidence.nutrients[field]` supplies verification status and supporting source URLs.
Partial calorie evidence does not verify sugar, fiber or any other inferred field.
Parent and component evidence remain separate. Direct verified parent fields take
precedence over component sums; ordinary composites continue using component totals.
Changing components removes the parent's verification and recalculates the result.
Changing only the parent's consumed count preserves its per-serving evidence.

Confidence metadata explicitly separates `model`, `evidence`, and `combined`.
No independent numeric source confidence is available, so `evidence` is null,
never a fabricated score. `combined` is the minimum available model dependency
score, or null if a dependency is unscored. Categorical verification is independent
of every confidence score. The UI explains this and exposes source coverage and
the mixed parent/component state.

SourceReference stores its own nullable `is_official` and evidence JSON. Legacy
null official flags serialize conservatively as false/unknown; they are never
inferred from the parent's label. The additive migration does not rewrite old
versions, proposals, revisions, snapshots or source claims. Legacy component
snapshots may omit evidence and remain readable. Source URLs can remain as lineage
on adjusted foods, while no adjusted value is presented as verified. Review input
cannot override server-owned evidence, even when returned metadata is round-tripped.

Canonical food identity is separate from version content fingerprints (Batch 2,
#70). Trust-bearing evidence and source classifications participate in version
content identity, so old unsourced content cannot swallow a verified publication.
Retrieval IDs and confidence remain additional estimate evidence rather than
splitting otherwise equivalent content. Identity still preserves explicit market,
product identifiers and product URLs. Canonical `market` and evidence `region`
share the supplied regional context; contradictory nonblank values are rejected
before publication. Both remain blank when no regional context is supplied.
Nutrition or serving changes create versions under the same canonical food. See [CANONICAL-FOODS.md](CANONICAL-FOODS.md).
The merged schema applies Batch 3's evidence migration before Batch 2's additive
canonical-food migration. Neither migration repairs production data.

## Deferred existing-data remediation

The historical issue evidence identifies American Cheese (food/version 10), Bun,
Beef Patty, Lettuce, Tomato, Spread, Onion and Cheeseburger w/Onion from proposal 4
as all-null. Issue #77 identifies unsourced Costco pizza (food/version 100,
proposal 51). These identifiers are investigation leads, not an archive allowlist;
their current production state has not been read or modified in this batch.

On an approved private database copy, run the default read-only audit:

```powershell
python backend/manage.py audit_catalog_nutrition
```

It examines effective recursive nutrition, including empty composite parents, and
reports food/version IDs only. Review every candidate, references and sources.
Do not infer nutrition or clear nulls to zero. After separate explicit production
authorization and the app release guide's SQLite capture/recovery prerequisites,
an operator may archive **only reviewed still-empty shared food IDs**:

```powershell
python backend/manage.py audit_catalog_nutrition --archive --food-id REVIEWED_ID
```

The command rechecks selected rows transactionally and rejects any changed, usable,
personal, missing or already archived target. Archiving changes discovery metadata
only: no versions, component references, source evidence, diary nutrition snapshots,
or proposal revisions are rewritten/deleted. All affected empty containers should
be reviewed with their leaves. Test on a disposable copy and compare historical
version IDs, meal totals, component snapshots and revision JSON before/after.
Rollback restores only the archived timestamps recorded in the approved plan;
never rewrite historical nutrition to match a later correction.

Re-research unsourced/incorrect legacy records separately using approved evidence;
create new immutable versions or replacement shared publications. Preserve the old
references and original model metadata. Do not run paid re-estimation, archive
production records, execute migrations, or promote env-prod as part of this batch.

## Verification

Synthetic backend and SDK fixtures cover null/zero/partial nutrition, official
parent and AI child, per-nutrient coverage, source/product/region/serving mismatch,
targeted Costco pizza versus muffin source attribution, retrieval failure versus
unavailable evidence, cross-user reuse, no-op review, hostile evidence edits, and
dry-run/archive history preservation. Frontend tests exercise adapters, counts,
component edits, mixed badges, links, confidence explanations, warnings and legacy
fallbacks. Run both backend MCP profiles, frontend tests/lint/build, browser tests,
shared MCP/release parity and disposable release/security checks before merge.

Official API contract: [Responses web search](https://developers.openai.com/api/docs/guides/tools-web-search)
and [tool selection](https://developers.openai.com/api/docs/guides/tools).
