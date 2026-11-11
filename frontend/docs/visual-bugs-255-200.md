> **Historical evidence — clarified scope on 2026-11-07.** The coordinated rollback was cancelled before production changed. The owner subsequently confirmed “Undo #377’s visual changes” under #382. Main-only revert #379 keeps the earlier date-control appearance; reapplication PR #381 was superseded without merging. The independent nonempty-date guard is retained after a fail-first regression reproduced `RangeError: Invalid time value` when clearing the input and navigating. Earlier Food & Servings functionality remains and receives focused coverage again. This original investigation/screenshots preserve historical evidence; prior geometry pass results do not override the owner’s rejected visual appearance. #255/#200 stay open for renewed acceptance, and the original native-picker anchoring concern is not claimed resolved. Security #375/#376, current user data and release safeguards remain intact.

# Diary visual regressions: #255 and #200

## Date picker (#255)

The diary uses `HTMLInputElement.showPicker()` on a native date input, not a
MUI Popover/Popper. The old invisible input was a 1×1 absolutely positioned
element after the navigation stack, with no explicit inset. Its static
position was 45px left of the visible date button in production Chromium at
all six tested widths. Native popup positioning used that input instead of
the visible trigger. Mobile navigation also explicitly aligned to the left.
No portal, container, Popover origin, or production-only CSS override controlled
this popup. PR #127 repaired removed MUI 9 layout props and reserved a Today
slot; it did not correct this native input's anchor geometry.

The input now shares a relatively positioned wrapper with the visible button,
with coincident bounds through `inset: 0` and percentage sizing. Navigation
aligns to the right while preserving the reserved Today slot. The browser
retains native viewport collision handling; there are no popup pixel offsets.
The button reserves a consistent responsive width for both Today and the longer
compact date labels, preventing a further 6px shift on dates such as September 30.
Clearing the native input cannot put the diary into an invalid empty-date state.

## Food & Servings (#200)

The requested heading capitalization and `sm`-and-up grid centering were already
implemented in `9b8e4428acd9a28f0caaf8fe03f0dab413ce1a1b`. They are present in
both main and the deployed production source. Before-change production browser
tests passed at all six widths, including long food names and serving context.
No additional nutrition/table implementation change is necessary.

The regression suite now verifies the exact heading and each adjacent cell's
vertical center against the complete food cell, for short and wrapped content.
Phones retain the existing stacked food identity with three labeled metadata
columns below it. Test assertions preserve the sample food, serving count,
calories, and confidence. No nutrition or estimation logic changes.

## Shared UI parity and scope

FullStackTemplate and Notoli have no equivalent diary date-navigation/native
picker wrapper or nutrition-breakdown table. Both defects are product-specific;
no canonical reusable correction or downstream adoption is needed. Generic
shell/settings work remains with FullStackTemplate #295/#296. No other product
or protected issue is changed by this batch.

## Verification method

`e2e/diary-visual.spec.mjs` runs in the normal isolated browser suite and through
`playwright.visual.config.mjs` against the built production frontend or an
explicit deployed URL. It tests widths 320, 375, 600, 768, 1024, and 1440px.
Browser-intercepted API responses use only `example.test` identities and sample
meals; unexpected API/auth requests are aborted. No production DB writes occur.

Before-change production: all six date-anchor tests fail (45px horizontal
displacement); all six food-layout tests pass. Screenshots and traces are
retained in the local ignored `frontend/browser-evidence/before/` directory.

After-change production build: all twelve browser tests pass. Representative
screenshots use only synthetic meals:

| Viewport | Before (deployed assets) | After (production build) |
| --- | --- | --- |
| Phone, 375px | [Before](visual-bugs-255-200/before-375.png) | [After](visual-bugs-255-200/after-375.png) |
| Tablet, 768px | [Before](visual-bugs-255-200/before-768.png) | [After](visual-bugs-255-200/after-768.png) |

Date tests check coincident trigger/input bounds, right alignment, viewport
containment, successful native opening requests, previous/next/Today stability,
explicit date selection, and absence of diary overflow. Food tests compare
actual rendered cell centers and check mobile field labels and wrapping.

Linux CI additionally exposed a pre-existing 2px overhang of an icon-only button
in the unchanged shared application header at 320px. The diary's elements stay
within the viewport. Overflow checks cover this ticket's complete diary subtree;
the shared header remains in the separate FullStackTemplate #296 shell scope.

Headless page screenshots do not capture or prove native browser/OS popup
bounds. Native picker presentation on iOS/Android remains OS-controlled;
production anchor verification must be distinguished from those device-specific
interactions. VM container health alone is not visual verification.
