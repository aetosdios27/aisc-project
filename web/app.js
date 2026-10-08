'use strict';

const $ = id => document.getElementById(id);
const ENGINES = {
  'random': { label: 'Random', description: 'Chooses uniformly from legal moves. It does not search or evaluate positions.' },
  'manual-greedy': { label: 'Manual · greedy', description: 'Chooses the best immediately resulting manual score. It always looks one placement ahead.' },
  'manual-minimax': { label: 'Manual · Minimax', description: 'Searches every branch to the selected depth, using seven explicit manual scoring features.' },
  'manual-ab': { label: 'Manual · Alpha-Beta', description: 'Manual scoring with pruning. Same move and value as Minimax at equal depth.' },
  'ga-ab': { label: 'Evolved · Alpha-Beta', description: 'Uses seven feature weights evolved through actual games. The Alpha-Beta search stays identical.' },
  'neural-ab': { label: 'Neural · Alpha-Beta', description: 'Uses a small network trained on public human-game outcomes. It changes leaf scoring, not the rules or search.' }
};
const FEATURES = {
  piece: ['Disc difference', 'Relative number of your discs and the opponent’s.'],
  mobility: ['Legal moves', 'Relative number of legal placements available to each player.'],
  corner: ['Corners', 'Corner ownership. A corner disc cannot be flipped.'],
  frontier: ['Exposed discs', 'Fewer discs adjacent to empty squares is favored.'],
  position: ['Square positions', 'A documented preference for corners and edges.'],
  potential: ['Potential mobility', 'Empty squares next to opponent discs, indicating future opportunities.'],
  danger: ['Corner risk', 'Avoids neighboring squares while their corner is empty.']
};
let state = null;
let busy = true;
let playing = false;
let lastMove = null;
let suggestedMove = null;
let lastSearch = null;
let sequence = 0;
let game = [];
let epoch = 0;
let autoToken = 0;
let resultsLoaded = false;

for (const id of ['black-engine', 'white-engine']) {
  for (const [value, item] of Object.entries(ENGINES)) $(id).add(new Option(item.label, value));
  $(id).value = id === 'black-engine' ? 'ga-ab' : 'manual-ab';
}
const playerName = player => player === 1 ? 'Black' : 'White';
const coord = move => move === null ? 'Pass' : 'abcdefgh'[move % 8] + (Math.floor(move / 8) + 1);
const signed = value => `${value >= 0 ? '+' : ''}${value.toFixed(3)}`;
const humanMode = () => $('mode').value === 'human';
const selectedEngine = () => humanMode() ? $('white-engine').value : $(state.turn === 1 ? 'black-engine' : 'white-engine').value;
const element = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

function status(message, error = false) {
  $('status').textContent = message;
  $('status').classList.toggle('error', error);
}

function instruction() {
  if (!state) return 'Loading the starting position…';
  if (state.terminal) return `${state.winner === 0 ? 'Draw' : `${playerName(state.winner)} wins`}. Final count: Black ${state.counts.black}, White ${state.counts.white}.`;
  if (!state.legal.length) return `${playerName(state.turn)} has no legal move and must pass.`;
  return humanMode() && state.turn === 1 ? 'Your turn. Choose a marked square.' : `${playerName(state.turn)} to move. Run one move or play continuously.`;
}

function renderSearch() {
  const fields = ['selected', 'nodes', 'evaluation', 'time', 'completed', 'cutoffs', 'skipped'];
  if (!lastSearch) {
    fields.forEach(id => { $(id).textContent = '—'; });
    $('search-title').textContent = 'AI decision';
    $('search-context').textContent = 'Analyze the board to see a suggested move and its search cost.';
    $('value-note').textContent = 'The value is an evaluation score, not a win probability.';
    return;
  }
  const search = lastSearch;
  const random = search.engine === 'random';
  $('search-title').textContent = search.kind === 'analyze' ? 'Position analysis' : 'Last AI move';
  $('search-context').textContent = `${ENGINES[search.engine]?.label || search.engine} · ${playerName(search.player)} · ${search.kind === 'analyze' ? 'current position' : 'position before the move'}`;
  $('selected').textContent = coord(search.move);
  $('nodes').textContent = search.nodes.toLocaleString();
  $('evaluation').textContent = random ? '—' : signed(search.value);
  $('time').textContent = search.seconds < 1 ? `${(search.seconds * 1000).toFixed(1)} ms` : `${search.seconds.toFixed(2)} s`;
  $('completed').textContent = random ? 'No search' : search.completed_depth;
  $('cutoffs').textContent = search.cutoffs.toLocaleString();
  $('skipped').textContent = search.skipped_children.toLocaleString();
  $('value-note').textContent = random ? 'Random chooses a legal move without evaluating the position.' : `Positive favors ${playerName(search.player)} in the searched position. This score is not a win probability.`;
}

function render() {
  const waiting = busy || !state;
  const settingsLocked = waiting || playing;
  for (const id of ['mode', 'black-engine', 'white-engine', 'depth', 'seed']) $(id).disabled = settingsLocked;
  $('new-game').disabled = busy;
  $('export').disabled = waiting;
  $('analyze').disabled = waiting || playing || state?.terminal;
  $('autoplay').hidden = humanMode();
  $('autoplay').disabled = !state || state.terminal || (waiting && !playing);
  $('autoplay').textContent = playing ? 'Pause after this move' : 'Play continuously';
  $('black-control').hidden = humanMode();
  $('white-label').textContent = humanMode() ? 'AI engine' : 'White engine';
  $('step').hidden = humanMode() && state?.turn === 1;
  $('step').disabled = waiting || playing || state?.terminal;
  document.querySelector('.run-controls').hidden = $('step').hidden && $('autoplay').hidden;
  $('step').textContent = busy ? 'Thinking…' : 'Play next AI move';
  $('engine-description').textContent = ENGINES[$('white-engine').value].description;
  const depth = Number($('depth').value);
  $('depth-note').textContent = depth >= 3
    ? `${depth} future placements. Deeper searches can take several seconds. Random ignores depth; greedy always uses one placement.`
    : 'Depth counts placements. Random ignores it; greedy always uses one.';
  if (!state) return;
  const humanTurn = humanMode() && state.turn === 1;
  const focusedMove = document.activeElement?.dataset?.move;
  $('board').replaceChildren();
  for (let move = 0; move < 64; move++) {
    const legal = state.legal.includes(move) && !state.terminal;
    const cell = element('button', `square${legal ? ' legal' : ''}${lastMove === move ? ' last' : ''}${suggestedMove === move ? ' suggested' : ''}`);
    cell.dataset.move = String(move);
    cell.setAttribute('aria-label', `${coord(move)}, ${state.cells[move] === 1 ? 'Black disc' : state.cells[move] === -1 ? 'White disc' : legal ? 'legal move' : 'empty'}`);
    cell.disabled = waiting || playing || !humanTurn || !legal;
    if (state.cells[move]) cell.append(element('span', `piece ${state.cells[move] === 1 ? 'black' : 'white'}`));
    else if (legal) cell.append(element('span', 'legal-dot'));
    cell.onclick = () => action('move', move);
    $('board').append(cell);
  }
  if (focusedMove !== undefined && humanTurn && !waiting) {
    const target = $('board').querySelector(`[data-move="${focusedMove}"]:not(:disabled)`) || $('board').querySelector('button:not(:disabled)');
    target?.focus({ preventScroll: true });
  }
  $('board').setAttribute('aria-busy', String(busy));
  $('black-score').textContent = state.counts.black;
  $('white-score').textContent = state.counts.white;
  $('black-role').textContent = humanMode() ? 'You' : ENGINES[$('black-engine').value].label;
  $('white-role').textContent = humanMode() ? 'AI' : ENGINES[$('white-engine').value].label;
  $('turn').textContent = state.terminal ? (state.winner === 0 ? 'Game drawn' : `${playerName(state.winner)} wins`) : humanTurn ? 'Your turn · Black' : `${playerName(state.turn)} to move`;
  $('legal-count').textContent = state.terminal ? 'Game over' : `${state.legal.length} legal ${state.legal.length === 1 ? 'move' : 'moves'}`;
  $('pass').hidden = state.terminal || state.legal.length > 0 || !humanTurn;
  $('pass').disabled = waiting || playing || state.terminal || state.legal.length > 0 || !humanTurn;
  $('manual-score').textContent = signed(state.manual_evaluation);
  $('feature-perspective').textContent = `Manual score for ${playerName(state.turn)} in the current position. This explanation always uses the manual evaluator, regardless of the selected AI.`;
  $('features').replaceChildren();
  for (const [name, feature] of Object.entries(state.features)) {
    const row = element('tr');
    const first = element('td');
    first.append(element('span', 'feature-name', FEATURES[name][0]), element('span', 'feature-description', FEATURES[name][1]));
    row.append(first);
    for (const value of [feature.value, feature.weight]) row.append(element('td', 'mono', signed(value)));
    row.append(element('td', `mono ${feature.contribution >= 0 ? 'positive' : 'negative'}`, signed(feature.contribution)));
    $('features').append(row);
  }
  renderSearch();
}

async function request(path, payload) {
  const response = await fetch(path, payload === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function seedValue() {
  const seed = Number($('seed').value);
  if ($('seed').value === '' || !Number.isSafeInteger(seed) || seed < 0 || seed > 2147483647) {
    throw new Error('Use a whole-number seed from 0 to 2147483647.');
  }
  return seed;
}

async function action(kind, move) {
  if (busy || !state || state.terminal) return false;
  let payload;
  try {
    payload = { action: kind, board: state.board, depth: Number($('depth').value), engine: selectedEngine(), seed: seedValue() + sequence };
    if (kind === 'move') payload.move = move;
  } catch (error) { status(error.message, true); return false; }
  const token = epoch;
  const before = state.board;
  const player = state.turn;
  busy = true;
  render();
  status(kind === 'move' ? 'Placing your disc…' : `${playerName(player)} is thinking…`);
  let succeeded = false;
  try {
    const data = await request('/api/game', payload);
    if (token !== epoch) return false;
    state = data;
    suggestedMove = kind === 'analyze' ? data.search?.move ?? null : null;
    lastSearch = data.search ? { ...data.search, player, kind } : null;
    if (kind !== 'analyze') {
      lastMove = kind === 'move' ? move : data.search.move;
      game.push({ player, move: lastMove, initial: before, final: data.board, engine: kind === 'move' ? 'human' : payload.engine,
        requested_depth: payload.depth, seed: payload.seed, search: data.search || null });
      sequence++;
    }
    const played = kind === 'move' ? move : data.search.move;
    status(kind === 'analyze' ? `Suggested move: ${coord(played)} for ${playerName(player)}. The board is unchanged.` : state.terminal ? instruction() : `${playerName(player)} ${played === null ? 'passed' : `played ${coord(played)}`}. ${instruction()}`);
    succeeded = true;
  } catch (error) {
    if (token === epoch) { playing = false; autoToken++; status(error.message, true); }
  } finally {
    if (token === epoch) { busy = false; render(); }
  }
  if (succeeded && kind === 'move' && humanMode() && !state.terminal && state.turn === -1 && token === epoch) {
    await action('step');
  }
  return succeeded;
}

async function autoplay() {
  if (playing) {
    playing = false;
    autoToken++;
    render();
    status(busy ? 'Pausing after the current move finishes…' : `Paused. ${instruction()}`);
    return;
  }
  if (busy || !state || state.terminal || humanMode()) return;
  const token = ++autoToken;
  const gameEpoch = epoch;
  playing = true;
  render();
  while (playing && token === autoToken && gameEpoch === epoch && !state.terminal) {
    if (!await action('step')) break;
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  if (token === autoToken) { playing = false; render(); }
}

async function reset() {
  if (busy && state) return;
  const token = ++epoch;
  autoToken++;
  playing = false;
  busy = true;
  render();
  status('Loading the starting position…');
  try {
    const data = await request('/api/state');
    if (token !== epoch) return;
    state = data;
    lastMove = suggestedMove = lastSearch = null;
    game = [];
    sequence = 0;
    status(instruction());
  } catch (error) { if (token === epoch) status(error.message, true); }
  finally { if (token === epoch) { busy = false; render(); } }
}

function changeSettings() {
  if (busy || playing || !state) return;
  if (lastSearch?.kind === 'analyze') lastSearch = null;
  suggestedMove = null;
  render();
  status(instruction());
}
$('new-game').onclick = reset;
$('pass').onclick = () => action('move', null);
$('step').onclick = () => action('step');
$('analyze').onclick = () => action('analyze');
$('autoplay').onclick = autoplay;
for (const id of ['mode', 'white-engine', 'black-engine', 'depth', 'seed']) $(id).onchange = changeSettings;
$('export').onclick = () => {
  if (!state || busy) return;
  const content = { format: 'othello-ai-game-v1', initial: game[0]?.initial || state.board, turns: game, final: state.board,
    terminal: state.terminal, winner: state.winner };
  const url = URL.createObjectURL(new Blob([JSON.stringify(content, null, 2)], { type: 'application/json' }));
  const link = element('a'); link.href = url; link.download = 'othello-game.json'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

function showTab(id) {
  const laboratory = id === 'lab-tab';
  for (const buttonId of ['lab-tab', 'experiments-tab']) {
    const selected = buttonId === id;
    $(buttonId).classList.toggle('active', selected);
    $(buttonId).setAttribute('aria-selected', String(selected));
    $(buttonId).tabIndex = selected ? 0 : -1;
  }
  $('laboratory').hidden = !laboratory;
  $('experiments').hidden = laboratory;
  if (!laboratory && !resultsLoaded) results();
}
for (const id of ['lab-tab', 'experiments-tab']) {
  $(id).onclick = () => showTab(id);
  $(id).onkeydown = event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 'lab-tab' : event.key === 'End' ? 'experiments-tab' : id === 'lab-tab' ? 'experiments-tab' : 'lab-tab';
    showTab(next); $(next).focus();
  };
}
$('compare-link').onclick = () => { showTab('experiments-tab'); $('experiments-tab').focus(); window.scrollTo(0, 0); };

function comparisonCards(data) {
  const pairings = [['manual-ab', 'ga-ab'], ['manual-ab', 'neural-ab'], ['ga-ab', 'neural-ab']];
  const names = { 'manual-ab': 'Manual', 'ga-ab': 'Evolved', 'neural-ab': 'Neural' };
  $('pair-results').replaceChildren();
  for (const [first, second] of pairings) {
    const pair = data.tournament.pairs?.[[first, second].sort().join(' / ')];
    if (!pair || !pair.games) continue;
    const card = element('article', 'comparison-card');
    card.append(element('h3', '', `${names[first]} vs ${names[second]}`));
    const rate = pair.engines[first] / pair.games;
    for (const [name, value] of [[first, rate], [second, 1 - rate]]) {
      const row = element('div', 'comparison-score');
      row.append(element('span', '', names[name]), element('strong', '', `${(value * 100).toFixed(1)}%`));
      card.append(row);
    }
    const bar = element('div', 'score-bar'); bar.setAttribute('aria-hidden', 'true');
    const fill = element('i'); fill.style.width = `${rate * 100}%`; bar.append(fill); card.append(bar);
    card.append(element('p', 'hint', `${pair.games} games · score rate, draw = ½`));
    const interval = Array.isArray(data.analysis?.pairings) && typeof data.tournament.artifact_sha256 === 'string' && data.analysis.tournament_sha256 === data.tournament.artifact_sha256
      ? data.analysis.pairings.find(p => new Set([p.first, p.second]).has(first) && new Set([p.first, p.second]).has(second)) : null;
    if (interval) {
      const [low, high] = interval.first === first ? interval.first_score_interval95 : [1 - interval.first_score_interval95[1], 1 - interval.first_score_interval95[0]];
      card.append(element('p', 'hint', `${names[first]} 95% interval: ${(low * 100).toFixed(0)}–${(high * 100).toFixed(0)}%. ${interval.opening_pairs} paired openings.`));
    } else card.append(element('p', 'hint', 'Paired uncertainty has not been calculated for this artifact.'));
    $('pair-results').append(card);
  }
}

function resultsTable(data) {
  const wrap = element('div', 'table-scroll');
  const table = element('table');
  table.append(element('caption', '', 'Round-robin results. Win rate counts only wins; score rate also counts half the draws.'));
  const head = element('thead'); const headings = element('tr');
  for (const title of ['Engine', 'Win / draw / loss', 'Win rate', 'Score rate', 'Nodes / move', 'Time / move', 'Black / White score', 'Total nodes']) {
    const cell = element('th', '', title); cell.scope = 'col'; headings.append(cell);
  }
  head.append(headings); table.append(head);
  const body = element('tbody');
  for (const [name, row] of Object.entries(data.tournament.summary)) {
    const tr = element('tr');
    const values = [ENGINES[name]?.label || name, `${row.wins} / ${row.draws} / ${row.losses}`, `${(row.win_rate * 100).toFixed(1)}%`,
      `${(row.score_rate * 100).toFixed(1)}%`, Math.round(row.average_nodes).toLocaleString(), `${(row.average_search_seconds * 1000).toFixed(1)} ms`,
      `${(row.colors.black.score_rate * 100).toFixed(0)}% / ${(row.colors.white.score_rate * 100).toFixed(0)}%`, row.total_nodes.toLocaleString()];
    values.forEach(value => tr.append(element('td', '', value))); body.append(tr);
  }
  table.append(body); wrap.append(table); $('results-table').replaceChildren(wrap);
}

function charts(data) {
  const definitions = [
    ['Search efficiency', 'Minimax and Alpha-Beta must choose the same move and value. These measurements compare the work required on identical positions.', [
      ['nodes', 'Visited positions by search depth.'], ['runtime', 'Runtime by search depth. Wall time depends on the machine.']]],
    ['Evaluator comparisons', 'Direct paired games keep the same search protocol and change only the evaluator.', [
      ['manual_ga', 'Manual vs evolved evaluation.'], ['manual_neural', 'Manual vs neural evaluation.'], ['ga_neural', 'Evolved vs neural evaluation.']]],
    ['Learning progress', 'A changing training opponent panel can inflate GA fitness. Falling neural training loss can hide worse validation performance.', [
      ['ga', 'Compare the fixed validation curve across generations; the training panel changes.'],
      ['neural', `The checkpoint is chosen by validation loss. Test MSE: ${data.neural?.test?.mse?.toFixed(3) ?? 'unavailable'}. Lower is better.`]]],
    ['Depth and overall strength', 'These contextual studies answer different questions from the controlled evaluator comparisons.', [
      ['depth_strength', 'Candidate depth changes; the opponent remains a fixed depth-one manual engine.'],
      ['round_robin', 'Pooled score rates mix opponents of different strengths. Use direct pairings for the main research question.']]]
  ];
  $('charts').replaceChildren();
  if (!data.plots?.sources_match) {
    $('charts').append(element('p', 'hint', 'Charts have not been generated for this exact result snapshot. Regenerate plots before interpreting the curves.'));
    return;
  }
  for (const [index, [title, explanation, entries]] of definitions.entries()) {
    const group = element('details', 'chart-group'); group.open = index === 0;
    group.append(element('summary', '', title), element('p', '', explanation));
    const grid = element('div', 'chart-grid');
    for (const [name, caption] of entries) {
      const figure = element('figure', 'chart'); const image = element('img');
      image.src = `/plots/${name}.png`; image.alt = caption; image.loading = 'lazy';
      image.onerror = () => { image.hidden = true; figure.append(element('p', 'hint', 'Chart unavailable. Regenerate plots for this run.')); };
      figure.append(image, element('figcaption', '', caption)); grid.append(figure);
    }
    group.append(grid); $('charts').append(group);
  }
}

async function results() {
  try {
    const data = await request('/api/results');
    if (!data.tournament) { $('experiment-description').textContent = 'No tournament results are available yet. Run the experiment suite to populate this screen.'; return; }
    const config = data.tournament.config;
    const budget = config.time_budget == null ? `equal depth ${config.depth}` : `equal ${config.time_budget} s per move, maximum depth ${config.depth}`;
    $('experiment-description').textContent = `${config.status === 'pilot' ? 'Pilot' : 'Saved'} study · ${config.games_per_pair} games per pairing · ${budget} for search agents · shared seeded openings.`;
    comparisonCards(data); resultsTable(data); charts(data);
    resultsLoaded = true;
  } catch (error) {
    console.error('Experiment results failed to load', error);
    $('experiment-description').textContent = 'Results are temporarily unavailable. Switch tabs to retry. If this persists, restart the local server.';
  }
}
reset();
