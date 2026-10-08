// Execute the production renderer with a minimal DOM double, without a browser dependency.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
const renderer = source.slice(source.indexOf('function comparisonCards(data)'), source.indexOf('function resultsTable(data)'));

function setup() {
  const node = (tag, className, text) => ({tag, className, text, children: [], style: {},
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; }, setAttribute() {} });
  const container = node('div');
  const context = { $: () => container, element: node };
  vm.runInNewContext(renderer, context);
  return { render: context.comparisonCards, container };
}
function fixture() {
  return { tournament: {pairs: {
    'ga-ab / manual-ab': {games: 20, engines: {'ga-ab': 8, 'manual-ab': 12}},
    'manual-ab / neural-ab': {games: 20, engines: {'manual-ab': 17, 'neural-ab': 3}},
    'ga-ab / neural-ab': {games: 20, engines: {'ga-ab': 18.5, 'neural-ab': 1.5}}
  }}};
}
function text(node) { return [node.text || '', ...node.children.map(text)].join(' '); }

test('legacy response with no analysis or artifact hash still renders three comparisons', () => {
  const {render, container} = setup();
  assert.doesNotThrow(() => render(fixture()));
  assert.equal(container.children.length, 3);
  assert.match(text(container.children[0]), /60.0%/);
  assert.match(text(container.children[0]), /has not been calculated/);
});
test('missing analysis is valid even when the tournament has a hash', () => {
  const {render, container} = setup();
  const data = fixture(); data.tournament.artifact_sha256 = 'current';
  render(data);
  assert.equal(container.children.length, 3);
});
test('interval perspective is reversed correctly and stale analysis is not shown', () => {
  const {render, container} = setup();
  const data = fixture(); data.tournament.artifact_sha256 = 'current';
  data.analysis = {tournament_sha256: 'current', pairings: [{first: 'ga-ab', second: 'manual-ab', first_score_interval95: [.15, .6], opening_pairs: 10}]};
  render(data);
  assert.match(text(container.children[0]), /Manual 95% interval: 40–85%/);
  data.analysis.tournament_sha256 = 'old';
  render(data);
  assert.match(text(container.children[0]), /has not been calculated/);
});

test('a failed initial load leaves New game available to retry', () => {
  const nodes = {};
  const context = { busy: false, state: null, playing: false,
    $: id => nodes[id] ||= {value: id === 'white-engine' ? 'random' : '2'},
    document: {querySelector: () => ({})}, humanMode: () => true,
    ENGINES: {random: {description: 'Random baseline'}} };
  const renderSource = source.slice(source.indexOf('function render()'), source.indexOf('async function request('));
  vm.runInNewContext(renderSource, context);
  context.render();
  assert.equal(nodes['new-game'].disabled, false);
  assert.equal(nodes.export.disabled, true);
  assert.equal(nodes.analyze.disabled, true);
  context.busy = true;
  context.render();
  assert.equal(nodes['new-game'].disabled, true);
});
