# Delivery plan — temporary repository name: othello-ai

Research question: can learned or evolved evaluators beat a manual evaluator under equal adversarial search budgets?

Python owns all rules and algorithms. Immutable 64-cell boards keep transitions inspectable. Separate modules own evaluation, search, evolution, public-data processing, training, experiments, and serving. The browser only renders and requests engine operations.

Dependencies: standard library for the engine/API/tournaments/GA/data parser; PyTorch for tensors and backpropagation; Matplotlib for artifact plots; pytest optional (tests also run with unittest). No game libraries, pretrained networks, databases, accounts, or LLMs.

## Calendar

| Dates (October 2026) | Acceptance gate |
| --- | --- |
| 7–8 | Rules, serialization, passes, random simulation; deterministic tests pass |
| 9–10 | Features, Minimax, Alpha-Beta; identical value AND move across ordering modes |
| 11–12 | Paired tournament runner, efficiency benchmarks, GA operators and fitness |
| 13–15 | Public-data provenance, leakage audit, neural training and offline metrics |
| 16–18 | Controlled evaluator tournaments, depth studies, restrained web demo |
| 19–20 | Integration checks, bug fixes, reproducibility review; feature freeze |
| 21–24 | Larger experiments, report, presentation, viva; no new features |
| 25 | Submission |

Risks: pass depth semantics; changing evaluator perspective; bound-valued Alpha-Beta ties; duplicate/symmetric training positions; outcome labels describe recorded play rather than perfect play; repeated deterministic opening games; small GA fitness panels overfit; CPU experiment costs. Each has tests or explicit measurement/protocol notes. Optional advanced search requires separate correctness and performance evidence; omit unless time remains.

Milestones may be implemented early but the calendar retains the 20 October stability gate. Initial small experiment artifacts are pilot evidence, not the final statistical claim.
