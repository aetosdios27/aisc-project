# Controlled experiment protocol

Research question: **Can learned or evolved position evaluators outperform a manually designed heuristic when every engine receives the same adversarial search budget?**

The manual heuristic is the prespecified reference. The GA evolves only its seven weights. The MLP learns a recorded-outcome value and replaces only leaf scoring. For primary comparisons all three use the exact same Alpha-Beta recurrence, positional ordering, terminal utility and placement depth. No opening book, game library, cache or special endgame solver changes one engine's search.

## Reproduction

Run the commands in README in order. Every result contains configuration/seeds, Python/platform information and SHA256 fingerprints of algorithm source. Tournament metadata additionally links GA and neural artifact hashes. Raw neural data and processed splits have their own manifest; the saved checkpoint has a hash in the neural result. Source hashes describe the run and can differ after later source edits; rerun for a final consistent snapshot. Wall-clock times need not match across machines; fixed-depth moves, values, node counts and outcomes should match in a pinned environment.

| Study | Saved artifact | Measurement |
| --- | --- | --- |
| Minimax vs Alpha-Beta | `benchmark.json`, `.csv` | Exact move/value assertions, visited nodes, time, cutoffs, reduction percentage |
| Manual vs GA | `tournament.json`, `.csv` | Direct paired game score, color performance, node/runtime cost |
| Manual vs neural | same | Same Alpha-Beta depth, different leaf evaluator |
| GA vs neural | same | Same Alpha-Beta depth, different leaf evaluator |
| Depth vs strength | `depth.json` | Depth 1/2/3 manual engines vs fixed depth-one reference |
| Depth vs runtime | `benchmark.json`, `.csv` | Identical seeded positions across depths |
| GA convergence | `ga.json`, `.csv` | Best/mean training fitness, fixed validation score, diversity |
| Neural training | `neural.json`, `.csv` | Epoch MSE, minimum-validation checkpoint, held-out test metrics |

The six-engine round robin also includes seeded Random, greedy manual evaluation, and manual Minimax. Greedy is exactly one-placement Minimax. These contextual baselines do not receive the same algorithm/depth as the three primary evaluator comparisons. A depth-strength study deliberately varies depth; label it as such.

## Pairing and uncertainty

For each opponent pair, draw an opening by eight seeded random turns from the legal opening. Replay the same state twice, swapping colors. Each distinct opening seed is the statistical block. Random-agent streams use the opening's seed but independent per-agent Random objects. Opening turns are outside measured search cost; per-move averages count actual engine placements, excluding passes. Full transcripts include pass turns.

Report raw win rate W/N and score rate (W+0.5D)/N separately. Color breakdown helps diagnose imbalance. Mean game length should include the seeded opening; continuation length is also retained. Direct evaluator pairings answer the research question; pooled round-robin rate depends on opponent composition.

Uncertainty must resample opening pairs as blocks, rather than individual games. A deterministic percentile bootstrap with 2,000 samples is suitable for pilot score-rate intervals. Small panels can yield wide or misleadingly narrow intervals, especially for deterministic repeated/symmetric openings. The dataset consists of related trajectory samples; independent game-level evaluation is preferable to treating positions as independent observations.

## Freeze and final study, 21–24 October

The shipped artifacts are **pilot measurements** to prove the pipeline runs. They are not a prespecified final superiority claim. Freeze algorithm/settings by 20 October. Before the reserved experiment window, fix the final opening panel, search budget, number of repetitions and interpretation criteria. Use at least 100 distinct opening pairs (200 games) for each primary pairing, preferably at depths 2 and 3. Reuse the panel across pairings. Seeds must remain separate from GA fitness (440 onward), GA validation (1440 onward) and pilot tournaments (1200 onward).

Repeat evolution/training with multiple independent seeds if compute allows; assess instability instead of reporting only the best run. Preserve each run's artifacts in a separate directory before another invocation overwrites default output. Do not choose settings based on final test games. If the pilot test set has been inspected for model changes, reserve a new untouched game-group test set for the final report.

Suggested research sessions: 21 October run larger paired tournaments; 22 October analyze uncertainty and regenerate report figures; 23 October prepare slides and rehearse the demo; 24 October rehearse viva and verify submission archive. No new product features in this window.

## Known limitations

The GA pilot uses a small population and short games panel. Changing opponents mean training fitness across generations is not directly comparable; use the fixed validation curve. Validation can itself be overfit by repeated champion selection. The neural pilot samples one public year, has outcome-label noise and a clear overfitting curve. A test prediction improvement does not imply stronger play. Depth equality controls horizon but not runtime; neural inference cost matters in separate equal-time studies. Timed searches are deadline-sensitive and are not expected to repeat exactly.

No benchmark number is manually entered into chart data. `experiments/plots.py` reads saved experiment JSON and creates standalone PNGs. The browser displays those figures and calculated table entries from the same saved outputs.

## Profiling evidence

`python -m experiments.profile` profiles the same six depth-three manual Alpha-Beta positions without overwriting benchmark timings. The saved `profile.txt` identifies feature extraction and legal-move/capture scanning as the main cumulative costs. Profiling overhead affects its times, so use the uninstrumented benchmark for comparisons. No further optimization is introduced in this implementation; preserving the verified recurrence and output takes priority.
