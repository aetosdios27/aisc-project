const $ = id => document.getElementById(id);
const engines = {'random':'Random · seeded baseline','manual-greedy':'Manual heuristic · greedy','manual-minimax':'Minimax + manual heuristic','manual-ab':'Alpha-Beta + manual heuristic','ga-ab':'Alpha-Beta + evolved heuristic','neural-ab':'Alpha-Beta + neural evaluator'};
let state, busy = false, playing = false, lastMove = null, sequence = 0, game = [], autoToken = 0;
for (const id of ['black-engine','white-engine']) {
  for (const [value,text] of Object.entries(engines)) $(id).add(new Option(text,value));
  $(id).value = id === 'black-engine' ? 'ga-ab' : 'manual-ab';
}
const coord = m => m === null ? 'Pass' : 'abcdefgh'[m % 8] + (Math.floor(m / 8) + 1);
const engine = () => $(state.turn === 1 ? 'black-engine' : 'white-engine').value;
function render() {
  const humanTurn = $('mode').value === 'human' && state.turn === 1;
  $('board').replaceChildren();
  for (let i=0;i<64;i++) {
    const cell = document.createElement('button');
    const legal = state.legal.includes(i) && !state.terminal;
    cell.className = `square${legal ? ' legal':''}${lastMove === i ? ' last':''}`;
    cell.setAttribute('aria-label', `${coord(i)}, ${state.cells[i] === 1 ? 'Black disc' : state.cells[i] === -1 ? 'White disc' : legal ? 'legal move' : 'empty'}`);
    cell.disabled = busy || playing || !humanTurn || !legal;
    if (state.cells[i]) {
      const piece = document.createElement('span'); piece.className = 'piece '+(state.cells[i] === 1 ? 'black':'white'); cell.append(piece);
    } else if (legal) {const dot=document.createElement('span');dot.className='legal-dot';cell.append(dot);}
    cell.onclick = () => action('move', i);
    $('board').append(cell);
  }
  $('black-score').textContent = state.counts.black;
  $('white-score').textContent = state.counts.white;
  $('legal-count').textContent = `${state.legal.length} legal moves`;
  $('turn').textContent = state.terminal ? (state.winner === 0 ? 'Draw' : `${state.winner === 1 ? 'Black':'White'} wins`) : `${state.turn === 1 ? 'Black':'White'} to move`;
  $('pass').disabled = busy || playing || state.terminal || state.legal.length > 0 || !humanTurn;
  $('step').disabled = busy || playing || state.terminal || humanTurn;
  $('analyze').disabled = busy || playing || state.terminal;
  $('new-game').disabled = busy;
  $('mode').disabled = busy || playing;
  $('autoplay').disabled = state.terminal;
  $('autoplay').textContent = playing ? 'Ⅱ Pause' : '▶ Auto play';
  $('black-control').hidden = $('mode').value !== 'ai';
  $('features').replaceChildren();
  for (const [name,f] of Object.entries(state.features)) {
    const div=document.createElement('div');div.className='feature';
    div.innerHTML=`<span>${name}</span><strong>${f.contribution >= 0 ? '+':''}${f.contribution.toFixed(3)}</strong><div class="bar"><i class="${f.contribution < 0 ? 'negative':''}" style="width:${Math.min(Math.abs(f.contribution)*300,100)}%"></i></div>`;
    div.title=`Feature ${f.value.toFixed(4)} × weight ${f.weight.toFixed(4)} / total absolute weight`;
    $('features').append(div);
  }
  if (state.search) {
    const s=state.search;
    $('selected').textContent=coord(s.move);
    $('evaluation').textContent=`${s.value>=0?'+':''}${s.value.toFixed(4)}`;
    $('nodes').textContent=s.nodes.toLocaleString();$('cutoffs').textContent=s.cutoffs.toLocaleString();
    $('skipped').textContent=s.skipped_children.toLocaleString();$('time').textContent=(s.seconds*1000).toFixed(1)+' ms';$('completed').textContent=s.completed_depth;
  }
}
function status(message) {$('status').textContent=message;}
async function action(actionName,move) {
  if (busy) return;
  busy=true;render();status('Engine running…');
  try {
    const before=state.board;
    const payload={action:actionName,board:before,depth:Number($('depth').value),engine:engine(),seed:Number($('seed').value)+sequence};
    if (actionName==='move') payload.move=move;
    const response=await fetch('/api/game',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await response.json();if(!response.ok) throw new Error(data.error || 'Request failed');
    state=data;
    if (actionName!=='analyze') {lastMove=actionName==='move'?move:data.search?.move;game.push({initial:before,move:lastMove,search:data.search || null});sequence++;}
    status(state.terminal ? `${state.winner===0?'Draw':state.winner===1?'Black wins':'White wins'}. Final disc count: ${state.counts.black}–${state.counts.white}.` : `${actionName==='analyze'?'Suggested':'Played'} ${coord(actionName==='move'?move:state.search?.move ?? null)}. ${state.turn===1?'Black':'White'} to move.`);
  } catch(e) {playing=false;status(e.message);} finally {busy=false;render();}
}
async function autoplay() {
  playing=!playing;const token=++autoToken;render();
  while(playing && token===autoToken && !state.terminal) {
    if($('mode').value==='human' && state.turn===1) {playing=false;break;}
    await action('step');
    await new Promise(resolve=>setTimeout(resolve,250));
  }
  if(token===autoToken) {playing=false;render();}
}
async function reset() {
  playing=false;autoToken++;
  try {const response=await fetch('/api/state');state=await response.json();lastMove=null;game=[];sequence=0;
    for(const id of ['selected','evaluation','nodes','cutoffs','skipped','time','completed']) $(id).textContent='—';
    render();status('Choose a legal square to begin.');
  } catch(e){status(e.message);}
}
$('new-game').onclick=reset;$('pass').onclick=()=>action('move',null);$('step').onclick=()=>action('step');$('analyze').onclick=()=>action('analyze');$('autoplay').onclick=autoplay;
$('mode').onchange=()=>{playing=false;render();};
$('export').onclick=()=>{const blob=new Blob([JSON.stringify({seed:Number($('seed').value),mode:$('mode').value,initial:game[0]?.initial || state.board,turns:game,final:state.board},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='othello-game.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
async function results() {
  try {
    const response=await fetch('/api/results');const data=await response.json();
    if(!data.tournament){$('experiment-description').textContent='No tournament artifact yet. Run the reproducible experiment suite to populate this view.';return;}
    const config=data.tournament.config;
    $('experiment-description').textContent=`Pilot evidence · ${config.games_per_pair} games per pairing · depth ${config.depth} · alternating colors · shared seeded openings. Small samples do not establish general superiority.`;
    const wrap=document.createElement('div');wrap.className='table-scroll';
    const table=document.createElement('table');table.innerHTML='<thead><tr><th>Engine</th><th>W / D / L</th><th>Win rate</th><th>Score rate</th><th>Nodes / move</th><th>Time / move</th><th>Black / White score</th></tr></thead>';
    const tbody=document.createElement('tbody');
    for(const [name,r] of Object.entries(data.tournament.summary)) {
      const tr=document.createElement('tr');
      for(const value of [name,`${r.wins} / ${r.draws} / ${r.losses}`,`${(r.win_rate*100).toFixed(1)}%`,`${(r.score_rate*100).toFixed(1)}%`,Math.round(r.average_nodes).toLocaleString(),`${(r.average_search_seconds*1000).toFixed(1)} ms`,`${(r.colors.black.score_rate*100).toFixed(0)}% / ${(r.colors.white.score_rate*100).toFixed(0)}%`]) {const td=document.createElement('td');td.textContent=value;tr.append(td);}tbody.append(tr);
    }table.append(tbody);wrap.append(table);$('results-table').replaceChildren(wrap);
    $('pair-results').replaceChildren();
    for(const [name,pair] of Object.entries(data.tournament.pairs)) {
      if(!Object.keys(pair.engines).every(n=>['manual-ab','ga-ab','neural-ab'].includes(n)))continue;
      const div=document.createElement('div');div.className='pair-row';const label=document.createElement('span');label.textContent=name;const value=document.createElement('strong');value.textContent=Object.entries(pair.engines).map(([n,s])=>`${n}: ${(s/pair.games*100).toFixed(0)}%`).join(' · ');div.append(label,value);$('pair-results').append(div);
    }
    const charts=[['nodes','Minimax and Alpha-Beta search the same positions. Node counts are visited states.'],['runtime','Wall time depends on the machine; node counts provide the reproducible comparison.'],['manual_ga','Same Alpha-Beta implementation, depth and ordering; only the evaluator changes.'],['manual_neural','Neural outcome prediction is assessed by actual playing performance.'],['ga_neural','Both evaluators receive the same placement depth.'],['ga','Fixed validation seeds are separate from fitness seeds. Training panels change between generations.'],['neural',`Best checkpoint chosen on validation loss. Test MSE: ${data.neural?.test.mse.toFixed(3) ?? 'unavailable'}.`],['depth_strength','Intentional depth comparison against a fixed depth-one manual reference.'],['round_robin','Pooled performance includes opponents of different strengths. Use direct comparisons for the research question.']];
    $('charts').replaceChildren();
    for(const [name,caption] of charts){const div=document.createElement('div');div.className='chart';const img=document.createElement('img');img.src=`/plots/${name}.png`;img.alt=caption;img.loading='lazy';const p=document.createElement('p');p.textContent=caption;div.append(img,p);$('charts').append(div);}
  }catch(e){$('experiment-description').textContent=e.message;}
}
for(const [id,other,section] of [['lab-tab','experiments-tab','laboratory'],['experiments-tab','lab-tab','experiments']]) $(id).onclick=()=>{$(id).classList.add('active');$(other).classList.remove('active');$('laboratory').hidden=section!=='laboratory';$('experiments').hidden=section!=='experiments';if(section==='experiments')results();};
reset();
