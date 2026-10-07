# Viva preparation

The project compares three leaf evaluators inside the same adversarial search. Explain the rules and controlled comparison first; then derive the algorithms. The full definitions, mathematical formulations, pseudocode, complexity, implementation assumptions and limitations for every major algorithm are in [algorithms.md](algorithms.md). Source boundaries are in [architecture.md](architecture.md).

## Rules and representation

**How is a move legal?** An empty square must bracket a nonempty contiguous opponent run with an existing friendly disc in at least one of eight directions. Capture rays stop at an empty square, boundary, or friendly disc. All bracketed runs flip simultaneously.

**What happens on a pass?** A pass is mandatory only if the current player has no move. It swaps players without consuming a search placement depth. If neither player has a move, the game is terminal even if empty squares remain.

**Why immutable boards?** A search child cannot corrupt its siblings or parent. Copy cost is small on 64 cells, and transitions are easy to replay and test.

**How is reproducibility achieved?** Explicit local random seeds, complete serialized states and transcripts, deterministic tie breaks, CPU neural training, fixed data/group splits and stored hashes/configuration.

## Minimax and pruning

**What is Minimax?** A recursive decision rule for two-player zero-sum games. MAX selects the largest child utility; MIN selects the smallest, from one fixed player's perspective.

**Why does it work?** At terminal/cutoff nodes utilities are given. By induction, each parent chooses its best child assuming the other player does the same. Finite-depth Minimax is optimal for its explored tree, not necessarily the full game.

**Why evaluate at a depth limit?** The full tree is too expensive. An evaluator approximates future outcome at unexplored leaves. Deeper search is more expensive and can still suffer horizon effects.

**What is Alpha-Beta pruning?** Minimax with bounds that let it skip branches incapable of changing an ancestor's choice.

**What do alpha and beta mean?** Alpha is MAX's established lower bound; beta is MIN's established upper bound along the current search context.

**When does pruning occur?** When alpha is at least beta. The opposing ancestor already has an alternative at least as good as anything that matters through this branch.

**Why the same result as Minimax?** Only branches that cannot affect the controlling decision are omitted. Exact root candidate windows plus a canonical tie break preserve selected-move equivalence as well as value equivalence.

**Why is move ordering useful?** Good candidates tighten bounds sooner. It affects explored nodes and runtime, not the exact fixed-depth result. Mobility ordering itself has a cost.

**What are the complexities?** Minimax O(bᵈ). Alpha-Beta worst O(bᵈ), ideally about O(b^(d/2)). This depth-first implementation uses O(bd) space because of board copies/child lists. Rule and evaluation costs multiply those bounds.

**Can equal numeric root results still hide a bug?** Yes. Pruned child returns may be bounds rather than exact values. Tie handling must not treat them as exact candidate evaluations. We test both chosen move and value.

**What does “nodes pruned” mean?** We know skipped immediate children. Full descendant savings require comparison with unpruned Minimax; the benchmark measures that difference and its percentage.

## Heuristics

**What is a heuristic evaluation function?** A computable approximation to future game value. Here it is a weighted sum of seven separately observable normalized features.

**Why are corners valuable?** A corner disc cannot be bracketed: there is no square beyond the corner on a capture line. A corner also supports less vulnerable edge play.

**What is mobility?** Number of currently legal placements. Relative mobility compares own and opponent legal choices. Potential mobility counts empties next to opponent discs; it approximates future opportunity.

**Why not maximize discs early?** Many discs can be exposed frontier discs that give the opponent moves. Final disc majority matters; early material alone is misleading.

**Why these weights?** They encode explicit strategic hypotheses, not verified optimal constants. Corners and mobility receive the most emphasis; GA tests whether different weights perform better in actual games.

**How is each contribution explained?** Normalize by total absolute weight, then display weight × feature / total absolute weight. Every feature favors the requested player, and reversing perspective negates the score.

**Why bounded leaves?** Shared terminal wins exceed every possible leaf prediction, preventing a speculative heuristic from outranking a known win.

## Genetic algorithm

**What is a GA?** Population-based optimization inspired by inheritance and variation, guided by a fitness function.

**What is the chromosome?** Seven real values, one per heuristic feature. L1 normalization removes overall scale redundancy.

**What is fitness?** Actual game score rate: wins plus half draws divided by games, against the manual evaluator, previous champion and a sampled population member at equal depth and paired colors.

**What is selection?** Sample three population indices with replacement and select the highest-fitness parent. It biases reproduction toward better candidates without eliminating all variety.

**What is crossover?** Child = t parent A + (1−t) parent B for a sampled t between zero and one.

**What is mutation?** Independently perturb a gene with a Gaussian sample, then normalize. It explores weights unavailable from parent blending alone.

**Why elitism?** Preserve the current best individual unchanged so variation cannot discard it. A champion's measured fitness can still change if the opponent panel changes.

**Does convergence prove optimality?** No. The space is continuous, fitness is noisy and panel-dependent, and local plateaus are possible. Separate fixed validation and final opponents are needed.

**How do you reduce noise?** Give every candidate the same openings, swapped colors and frozen panel within a generation. Use separate fixed validation seeds and larger final tournaments.

## Neural network

**What is a neural network?** A parameterized composition of linear transformations and nonlinear activations, fitted by minimizing a loss.

**What is forward propagation?** Compute h1=ReLU(W1x+b1), h2=ReLU(W2h1+b2), output=tanh(W3h2+b3).

**Why 64 inputs?** One value per square, relative to the side to move. Side to move is already implicit in which discs encode as +1. No absolute color advantage is assumed.

**Why ReLU and tanh?** ReLU introduces nonlinearity in hidden layers; tanh constrains predicted value to the outcome range [−1,1].

**What is backpropagation?** Apply the chain rule backward through the computation graph to obtain derivatives of loss with respect to each weight and bias.

**What loss is used?** MSE: average squared error between predicted value and recorded game outcome −1,0,+1. The conditional mean of those outcomes is the regression objective.

**What is gradient descent?** Adjust parameters in the opposite direction of the loss gradient. Adam adapts update scales using first and second gradient moments.

**Why use a public dataset?** It gives independent human-game trajectories with traceable provenance and reduces dependence on our own engines' weaknesses. It still has selection bias and imperfect-play labels.

**What is overfitting?** Fitting training patterns that do not generalize. Our pilot validation loss worsens after epoch one while training loss falls, so the saved checkpoint is epoch one.

**Why separate train, validation, and test?** Train fits weights; validation chooses checkpoint/settings; test estimates held-out performance. Repeated tuning against test results compromises that estimate.

**How do you prevent leakage?** Keep entire games/shared-opening groups together, remove symmetric duplicates, and exclude later-split states within two changed cells of earlier splits under all board symmetries. Report this operational definition and remaining broader similarity risks.

**Does prediction accuracy guarantee game strength?** No. Search decisions depend on relative ranking of positions encountered during play, which may differ from human-game test states. Actual equal-budget tournaments answer the research question.

**Why can the neural evaluator be used in Alpha-Beta?** Alpha-Beta only needs scalar cutoff values. The model replaces that scalar function, while legal moves, search recurrence, terminal utilities and budget stay identical.

**How do perspectives work?** The network predicts for leaf side to move. Multiply by leaf turn × root player to express every leaf in the root player's perspective.

## Experimental design and defense

**Why equal budgets?** Otherwise a deeper search could explain better results rather than a better evaluator. Equal depth measures evaluator differences at a fixed horizon; equal time measures practical strength with inference cost included.

**Why alternate colors?** Opening and color advantages can bias outcomes. Each opening is replayed with the engines swapped.

**Why varied openings?** Deterministic engines repeat the same game from the same state. Repetition alone is not independent evidence. Shared seeded random openings create varied, comparable starting states.

**Why show direct pairings as well as pooled win rates?** Pooled strength depends on opponent mix. The research question is answered by manual-vs-GA, manual-vs-neural and GA-vs-neural direct comparisons.

**What is a draw worth?** Zero in raw win rate W/N, half in score rate (W+0.5D)/N. Both are reported and should not be confused.

**How should uncertainty be calculated?** Bootstrap opening pairs as blocks, keeping both color games together. Do not treat paired games or positions from one trajectory as independent samples.

**What can the pilot establish?** Working algorithms, measurable pruning, executable training/evolution, and initial performance signals. It cannot establish general superiority from a small opening panel or single training seed.

**What is omitted?** Stable-disc approximation, phase-specific weights, full-game solution search, transposition tables and elaborate tree visualization. Each would need validation and can distract from the controlled evaluator study.

## Five-minute demonstration

1. Show opening legal moves; place d3 and explain the flip.
2. Analyze with Minimax and Alpha-Beta at equal depth; compare chosen move/value and cost.
3. Show feature contributions and the chromosome vector.
4. Show the GA fixed validation curve and explain changing training panels.
5. Show neural training/validation divergence and selected checkpoint.
6. Show the three direct evaluator comparisons, paired colors and recorded seeds.
7. Explain limitations honestly and state the final experiment protocol.

Before viva: derive one capture line, a small MAX/MIN tree and alpha-beta cutoff on paper; calculate one weighted evaluation; perform one arithmetic crossover; derive tanh/MSE gradients; explain leakage with duplicate symmetric boards. See `docs/plan.md` for the 21–24 October preparation window.
