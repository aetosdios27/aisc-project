# othello-ai

Temporary repository name for an AISC Othello/Reversi engine comparison. No final project name has been chosen.

**Research question:** can learned or evolved position evaluators outperform a manually designed heuristic under the same adversarial search budget?

Rules, Minimax, Alpha-Beta and the Genetic Algorithm are implemented from scratch. A small PyTorch network learns position outcomes from public WTHOR games. Manual, GA and neural evaluators plug into identical Alpha-Beta search. A local engine laboratory exposes play, measured search behavior and actual experiment artifacts.

**Schedule:** complete and stable by **20 October 2026**; reserve **21–24 October** for larger experiments, documentation, presentation and viva; submit **25 October**. See [delivery plan](docs/plan.md).

## Setup

Python 3.12 is the tested research environment. Core algorithms have no runtime dependencies and support Python 3.11+. [uv](https://docs.astral.sh/uv/) can create the environment and install the pinned CPU research packages:

```bash
uv python install 3.12
uv venv --python 3.12
uv pip install --python .venv/bin/python --index-strategy unsafe-best-match \
  --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-research.txt
.venv/bin/python -m unittest discover -v
```

Run commands from the repository root. Alternatively, create a Python 3.12 virtual environment with pip and install the same requirements file using the PyTorch CPU extra index. `pyproject.toml` describes the minimal core and optional research/dev dependencies; `requirements-research.txt` pins the environment used for committed measurements.

For a dependency-free rules/search check:

```bash
python -m unittest engine.tests.test_board engine.tests.test_search \
  engine.tests.test_experiments engine.tests.test_dataset
```

## Local demo

```bash
.venv/bin/python -m api.server --port 8000
```

Open **http://localhost:8000**. Human plays Black; use Run one move or Auto play for the AI reply. AI-vs-AI supports all six engines. Analyze exposes the chosen move, root value, visited nodes, pruning cutoffs, skipped immediate children and search time. The manual feature panel shows separate weighted contributions. Export saves a replayable game transcript. The Experiments tab reads committed JSON and generated figures.

Committed evolved weights and neural checkpoint allow play without downloading training data. Manual/random engines also work without PyTorch. This is a local research demo, not a public production hosting service.

## Reproduce research artifacts

Run in this order. The source hash can be read from the committed dataset manifest; supplying it guards against a changed upstream archive.

```bash
.venv/bin/python -m evolution.ga --population 6 --generations 4 --pairs 2 --depth 1 --seed 440
.venv/bin/python -m neural.dataset --seed 730 --sha256 f7c2672aaae2badeb1c21bccfc7e4936a11277c68fcb9775f6c7375872f22208
.venv/bin/python -m neural.train --epochs 20 --seed 810
.venv/bin/python -m experiments.run --games 20 --depth 2 --seed 1200
.venv/bin/python -m experiments.analyze
.venv/bin/python -m experiments.plots
.venv/bin/python -m experiments.profile
.venv/bin/python -m unittest discover -v
```

For an initial download without hash enforcement, omit `--sha256`; the pipeline automatically downloads the public file and records its hash. For the exact committed dataset, use the hash from `experiments/results/dataset_manifest.json`. All charts come from saved experiment outputs. Main tournament games are paired and the requested game count must be even.

```bash
# Search efficiency alone; no neural dependency needed.
python -m experiments.run --benchmark-only

# Configurable time mode: common deadline and maximum depth for search agents.
.venv/bin/python -m experiments.run --games 20 --depth 5 --seconds 0.1 --seed 2300
```

Time mode uses the last completed iterative depth and records attempted-search cost. Fixed-depth experiments are deterministic; deadline-driven results can depend on hardware/scheduling. Preserve default results before running another experiment: the scripts intentionally write predictable artifact paths. For the final report, follow the [controlled experiment protocol](docs/experiments.md), including independent opening pairs and seeds.

## Repository map

- `engine/`: immutable board, features, search, agents, deterministic tests.
- `evolution/`: real-valued GA and actual-game fitness.
- `neural/`: public-data download/parser/split, 64→128→64→1 MLP, training, checkpoint.
- `experiments/`: paired tournament/replay, benchmarks, JSON/CSV outputs and PNG charts.
- `api/`, `web/`: thin local HTTP adapter and restrained browser laboratory.
- `data/`: regenerated source cache and processed splits (gitignored).
- `docs/`: [architecture](docs/architecture.md), [algorithm formulations and pseudocode](docs/algorithms.md), [dataset provenance](docs/dataset.md), [experiment protocol](docs/experiments.md), [viva preparation](docs/viva.md), [schedule](docs/plan.md).

## Interpreting the pilot

Read the [generated results summary](docs/results.md) and [paired uncertainty artifact](experiments/results/analysis.json).

The saved outputs are real pilot runs, with seeds, configurations and source/model/data hashes. They test the whole pipeline; they do not establish general superiority. The neural curve exposes overfitting and validation chooses the checkpoint. GA training fitness is panel-dependent; its fixed validation curve is the comparable measurement. Use direct evaluator pairings at equal depth to answer the research question. Pooled round-robin rates mix opponent strengths.

The engine deliberately favors readability and verified behavior. Terminal wins outrank all bounded nonterminal evaluations. Passes do not consume placement depth. Alpha-Beta uses full root candidate windows so canonical ties remain correct regardless of move ordering. Counters distinguish immediate skipped children from total nodes saved against Minimax. Optional transposition tables/tree visualization are omitted until evidence justifies them.
