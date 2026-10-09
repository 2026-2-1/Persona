const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state = null, detail = null, selectedPersona = null, selectedRun = null, selectedStep = null;
let initialized = false, refreshing = false, posting = false, manualRun = false, pendingJob = null;

const reasons = {
  verified_success: '완료 검증됨', agent_finished: '에이전트 완료 판단', agent_gave_up: '에이전트 중단',
  browser_error: '브라우저 오류', model_error: '모델 오류', max_steps: '단계 한도 도달',
  run_timeout: '실행 시간 초과', budget_exceeded: '호출 한도 도달', stuck: '반복 감지', interrupted: '중단됨'
};
const statusLabel = run => !run ? '대기' : run.active ? '실행 중' : reasons[run.termination_reason] || '실행 종료';
const statusClass = run => !run ? '' : run.active ? 'running' : run.verification === 'success' ? 'success' : 'failure';
const empty = text => `<div class="empty">${esc(text)}</div>`;

function notify(message, error = false) {
  $('notice').textContent = message;
  $('notice').classList.toggle('error', error);
}

async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(path, {...options, cache: 'no-store', signal: controller.signal});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `요청 실패 (${response.status})`);
    return data;
  } finally {
    clearTimeout(timeout);
  }
}

function isDemoUrl(value) {
  try {
    const url = new URL(value);
    return ['localhost', '127.0.0.1'].includes(url.hostname) && url.pathname.endsWith('shop.html');
  } catch { return false; }
}

function updateProvider() {
  if (!isDemoUrl($('target-url').value) && $('provider').value === 'mock') {
    $('provider').value = state?.providers?.jev ? 'jev' : 'gemini';
  }
  $('provider-note').textContent = $('provider').value === 'mock'
    ? 'Mock은 기본 데모 사이트 전용입니다. 페르소나는 무료 로컬 템플릿으로 생성합니다.'
    : '입력한 사이트에서 선택한 모델로 실행합니다. 페르소나는 무료 로컬 템플릿으로 생성합니다.';
}

function initializeSetup() {
  if (initialized) return;
  const g = state.generation || {};
  $('target-url').value = g.start_url || state.study.start_url || '';
  $('task-input').value = g.task || state.study.task || '';
  $('persona-count-input').value = g.requested_count || state.persona_defaults.count || 6;
  $('persona-background').value = g.background || state.persona_defaults.background || '';
  try {
    const saved = JSON.parse(localStorage.getItem('uxagent-dashboard-setup') || 'null');
    if (saved) {
      for (const id of ['target-url', 'task-input', 'persona-count-input', 'persona-background', 'provider']) {
        if (typeof saved[id] === 'string') $(id).value = saved[id];
      }
    }
  } catch { /* Local storage may be unavailable in private browser sessions. */ }
  initialized = true;
  updateProvider();
}

function chooseRun() {
  const job = state.job;
  if ($('follow-live').checked && job?.kind === 'batch') {
    const runs = state.runs.filter(run => (job.run_ids || []).includes(run.run_id));
    const run = runs.find(run => run.active) || runs[0];
    if (run || job.status === 'running') {
      if (selectedRun !== (run?.run_id || null)) selectedStep = null;
      selectedRun = run?.run_id || null;
      selectedPersona = run?.persona_id || null;
      return;
    }
  }
  if (manualRun) return;
  if (!selectedPersona && state.personas.length) selectedPersona = state.personas[0].persona_id;
  const persona = state.personas.find(p => p.persona_id === selectedPersona);
  const runId = persona ? persona.run?.run_id || null : state.runs[0]?.run_id || null;
  if (selectedRun !== runId) selectedStep = null;
  selectedRun = runId;
}

function renderStats() {
  const runs = state.runs, done = runs.filter(r => !r.active);
  const stats = [
    ['페르소나', `${state.personas.length}명`, '현재 생성된 참여자'],
    ['진행 중', `${runs.filter(r => r.active).length}명`, '브라우저 세션'],
    ['완료 검증', `${done.filter(r => r.verification === 'success').length}건`, '평가기로 확인된 성공'],
    ['총 액션', `${runs.reduce((sum, r) => sum + (r.action_attempts || 0), 0)}회`, '저장된 실행 기록 전체']
  ];
  $('stats').innerHTML = stats.map(s => `<div class="stat"><label>${esc(s[0])}</label><strong>${esc(s[1])}</strong><div class="hint">${esc(s[2])}</div></div>`).join('');
}

function renderPersonas() {
  $('persona-count').textContent = `${state.personas.length}명`;
  $('persona-list').innerHTML = state.personas.length ? state.personas.map(p => `
    <button class="persona ${p.persona_id === selectedPersona ? 'active' : ''}" data-persona="${esc(p.persona_id)}">
      <span class="avatar">${esc(p.persona_id.slice(-2))}</span>
      <span class="persona-copy"><span class="persona-name">${esc(p.persona_id)} · ${esc(p.digital_familiarity)}</span><span class="persona-meta">${esc(p.background)}</span></span>
      <span class="status-pill ${statusClass(p.run)}">${esc(statusLabel(p.run))}</span>
    </button>`).join('') : empty('설명과 인원을 입력하고 페르소나 생성을 누르세요.');
  $('persona-list').querySelectorAll('[data-persona]').forEach(button => {
    button.onclick = () => {
      selectedPersona = button.dataset.persona;
      selectedRun = null; selectedStep = null; detail = null; manualRun = false;
      $('follow-live').checked = false;
      refresh();
    };
  });
}

function renderGeneration() {
  const g = state.generation;
  if (!g) {
    $('generation').innerHTML = '<div><h2>페르소나 생성</h2><p>입력한 설명과 작업을 바탕으로 숙련도와 탐색 습관이 다른 페르소나를 만듭니다.</p></div>';
    return;
  }
  const when = g.generated_at ? new Date(g.generated_at).toLocaleString('ko-KR') : '기존 생성 기록';
  $('generation').innerHTML = `<div><h2>페르소나 생성 완료</h2><p>${esc(when)} · 로컬 템플릿 · seed ${esc(g.seed)}</p><p>${esc(g.task || '')}</p></div><div class="generation-values"><div><strong>${esc(g.generated_count)} / ${esc(g.requested_count)}</strong><span>생성 성공</span></div><div><strong>${esc(g.usage?.tokens || 0)}</strong><span>생성 토큰</span></div></div>`;
}

function renderProfile() {
  const p = detail?.persona || state.personas.find(p => p.persona_id === selectedPersona);
  if (!p) { $('profile').innerHTML = empty('페르소나를 선택하세요.'); return; }
  const tags = [...(p.preferences || []), ...Object.entries(p.constraints || {}).map(([k,v]) => `${k}: ${v}`)];
  $('profile').innerHTML = `<div class="profile-head"><h2>페르소나 정보</h2><span class="profile-id">${esc(p.persona_id)}</span></div><p class="profile-text">${esc(p.background)}</p><div class="tags">${tags.map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div><div class="profile-grid"><div class="profile-cell"><label>디지털 숙련도</label><strong>${esc(p.digital_familiarity)}</strong></div><div class="profile-cell"><label>목표</label><strong>${esc(p.intent)}</strong></div></div>`;
}

function renderCalls() {
  const calls = detail?.calls || [];
  $('call-count').textContent = `${calls.length} calls`;
  $('call-list').innerHTML = calls.length ? [...calls].reverse().map(c => `<div class="call"><span class="provider-chip ${esc(c.provider)}">${esc(c.provider)}</span><span><span class="call-model">${esc(c.model)}</span><br><span class="call-meta">in ${esc(c.input_tokens ?? '—')} · out ${esc(c.output_tokens ?? '—')} · ${esc(c.elapsed_ms || 0)}ms</span>${c.fallback_reason ? `<div class="call-reason">fallback · ${esc(c.fallback_reason)}</div>` : ''}${c.error ? `<div class="call-reason">오류 · ${esc(c.error)}</div>` : ''}</span><span class="call-meta">${c.estimated_cost_usd == null ? '비용 미확인' : '$' + Number(c.estimated_cost_usd).toFixed(5)}</span></div>`).join('') : empty('이 실행에는 아직 모델 호출 기록이 없습니다.');
}

function renderShot() {
  const run = state.runs.find(r => r.run_id === selectedRun);
  const row = selectedStep == null ? null : detail?.steps[selectedStep];
  const id = row ? row.next_observation_id || row.observation_id : run?.latest_observation_id;
  const obs = id ? detail?.observations[id] : null;
  const wrap = $('shot-wrap');
  const src = obs?.screenshot_url;
  const shotKey = src || `empty:${statusLabel(run)}`;
  if (wrap.dataset.shot !== shotKey) {
    wrap.dataset.shot = shotKey;
    wrap.innerHTML = src ? `<img alt="브라우저 관찰 스크린샷" src="${esc(src)}">` : `<div class="shot-placeholder"><b>▧</b>${esc(run && !run.active ? statusLabel(run) + ' · 기록된 스크린샷이 없습니다.' : '브라우저의 첫 관찰을 기다리고 있습니다.')}</div>`;
    if (src) wrap.querySelector('img').onerror = () => { wrap.innerHTML = empty('스크린샷을 읽지 못했습니다. 다음 갱신을 기다려 주세요.'); wrap.dataset.shot = ''; };
  }
  const url = obs?.url || run?.latest_url || '';
  $('screen-title').textContent = obs?.title || run?.latest_title || (selectedRun ? '실행 화면 대기' : '페르소나 생성 후 테스트를 시작하세요');
  $('screen-url').textContent = url;
  $('screen-url').href = /^https?:\/\//.test(url) ? url : '#';
  $('shot-step').textContent = selectedStep == null ? '최근 화면' : `STEP ${selectedStep + 1}`;
  $('shot-caption').textContent = obs ? `viewport · ${obs.observation_id}` : '캡처 준비 중';
}

function renderSteps() {
  const run = state.runs.find(r => r.run_id === selectedRun), rows = detail?.steps || [];
  $('run-status').textContent = run ? `${rows.length} steps · ${statusLabel(run)}` : '실행 대기';
  $('steps').innerHTML = rows.length ? rows.map((s,i) => {
    const a = s.action || {}, result = s.result || {}, error = result.error || s.error;
    const title = a.type ? `${a.type} · ${a.target_id || a.url || a.text || ''}` : s.decision?.finish ? '종료 판단' : '판단 오류';
    const description = error?.message || s.decision?.rationale_summary || s.decision?.finish?.summary || '';
    return `<button class="step ${(selectedStep == null ? rows.length - 1 : selectedStep) === i ? 'selected' : ''}" data-step="${i}"><span class="step-no">${i+1}</span><span class="step-main"><span class="step-title">${esc(title)}</span><div class="step-desc">${esc(description)}</div>${a.type ? `<span class="step-action">${esc(result.ok ? '✓ 실행됨' : error?.code || '결과 대기')}</span>` : ''}</span><span class="step-time">${esc(s.timing_ms?.llm ?? '—')}ms</span></button>`;
  }).join('') : empty(run?.summary?.last_error?.message || (run && !run.active ? statusLabel(run) + ' · 기록된 액션이 없습니다.' : '첫 액션 기록을 기다리고 있습니다.'));
  $('steps').querySelectorAll('[data-step]').forEach(button => {
    button.onclick = () => { selectedStep = Number(button.dataset.step); $('follow-live').checked = false; renderSteps(); renderShot(); };
  });
  $('run-select').innerHTML = '<option value="">실행 기록 선택</option>' + state.runs.map(r => `<option value="${esc(r.run_id)}">${esc(r.persona_id)} · ${esc(statusLabel(r))} · ${esc(r.run_id)}</option>`).join('');
  $('run-select').value = selectedRun || '';
}

function renderJob() {
  const job = state?.job, active = job?.status === 'running';
  $('generate').disabled = posting || active;
  $('run-batch').disabled = posting || active || !state?.personas.length;
  $('demo').disabled = posting || active;
  $('generate').textContent = active && job.kind === 'generate' ? '생성 중…' : '＋　페르소나 생성';
  $('run-batch').textContent = active && job.kind === 'batch' ? '테스트 실행 중…' : '순차 테스트 시작';
  const progress = job?.kind === 'batch' ? ` · ${job.finished_personas || 0}/${job.persona_count}명 실행 종료` : '';
  $('job-line').textContent = job ? `${job.label} · ${job.message}${progress}` : 'URL과 작업·설명을 입력하고 페르소나를 생성하세요.';
  $('job-line').classList.toggle('failed', job?.status === 'failed');
  if (pendingJob && job?.job_id === pendingJob && job.status !== 'running') {
    notify(job.message, job.status === 'failed');
    pendingJob = null;
  }
}

function render() {
  renderStats(); renderPersonas(); renderGeneration(); renderProfile(); renderCalls(); renderSteps(); renderShot(); renderJob();
  $('connection').textContent = '실시간 갱신';
  $('updated').textContent = '업데이트 ' + new Date().toLocaleTimeString('ko-KR');
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    state = await api('/api/state');
    initializeSetup();
    chooseRun();
    const runId = selectedRun;
    detail = null;
    if (runId) {
      const loaded = await api('/api/run/' + encodeURIComponent(runId));
      if (runId === selectedRun) detail = loaded;
    }
    render();
  } catch (error) {
    $('connection').textContent = '연결 오류';
    notify(error.name === 'AbortError' ? '서버 응답이 지연됩니다. 다시 연결하고 있습니다.' : error.message, true);
    if (state) renderJob();
  } finally { refreshing = false; }
}

async function start(kind) {
  if (posting) return;
  const fields = ['target-url','task-input'];
  if (kind === 'generate') fields.push('persona-count-input','persona-background');
  for (const id of fields) {
    if (!$(id).reportValidity()) { notify('필수 입력 내용을 확인하세요.', true); return; }
  }
  posting = true;
  renderJob();
  notify(kind === 'generate' ? '페르소나 생성을 요청하고 있습니다…' : '브라우저 테스트를 시작하고 있습니다…');
  try {
    const job = await api('/api/jobs', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
      kind, provider:$('provider').value, start_url:$('target-url').value.trim(), task:$('task-input').value.trim(),
      persona_count:Number($('persona-count-input').value), persona_background:$('persona-background').value.trim()
    })});
    pendingJob = job.job_id;
    state.job = job;
    notify(job.message);
    if (kind === 'batch') { $('follow-live').checked = true; manualRun = false; selectedRun = null; selectedStep = null; }
    try {
      localStorage.setItem('uxagent-dashboard-setup',JSON.stringify(Object.fromEntries(['target-url','task-input','persona-count-input','persona-background','provider'].map(id => [id,$(id).value]))));
    } catch { /* Saving preferences is optional. */ }
  } catch (error) {
    notify(error.name === 'AbortError' ? '시작 요청 시간이 초과됐습니다. 실행 상태를 확인한 뒤 다시 시도하세요.' : error.message, true);
  } finally { posting = false; renderJob(); await refresh(); }
}

$('generate').onclick = () => start('generate');
$('run-batch').onclick = () => start('batch');
$('refresh').onclick = refresh;
$('target-url').addEventListener('change', updateProvider);
$('provider').addEventListener('change', updateProvider);
$('follow-live').onchange = () => { manualRun = false; selectedStep = null; refresh(); };
$('latest-shot').onclick = () => { selectedStep = null; renderSteps(); renderShot(); };
$('run-select').onchange = () => {
  selectedRun = $('run-select').value || null; selectedPersona = null; selectedStep = null; manualRun = true; detail = null;
  $('follow-live').checked = false; refresh();
};
$('demo').onclick = () => {
  $('target-url').value = state.study.start_url;
  $('task-input').value = state.study.task;
  $('persona-background').value = state.persona_defaults.background;
  $('persona-count-input').value = 2;
  $('provider').value = 'mock'; updateProvider();
  notify('기본 데모 설정을 적용했습니다. 페르소나 생성 후 테스트를 시작하세요.');
};
window.addEventListener('error', event => notify(`화면 오류: ${event.message}`,true));
async function poll() { await refresh(); setTimeout(poll, 1000); }
poll();
