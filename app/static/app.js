const form = document.querySelector('#goal-form');
const objective = document.querySelector('#objective');
const workspace = document.querySelector('#workspace');
let pollTimer;

fetch('/api/health').then(r => r.json()).then(data => {
  document.querySelector('#mode').textContent = `${data.mode} · ${data.model}`;
}).catch(() => document.querySelector('#mode').textContent = 'agent unavailable');

objective.addEventListener('keydown', event => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') form.requestSubmit();
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  clearTimeout(pollTimer);
  workspace.classList.remove('hidden');
  document.querySelector('#tasks').innerHTML = '<div class="task"><span class="task-num">··</span><div><h3>Building the plan</h3><p>Gemini is decomposing the objective.</p></div><span class="pill">planning</span></div>';
  document.querySelector('#run-title').textContent = objective.value;
  document.querySelector('#run-status').textContent = 'planning';
  document.querySelector('#final').classList.add('hidden');
  workspace.scrollIntoView({behavior: 'smooth'});
  try {
    const response = await fetch('/api/runs', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({objective:objective.value})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not start run');
    poll(data.run_id);
  } catch (error) { showError(error.message); }
});

async function poll(runId) {
  try {
    const response = await fetch(`/api/runs/${runId}`);
    const run = await response.json();
    render(run);
    if (!['completed','failed'].includes(run.status)) pollTimer = setTimeout(() => poll(runId), 900);
  } catch (error) { showError(error.message); }
}

function render(run) {
  document.querySelector('#run-status').textContent = run.status;
  if (run.tasks.length) document.querySelector('#tasks').innerHTML = run.tasks.map((task, i) => `
    <div class="task ${task.status}">
      <span class="task-num">${String(i+1).padStart(2,'0')}</span>
      <div><h3>${escapeHtml(task.title)}</h3><p>${escapeHtml(task.description)} · ${task.attempts} attempt${task.attempts === 1 ? '' : 's'}</p></div>
      <span class="pill">${escapeHtml(task.tool)} / ${task.status}</span>
    </div>`).join('');
  if (run.final_response) {
    document.querySelector('#final').classList.remove('hidden');
    document.querySelector('#final-text').textContent = run.final_response;
  }
  if (run.error) showError(run.error);
}

function showError(message) {
  document.querySelector('#run-status').textContent = 'failed';
  document.querySelector('#tasks').insertAdjacentHTML('beforeend', `<div class="task failed"><span class="task-num">!</span><div><h3>Run stopped</h3><p>${escapeHtml(message)}</p></div><span class="pill">error</span></div>`);
}

function escapeHtml(value) {
  const node = document.createElement('div'); node.textContent = value ?? ''; return node.innerHTML;
}
