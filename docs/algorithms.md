# Algorithm specifications

## Rules and transitions

For an empty square m and direction d, walk m+d, m+2d, … within the board. A capture exists only if a nonempty contiguous opponent run ends at a friendly disc. Union captures from all eight directions. Legal(m) iff this union is nonempty. Place a friendly disc and flip exactly this union; flips do not trigger further captures.

```
captures(m, player):
  if m occupied or out of bounds: return empty
  for each of eight directions:
    collect contiguous opponent discs
    if collection nonempty and next cell friendly: add collection
  return collected captures
transition(state, move):
  if pass: require no legal move; swap player, increment pass count
  else: require legal move; place and flip; swap player, reset passes
terminal(state): neither player has a legal move
```

An 8×8 legal-move scan examines at most 64 squares × 8 rays × 7 cells. Generalized n×n representation: O(n³) ray scanning, O(n²) state storage. Passes do not consume a placement search depth. Winner is the sign of Black minus White occupied discs. We report occupied-disc counts, leaving unoccupied squares unawarded; this never changes the winner.

## Seeded random baseline

Enumerate all legal moves, select uniformly with a local seeded RNG, or pass if there are none. If there are k moves, each is selected with probability 1/k. The same seed and state trajectory reproduce the same choices. Pseudocode: `moves=legal(state); return rng.choice(moves) if moves else pass`. Runtime is legal-move generation plus O(1) selection; memory is the move list. It assumes no positional information and provides a deliberately weak playing baseline; one finite random run does not estimate every possible random outcome.

## Handcrafted evaluator

Let p be the evaluation player and o the opponent. For counts a,b define D(a,b)=(a-b)/(a+b), or 0 when both are zero. The feature vector φ is:

| Feature | Formula / definition | Manual weight | Reason |
| --- | --- | --- | --- |
| piece | D(number of p discs, number of o discs) | 0.05 | Material matters at termination but can be misleading early |
| mobility | D(legal moves for p, legal moves for o) | 0.25 | More immediate choices reduces forced weak moves |
| corner | (p corners − o corners)/4 | 0.30 | A corner cannot be captured because no ray extends beyond it |
| frontier | D(o frontier discs, p frontier discs) | 0.10 | Discs next to empties expose capture opportunities |
| position | Σ square_weight(i) × disc(i) × p / Σ abs(square_weight) | 0.10 | Coarse location preference |
| potential | D(empty squares adjacent to o, empties adjacent to p) | 0.10 | Approximates future mobility; does not imply current legality |
| danger | −(p minus o discs adjacent to empty corners)/12 | 0.10 | Discourages X/C squares while corners remain empty |

A frontier disc touches at least one empty square in any of eight directions. Potential mobility counts each empty square once. Positional categories are corner +4, its three immediate neighbors −3, remaining edge +2, and remaining interior +1. Their ratios encode a qualitative preference, not an empirical claim. Adjacent-to-corner penalties become inactive when that corner is owned; the coarse positional term remains static, a known limitation.

The score is E(s,p)=Σ wᵢφᵢ(s,p) / Σ |wᵢ|. Features are in [−1,1], so E is also bounded in [−1,1]. Feature signs favor p; reversing the perspective negates every feature. Each weight is an explicit, documented initial hypothesis. No phase weights or stable-disc approximation are included in this baseline. GA may evolve negative weights and challenge those hypotheses.

Terminal utility U(s,p)=2 × winner(s) × p + (BlackCount−WhiteCount) × p / 64. Thus every proven win scores above all nonterminal evaluations, and disc margin breaks terminal ties. This objective slightly prefers larger wins and smaller losses; it is shared by all engines.

Feature extraction scans the board and generates both players' legal moves. On this fixed board its cost is bounded; generalized board complexity is O(n³). Greedy evaluation selects the maximum one-placement child score, identical to depth-one Minimax.

## Minimax

Minimax chooses the move with the best guaranteed value assuming both players optimize the same zero-sum utility. For fixed root perspective p:

V(s,d,p) = U(s,p) if terminal;
V(s,d,p) = V(pass(s),d,p) if no legal move;
V(s,0,p) = E(s,p);
V(s,d,p) = maxₘ V(T(s,m),d−1,p) when turn=p;
V(s,d,p) = minₘ V(T(s,m),d−1,p) otherwise.

```
visit(s,d):
  if terminal: return U
  if no move: return visit(pass(s),d)
  if d=0: return E
  values = [visit(child,d−1) for each legal move]
  return max(values) on MAX turn, min(values) on MIN turn
root: choose largest exact child value; smallest row-major move wins a tie
```

Induction on remaining placements proves optimality for the finite tree: terminal/cutoff values are given; each MAX/MIN node chooses its optimal child. This proves optimality relative to the cutoff evaluator, not perfect play beyond the horizon. Time O(bᵈ), depth-first space O(bd) for stored children/state copies. The constant includes rules and feature extraction. Passes can add turn nodes without adding placements.

## Alpha-Beta

Alpha-Beta computes the same recurrence while omitting branches unable to influence an ancestor choice. α is a lower bound established by MAX; β is an upper bound established by MIN. At a MAX node update α=max(α,best); at a MIN node update β=min(β,best). Cut off remaining siblings when α≥β.

```
visit(s,d,α,β):
  apply identical terminal, pass and cutoff cases
  best = −∞ at MAX, +∞ at MIN
  for ordered legal child:
    v = visit(child,d−1,α,β)
    best = max(best,v) or min(best,v)
    update α at MAX, β at MIN
    if α≥β: stop remaining siblings
  return best
```

A pruned subtree cannot improve the controlling ancestor's bound, so pruning preserves its decision. This implementation searches each root candidate with a fresh [−∞,+∞] window, obtaining exact candidate values before resolving ties. This costs more than carrying root alpha forward, but protects canonical selected-move equivalence across ordering modes. Naively treating returned bounds as exact tied root values can choose a wrong move.

Order modes: ascending row-major; corners then descending positional weights; additionally ascending opponent mobility among tied square categories. Worst-case O(bᵈ); ideal ordering approximately O(b^(d/2)). Space O(bd). Mobility ordering spends extra rule-generation work and may lose runtime despite saving nodes. Correctness tests compare value AND move at identical depth, including forced passes and terminal states; benchmarks assert this again.

Pruning percentage = 100 × (Minimax visited nodes − Alpha-Beta visited nodes) / Minimax visited nodes. This is the known total reduction, unlike the count of skipped immediate children. Timings are measurements on one machine and are not universal performance promises.

## Genetic algorithm

A chromosome is seven real feature weights, in `FEATURES` order. Normalize by L1 norm to remove irrelevant overall scale. Initial population contains the manual vector and Gaussian perturbations. Fitness F = (wins + 0.5 draws)/games, from actual games at equal depth, swapped colors and common seeded openings.

```
initialize population and seed RNG
for generation:
  freeze opponents: manual baseline, previous champion, sampled population member
  play every candidate against panel with identical paired openings
  score actual wins/draws
  choose generation champion; assess on fixed validation seeds
  preserve champion unchanged (elitism)
  while next population incomplete:
    choose each parent by size-3 tournament selection
    child = t parent1 + (1−t) parent2, t uniform in [0,1]
    independently mutate each gene with probability 0.3:
      gene += Normal(0,0.1)
    L1-normalize child
  replace population
save best champion by validation score, retaining earlier champion on ties
```

Tournament selection samples with replacement and keeps the highest fitness. Arithmetic crossover blends genes. Mutation adds variation; elitism retains the current best chromosome. Diversity is the mean population standard deviation across genes. All operators use a local seeded RNG.

With population P, generations G, O opponents and S paired openings, there are 2GPOS fitness games plus validation games. Search cost dominates, roughly O(GPOS L bᵈ), where L is game length. Storing per-generation populations costs O(GP×7); game outcome records add O(GPOS).

Assumptions: actual game results approximate weight quality; the finite opponent panel represents relevant play; fixed-depth budget is appropriate. Limitations: noisy/small panels, co-adaptation, possible validation overfitting, fitness plateaus, and no guarantee of global optimum. Training-panel scores across generations have different opponents; the fixed-panel validation curve is the comparable one. Final evaluator tournaments use a third seed family.

## Dataset reconstruction and split

The authoritative public source and binary layout are linked in `docs/dataset.md`. WTHOR stores compact move records; replay all placements through our rules, inserting forced passes. Label each sampled state from the recorded game outcome, flipped to the current player's perspective. Sample every fourth placement from placement 16.

```
validate header/record size and move encoding
for each source game:
  replay legal moves and forced passes
  group by symmetric relative position after placement 12
  sample states after placements 16,20,…
hash (seed, group) to train / validation / test, approximately 70/15/15
remove symmetric duplicates inside each split
remove later-split states within 2 cell differences of earlier splits
save numeric arrays, outcome labels, game IDs, manifest and hashes
```

Eight dihedral board symmetries are used. Near matches are checked by indexing three disjoint cell bands: at most two mismatches leave one band exactly matching, so every distance≤2 candidate is checked. Actual distance is then verified. This handles near-identical states under any symmetry. Same games and shared-opening groups never cross splits. Ratios may depart from 70/15/15 because entire groups are assigned.

Reconstruction O(number of moves × move-generation cost). Near lookup worst case quadratic in samples if bands collide heavily; the small pilot avoids that scale. Memory O(samples). Hamming distance≤2 is an operational definition of near-identical, not a claim that all strategic similarity is eliminated. Longer-range similarities and shared human players still exist. Duplicate outcomes can conflict; within-split exact duplicates retain the first deterministically, a documented source of label variance/bias.

## Neural value network

Input x has 64 cells relative to side to move: own=1, opponent=−1, empty=0. Othello is symmetric between colors, so a separate absolute color bit is unnecessary. Inputs already have bounded scale. No pretrained model or AutoML is used.

Forward propagation:

h₁=ReLU(W₁x+b₁), h₂=ReLU(W₂h₁+b₂), v=tanh(W₃h₂+b₃).

Architecture 64→128→64→1 has 16,641 learned parameters. ReLU(z)=max(0,z); tanh bounds predictions to [−1,1]. Target y is −1/0/+1 for eventual recorded loss/draw/win, from side-to-move perspective. Loss L=(1/N)Σ(vᵢ−yᵢ)². Under this loss the population optimum estimates E[y|x], a continuous expected outcome.

Backpropagation computes gradients by the chain rule. For tanh, dv/dz=1−v²; for ReLU, derivative is 1 for z>0 and 0 otherwise (zero at the nondifferentiable origin by convention). Output error dL/dv=2(v−y)/N. Chain through each matrix multiplication to compute dL/dW and dL/db.

Adam maintains first and second gradient moments: mₜ=β₁mₜ₋₁+(1−β₁)gₜ; vₜ=β₂vₜ₋₁+(1−β₂)gₜ², bias-corrects them, and updates θ←θ−η m̂/(√v̂+ε). PyTorch performs tensor operations, differentiation and Adam; the architecture, forward equations, target, training loop and split are explicit.

```
seed RNGs; use CPU deterministic tensor algorithms
for epoch:
  shuffle training samples deterministically
  for batch: forward → MSE → zero gradients → backward → optimizer step
  evaluate validation loss without gradients
  save checkpoint if validation improves
restore minimum-validation-loss checkpoint
evaluate test set once; save metrics and source/checkpoint hashes
```

One forward pass is O(64×128+128×64+64); backprop is the same order with larger constants. Training O(epochs × samples × parameters), memory O(parameters + batch activations + loaded samples). Track MSE, MAE, Pearson correlation and secondary outcome accuracy using thresholds −1/3,+1/3. This is regression; classification accuracy is not the training objective. The mean training outcome is the offline constant baseline.

Overfitting means training error improves while held-out generalization degrades. The pilot shows it clearly, so checkpoint selection uses validation loss rather than the last epoch. Future regularization/data changes must be chosen on validation; reserve a new final test set if repeatedly tuning after examining pilot test metrics. Human-game outcomes include policy noise and are not perfect-play values.

The neural Alpha-Beta engine changes only the leaf evaluator. Prediction v is from leaf side-to-move perspective; return v × leaf.turn × root.player. Search handles all legal moves, passes, budgets and terminal utility identically. The model need not generate moves or understand Alpha-Beta to estimate leaves.

## Experiments and time mode

A game transcript stores the initial serialized board, each chosen move and search result, and final state. Replay must reproduce the final state. Pair each seeded random opening with swapped engine colors. Seeds are shared across opponents; agents use separate seeded RNGs. Tournament statistics include W/L/D, raw win rate W/N, score rate (W+0.5D)/N, average game length, per-move runtime/nodes, total nodes and color performance.

Repeated games from the same deterministic opening create no new independent evidence. Use many distinct opening seeds; pair colors. Equal-depth comparisons isolate leaf evaluation at a shared search horizon; equal-time comparisons study practical speed/quality and can reach different depths. Both are fair but answer different questions. Random and greedy are contextual baselines.

Iterative time mode repeats depth 1,2,… until the configured maximum or deadline. Keep only the last completed result. Include work from interrupted searches in cost counters. Complexity remains exponential in the deepest attempted depth; additional shallower iterations add overhead. The benchmark records overhead and confirms completed-depth equivalence. No performance benefit is claimed for this mode; it exists to support the required configurable time budget. No transposition tables, hashing, killer/history heuristics or aspiration windows are included.
