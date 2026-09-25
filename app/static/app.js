/** Browser client for starting planning runs and rendering live progress. */

const form = document.querySelector('#goal-form');
const objective = document.querySelector('#objective');
const workspace = document.querySelector('#workspace');
const submitButton = document.querySelector('#submit-button');
const statusBadge = document.querySelector('#run-status');
const healthBadge = document.querySelector('.health');
const charCount = document.querySelector('#char-count');
let pollTimer;

fetch('/api/health')
  .then(response => response.json())
  .then(data => {
    document.querySelector('#mode').textContent = data.configured
      ? `${data.mode} · ${data.model}`
      : 'EURI · setup required';
    healthBadge.classList.add(data.configured ? 'ready' : 'offline');
  })
  .catch(() => {
    document.querySelector('#mode').textContent = 'Agent offline';
    healthBadge.classList.add('offline');
  });

objective.addEventListener('input', () => {
  charCount.textContent = `${objective.value.length.toLocaleString()} / 4,000`;
});

objective.addEventListener('keydown', event => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') form.requestSubmit();
});

document.querySelectorAll('.example-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    objective.value = chip.dataset.prompt;
    objective.dispatchEvent(new Event('input'));
    objective.focus();
  });
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  clearTimeout(pollTimer);
  setSubmitting(true);
  workspace.classList.remove('hidden');
  document.querySelector('#tasks').innerHTML = loadingTask();
  document.querySelector('#run-title').textContent = objective.value;
  updateStatus('planning');
  document.querySelector('#final').classList.add('hidden');
  workspace.scrollIntoView({ behavior: 'smooth', block: 'start' });

  try {
    const response = await fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ objective: objective.value }),
    });
    const data = await response.json();
    if (!response.ok) {
      const message = response.status === 503
        ? `${data.detail || 'The model provider is not configured.'} Start the server with DEMO_MODE=true, or add EURI_API_KEY to .env.`
        : data.detail || 'Could not start the run.';
      throw new Error(message);
    }
    poll(data.run_id);
  } catch (error) {
    showError(error.message);
    setSubmitting(false);
  }
});

/** Fetch and render a run repeatedly until it reaches a terminal state. */
async function poll(runId) {
  try {
    const response = await fetch(`/api/runs/${runId}`);
    const run = await response.json();
    if (!response.ok) throw new Error(run.detail || 'Could not read this run.');
    render(run);
    if (!['completed', 'failed'].includes(run.status)) {
      pollTimer = setTimeout(() => poll(runId), 900);
    } else {
      setSubmitting(false);
    }
  } catch (error) {
    showError(error.message);
    setSubmitting(false);
  }
}

/** Render task progress, final output, and errors from an agent-state payload. */
function render(run) {
  updateStatus(run.status);
  updatePipeline(run.status, run.tasks);

  if (run.tasks.length) {
    document.querySelector('#tasks').innerHTML = run.tasks.map((task, index) => `
      <div class="task ${escapeHtml(task.status)}">
        <span class="task-num">${task.status === 'completed' ? '✓' : String(index + 1).padStart(2, '0')}</span>
        <div>
          <h3>${escapeHtml(task.title)}</h3>
          <p>${escapeHtml(task.description)} · ${task.attempts} attempt${task.attempts === 1 ? '' : 's'}</p>
        </div>
        <span class="pill">${escapeHtml(task.tool)} · ${escapeHtml(task.status)}</span>
      </div>`).join('');
  }

  if (run.final_response) {
    document.querySelector('#final').classList.remove('hidden');
    document.querySelector('#final-text').textContent = run.final_response;
  }
  if (run.error) showError(run.error);
}

/** Update the run badge without rebuilding its decorative status indicator. */
function updateStatus(status) {
  statusBadge.dataset.status = status;
  statusBadge.innerHTML = `<i></i> ${escapeHtml(status)}`;
}

/** Highlight pipeline stages based on current run and task state. */
function updatePipeline(status, tasks = []) {
  const steps = document.querySelectorAll('.pipeline-step');
  const hasRunningTask = tasks.some(task => task.status !== 'pending');
  const activeCount = status === 'completed' ? 4 : hasRunningTask ? 3 : 2;
  steps.forEach((step, index) => step.classList.toggle('active', index < activeCount));
}

/** Toggle the composer button between idle and active execution states. */
function setSubmitting(isSubmitting) {
  submitButton.disabled = isSubmitting;
  submitButton.querySelector('.button-label').textContent = isSubmitting
    ? 'Atlas is working…'
    : 'Build & execute plan';
  submitButton.querySelector('.button-icon').textContent = isSubmitting ? '···' : '→';
}

/** Return the initial planning card displayed while the first plan is generated. */
function loadingTask() {
  return `
    <div class="task running loading-card">
      <span class="task-num">✦</span>
      <div><h3>Building your plan</h3><p>Atlas is decomposing the objective into executable tasks.</p></div>
      <span class="pill">Planning</span>
    </div>`;
}

/** Display an escaped error message and mark the visible run as failed. */
function showError(message) {
  updateStatus('failed');
  const tasks = document.querySelector('#tasks');
  const configurationError = /API key|EURI_API_KEY|DEMO_MODE|not configured/i.test(message);
  tasks.querySelector('.loading-card')?.remove();
  tasks.querySelector('.error-card')?.remove();
  tasks.insertAdjacentHTML('beforeend', `
    <div class="task failed error-card">
      <span class="task-num">!</span>
      <div><h3>${configurationError ? 'EURI setup required' : 'This run could not be completed'}</h3><p>${escapeHtml(message)}</p></div>
      <span class="pill">${configurationError ? 'Configuration' : 'Run failed'}</span>
    </div>`);
}

/** Convert an arbitrary value into HTML-safe text for template insertion. */
function escapeHtml(value) {
  const node = document.createElement('div');
  node.textContent = value ?? '';
  return node.innerHTML;
}
