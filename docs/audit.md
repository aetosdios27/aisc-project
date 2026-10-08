# Adversarial refinement audit — 8 October 2026

The UI and experiment pipeline were checked against the project’s two priorities: an understandable first screen and defensible comparisons. Screenshots show the actual local application at a 390 × 844 CSS-pixel viewport.

1. **Play — healthy.** [Screenshot](audit/01-play-mobile.png). The board, current player, scores and legal moves appear before detailed controls. The opening instruction tells the user what to do. Human moves receive automatic AI replies. Technical definitions remain available in expandable sections. No horizontal overflow was measured at this viewport.
2. **Experiments — healthy, preliminary evidence.** [Screenshot](audit/02-experiments-mobile.png). The research question precedes three direct comparisons. Each card states the sample size and paired uncertainty. Detailed tables and nine plots retain the underlying evidence. Pilot status is explicit.

## Corrected defects

- Missing optional analysis and absent artifact hashes could compare equal and trigger a property access on undefined. Rendering now requires a real matching hash and an analysis array; older responses remain usable.
- Failed initial connection could disable New game permanently. Retry remains available while no request is running.
- Human-mode analysis could use the hidden Black selector. Analysis now uses the visible selected AI.
- Autoplay, reset and settings could conflict during an outstanding request. Controls and request tokens prevent stale responses and extra moves after pausing.
- Invalid serialized boards, nonfinite evaluators/budgets and invalid player types are rejected consistently. Falsey evaluator objects are preserved.
- Tournament totals omitted pass-search work; CSV omitted color performance. Derived totals now include passes, with averages explicitly per placement, and CSV retains both colors.
- Fitness seed iterators could be exhausted after one opponent. Every opponent receives the same materialized seed panel.
- Failed preprocessing and custom output paths could overwrite canonical dataset artifacts. Preparation validates before writing; custom outputs preserve the canonical manifest.
- Neural training now validates all three split fingerprints and sample encodings.
- Reports no longer assume ten opening pairs, six positions, depth three or a particular winning evaluator. Plot source hashes prevent showing stale figures as current results.

## Evidence

47 Python tests passed, including an independent directional-rules oracle over 20 seeded games, independent exact endgame solutions, search equivalence across move orderings, and near-duplicate filtering against a brute-force oracle. Four Node regression tests passed, including the screenshot’s missing-analysis failure and initial-load retry.

Browser checks covered automatic replies, analysis without changing the position, configuration changes, failed requests, pausing during a pending move, retry after an initial connection failure, and a complete 60-placement random-vs-random game ending in a 32–32 draw. A forced-pass fixture continued to the terminal position. Experiments rendered three comparison cards and nine chart images.

The search benchmark was rerun on the original 54 position/depth/ordering rows. Selected moves, values and both algorithms’ node counts matched the earlier artifact exactly. Wall times are new measurements; the earlier benchmark is preserved in `experiments/results/audit/benchmark_before.json`. The 324 tournament/depth transcripts were replayed and their derived summaries updated. GA and neural training were not rerun during this audit.

## Limits and research risks

Screenshots and semantic checks do not establish full accessibility compliance; a screen-reader session and broader keyboard/device testing remain useful. Charts are raster plots, with explanatory captions and source JSON available. Higher search depths remain slow in this readable Python implementation.

The stored results are pilot measurements. The neural checkpoint overfits this small dataset; GA superiority is not established. Larger independent opening panels and training seeds remain necessary for a final research claim. No new tournament outcomes or training results were invented.
