# MacroMapper production coordination handoff

[Infrastructure #4](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/4)
is the canonical decision thread; [MacroMapper #240](https://github.com/VanillaIceCube/MacroMapper/issues/240)
tracks app implementation. The [PR #239 audit](PR239-AUDIT.md) retains historical
findings, including its unauthorized merge. That historical merge is not approval.

## Current authorization state

**Architecture v2 is approved**, by the [owner's explicit decision](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/4#issuecomment-6111586759).
**The implementation PR merges and production rollout are not authorized.**
Each PR merge and the exact production plan require separate owner approvals.
Do not merge, enable auto-merge, move `env-prod`, dispatch Deploy or operate on
the VM based on architecture approval, reviewer approval or CI success.

The three standalone implementation PRs are [Infrastructure #11](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/pull/11),
[Notoli #906](https://github.com/VanillaIceCube/Notoli/pull/906) and
[MacroMapper #242](https://github.com/VanillaIceCube/MacroMapper/pull/242).
They include preparation work; #10/#905/#241 are closed as superseded, unmerged.
Ready for review means reviewable, not approved for merge or deployment.

Agent 5 owns implementation across all three repositories. Agent 3 remains the
independent read-only VM inspector and sole production operator after separate
approval. His [refreshed VM audit](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/4#issuecomment-6111383750)
and [v2 feasibility assessment](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/4#issuecomment-6111422055)
are the host baseline; source/CI tests do not establish live acceptance.

## Remaining checkpoints

1. Complete full-scope CI and reconcile code/security findings on all three PRs.
   Agent 3 independently re-reviews the recovery/timeout/journal fixes and exact
   source heads; keep findings visible until resolved.
2. Obtain owner approval for each exact PR merge. Merging `main` does not
   authorize promotion to `env-prod` or a deployment dispatch.
3. Agent 3 supplies the concrete command-level production plan, hold/window,
   writer quiescence, recovery/restore evidence, off-host backup policy, protected
   paths/locks/SSH capability, peak capacity, Cloudflare controls, hostname and
   port-3000 inventory, and functional acceptance/failure cutoff. Obtain separate
   owner approval before those live actions.
4. Execute sequentially under that plan: gateway cutover and both-app acceptance,
   Notoli activation and independent repeat verification, then MacroMapper
   activation and independent repeat verification. Preserve installed bridge
   files until cutover/recovery is proven; obsolete repository source remains in
   Git history rather than a deployable legacy folder.
5. Record actual production evidence on #4 with app-ticket cross-links.
   [#236](https://github.com/VanillaIceCube/MacroMapper/issues/236) and
   [#238](https://github.com/VanillaIceCube/MacroMapper/issues/238) remain open
   until their live acceptance criteria are observed.

Use the current [app release/recovery guide](production/README.md) and
infrastructure cutover runbook when preparing the separately approved plan.
The [local Docker hot-swap workflow](README.md#local-docker-with-macromapperlocalhost)
remains supported and does not operate the production host.
