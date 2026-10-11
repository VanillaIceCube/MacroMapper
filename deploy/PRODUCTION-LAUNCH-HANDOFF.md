# MacroMapper production coordination handoff

[MacroMapper #240](https://github.com/VanillaIceCube/MacroMapper/issues/240)
tracks app work. [Infrastructure #4](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/4)
is the single shared-architecture discussion and decision thread. The broader
[launch checklist #236](https://github.com/VanillaIceCube/MacroMapper/issues/236)
and [minimum prerequisites #238](https://github.com/VanillaIceCube/MacroMapper/issues/238)
remain open until their live acceptance evidence exists.

## Current status and authorization

PR #239 was merged without the owner's authorization. Its implementation is
an unapproved candidate. Read the [component audit](PR239-AUDIT.md) before
reusing it. Repository files and prior host reports do not establish the
current running configuration, adequate capacity, or successful deployment.

Agent 3's [VM audit](https://github.com/VanillaIceCube/Notoli/issues/904#issuecomment-6107091928)
observed MacroMapper already running through the bridge at SHA `a510a3a5…`;
both public HTTPS roots returned 200. Agent 1 posted
[VM reconciliation](https://github.com/VanillaIceCube/Notoli/issues/904#issuecomment-6107111199).
The component audit incorporates both reports and the
[proposed contract v1](https://github.com/VanillaIceCube/Notoli/issues/904#issuecomment-6107124549).
Agent 2 posted [conditional compatibility review](https://github.com/VanillaIceCube/Notoli/issues/904#issuecomment-6107138862),
asking for release staging/locking and bounded health-check clarification.
VM feasibility, feature acceptance, restore evidence, prior deployment
authorization and the final owner-approved contract remain open.

The owner has since consolidated all three repositories into Agent 5, replacing
separate Agents 1/2/4. Agent 3 remains the independent read-only VM inspector and
sole designated operator for separately authorized production changes.
Agent 3's [refreshed audit](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/4#issuecomment-6111383750)
confirms unchanged runtime topology/images and verifies Compose/architecture
and upstream aliases. Agent 5's [proposed v2 contract](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/4#issuecomment-6111397179)
consolidates the earlier findings and release-staging clarification; it remains
subject to VM feasibility and explicit owner approval.

Architecture approval, each PR merge, and each production deployment/cutover
require separate explicit owner authorization. Passing CI, a prior merge,
agent agreement, or silence grants none of these approvals. Leave prepared PRs
open and unmerged. Do not enable auto-merge or dispatch a deployment.

## Next checkpoints

1. Continue from v2 and the refreshed audit on Infrastructure #4; retain older
   Notoli #904 comments as historical evidence.
2. Agent 5 reconciles compatibility across all three repositories. Agent 3
   posts `[VM FEASIBILITY REVIEW]` against the numbered contract on #4;
   Agent 5 incorporates objections and links app-specific effects here.
3. Present the reconciled contract and outstanding risks to the owner.
   Finalize shared-boundary implementation only after contract approval.
   Independent app-local cleanup can proceed in reviewable PRs meanwhile.
4. Submit `[IMPLEMENTATION HANDOFF]` with PR/files, checks, risks and rollback
   on #240. Await PR-specific owner merge authorization.
5. Agent 3 prepares a concrete cutover plan and obtains separate owner
   production authorization. Release sequentially: shared ingress/Notoli
   verification first, MacroMapper second. Record actual production evidence
   on Infrastructure #4 with app-ticket cross-links before requesting closure.

The [deployment guide](README.md) describes candidate configuration, variables,
secret handling and recovery. Its bridge installation commands are not an
approved production plan. Preserve any installed bridge until an approved
replacement is deployed and verified; neither app should permanently own the
shared ingress lifecycle.
