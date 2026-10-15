const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const empty = text => `<div class="empty">${esc(text)}</div>`;
const providerName = p => ({scenario:'API 없는 점검',mock:'무료 데모',live:'OpenAI',gemini:'Gemini',claude:'Claude',jev:'Jev + Gemini'}[p] || p);
const valueText = value => value == null ? '미확인' : typeof value === 'object' ? JSON.stringify(value) : String(value);
const verdict = value => ({success:'성공 확인',failure:'실패 확인',running:'진행 중',pass:'통과',fail:'실패',unknown:'미확인',unsupported:'미지원'}[value] || '미확인');
const reasons = {verified_success:'과업 성공',agent_finished:'AI 종료 선언',agent_gave_up:'AI 중단',browser_error:'브라우저 오류',model_error:'모델 오류',max_steps:'단계 한도',run_timeout:'시간 초과',budget_exceeded:'호출 한도',stuck:'반복 감지',interrupted:'중단',cancelled:'취소',scenario_completed:'점검 완료',scenario_failed:'확인 조건 실패',scenario_unverified:'근거 부족',scenario_action_error:'조작 실패'};
let state = null, detail = null, experiments = [], selectedRun = null, selectedStep = null, selectedObservation = null, initialized = false, refreshing = false, posting = false, currentView = 'test', pendingJobId = null, wizardStep = 1, flowBusy = false, flowCancelled = false, guideBusy=false, connecting=false, guideOptions=null, guideHistory=[], guideCards=[], guideTask=null, guideLast=null, modelChoices={};
let detailRead = {status:'idle', updatedAt:null}, comparisonRead = {status:'idle', updatedAt:null};
function renderReadStatus() {
  const read = currentView==='compare' ? comparisonRead : detailRead;
  const relevant = ['board','history','compare'].includes(currentView);
  const box = $('data-status');
  box.hidden = !relevant || !['failed','loading'].includes(read.status);
  const label = currentView==='compare' ? '비교 자료' : '실행 상세';
  $('data-status-text').textContent = read.status==='failed' ? `${label}를 불러오지 못했습니다. ${read.updatedAt ? `마지막 정상 조회 ${read.updatedAt} 자료입니다. 최신 자료 확인 전에는 저장·내보내기를 사용할 수 없습니다.` : '자료를 다시 불러온 뒤 확인하세요.'}` : `${label}를 불러오고 있습니다.`;
  $('retry-data').hidden = read.status!=='failed';
}
function recoveryRate(recovery) {
  if (Number.isFinite(recovery?.rate)) return `${(recovery.rate*100).toFixed(1)}%`;
  return Array.isArray(recovery?.episodes) && recovery.episodes.length===0 ? '대상 사건 없음' : '미확인';
}
function notify(text, error = false) { $('notice').hidden=!text; $('notice').textContent = text || ''; $('notice').classList.toggle('error',error); }
async function api(path,options={}) { const controller = new AbortController(); const timer=setTimeout(()=>controller.abort(),['/api/connection','/api/setup-guide'].includes(path)?90000:15000); try { const response=await fetch(path,{...options,cache:'no-store',signal:controller.signal}); const body=await response.json(); if(!response.ok) { const error=new Error(body.error || `요청 실패 (${response.status})`); error.status=response.status; throw error; } return body; } finally { clearTimeout(timer); } }
function post(path,body) { return api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); }
function isDemoUrl(text) { try {const u=new URL(text);return ['localhost','127.0.0.1'].includes(u.hostname)&&u.pathname.endsWith('shop.html');}catch{return false;} }
function navigate(view) { currentView=view; document.querySelectorAll('[data-view]').forEach(b=>{const active=b.dataset.view===view;b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1;}); ['test','compare','board','history'].forEach(v=>$('view-'+v).hidden=v!==view); const copy={test:['과업 테스트','사이트와 목표를 입력하고 테스트를 시작하세요.'],compare:['AI 비교','일반 AI와 페르소나 AI의 결과를 비교하세요.'],board:['개선 보드','문제를 확인하고 수정할 작업을 정리하세요.'],history:['실행 기록','화면과 행동을 단계별로 확인하세요.']}[view];$('page-title').textContent=copy[0];$('page-description').textContent=copy[1];$('stats').hidden=true; renderReadStatus(); }
function plan() { const provider=$('provider').value, demo=isDemoUrl($('target-url').value);  const checks=$('evaluation-checks').value.trim(); $('plan-preview').innerHTML=`<ol><li><strong>대상</strong><br>${esc($('target-url').value || (provider==='scenario'?'합성 상품 재현 페이지 (실행 시 자동 생성)':'테스트 URL을 입력하세요.'))}</li><li><strong>목표</strong><br>${esc($('task-input').value || '사용자가 이루려는 목표를 입력하세요.')}</li><li><strong>실행</strong><br>${provider==='scenario'?'사전 정의한 단계 실행 (모델·페르소나 미사용)':`${esc($('model-select').selectedOptions[0]?.textContent||providerName(provider))}로 ${esc($('persona-count-input').value)}명 테스트`}</li><li><strong>성공 기준</strong><br>${provider==='scenario'?'등록된 과업별 코드 평가로 확인합니다.':demo?'데모 상품 조건을 독립 평가기가 확인합니다.':checks?'등록한 기능 점검으로 확인합니다. 조건 자체가 적절한지 검토하세요.':'등록된 독립 평가 조건이 없어 결과는 미확인입니다.'}</li></ol><p class="help">${provider==='scenario'?'모델 API 호출 없이 브라우저에서 점검합니다.':'사용자 생성과 테스트는 자동으로 이어집니다.'}</p>`;const total=Number($('persona-count-input').value)*Number($('repetitions').value);$('compare-plan').textContent=`각 AI ${total}회, 총 ${total*2}회 테스트합니다. ${$('model-select').selectedOptions[0]?.textContent||providerName(provider)}를 사용합니다.`; }
function initialize() {if(initialized)return;const g=state.generation||{};$('target-url').value=g.start_url||state.study?.start_url||'';$('task-input').value=g.task||state.study?.task||'';$('persona-background').value=g.background||state.persona_defaults?.background||'';$('persona-count-input').value=g.requested_count||2;initialized=true;navigate(currentView);notify('');plan();setWizardStep(wizardStep);}
function renderStats() { const runs=state.runs||[], done=runs.filter(r=>!r.active);$('stats').innerHTML=[['페르소나',`${state.personas?.length||0}명`],['실행 기록',`${runs.length}건`],['과업 성공',`${done.filter(r=>r.verification==='success').length}건`],['확인 필요',`${done.filter(r=>!['success','failure'].includes(r.verification)).length}건`]].map(([label,value])=>`<div class="stat"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join(''); }
function renderJob() { const active=['running','stopping'].includes(state?.job?.status); if(pendingJobId&&state?.job?.job_id===pendingJobId&&!active){notify(state.job.status==='failed'?state.job.message:'',state.job.status==='failed');pendingJobId=null;}['run-batch','run-compare','wizard-next','wizard-back'].forEach(id=>$(id).disabled=posting||active||flowBusy||connecting||guideBusy||state?.guide_busy);$('stop-job').disabled=posting||state?.job?.status!=='running';const job=state?.job;$('job-status-card').dataset.status=job?.status||'';const jobName={generate:'페르소나 생성',batch:'과업 테스트',compare:'AI 비교',scenario:'과업 점검'}[job?.kind]||'작업';const jobStatus={running:'진행 중',stopping:'중지 중',completed:'완료',failed:'실패',cancelled:'중지됨'}[job?.status]||'';$('job-line').textContent=job?`${jobName} ${jobStatus}`:'테스트 준비';$('job-status-card').hidden=!job||(currentView==='test'&&!active&&!flowBusy);$('stop-job').hidden=!active;$('job-line').classList.toggle('error',state?.job?.status==='failed');$('provider-status').textContent=state?.providers?.[$('connection-provider').value]?'연결됨':'API 키를 입력하세요.';syncModel();guideAvailability();const g=state?.generation;$('generation').innerHTML=g?`<h3>페르소나 생성 기록</h3><p class="help">${esc(g.generated_count)} / ${esc(g.requested_count)}명 · 로컬 템플릿</p><p class="help">${esc(g.task)}</p>`:'<h3>페르소나 생성</h3><p class="help">사용자 배경과 과업으로 테스트할 사용자를 만듭니다.</p>'; }
function runButtons(runs) {return runs.length?runs.map(r=>`<button class="run-row ${r.run_id===selectedRun?'selected':''}" data-run="${esc(r.run_id)}" title="${esc(r.run_id)}"><div class="run-row-top"><strong>${esc(r.provider==='scenario'?'시나리오 점검':r.persona_id||'일반 AI')}</strong><span class="badge">${esc(verdict(r.verification))}</span></div><span class="muted run-label-detail">${esc(providerName(r.provider||''))} ${esc(r.started_at?new Date(r.started_at).toLocaleString('ko-KR',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}):'')}</span><span class="muted run-row-meta"><span>${esc(r.active?'테스트 중':reasons[r.termination_reason]||r.termination_reason||'종료')}</span><span>행동 ${esc(r.action_attempts??r.steps??'미확인')}회</span></span></button>`).join(''):empty('아직 테스트 기록이 없습니다.');}
function renderRuns() {const runs=state.runs||[];$('test-runs').innerHTML=runButtons(runs.slice(0,3));$('recent-panel').hidden=!runs.length;const q=$('record-search').value.trim().toLowerCase(),filter=$('record-filter').value;const found=runs.filter(r=>`${r.run_id} ${r.persona_id||'일반 AI'} ${r.provider||''} ${r.model||''} ${r.latest_url||''}`.toLowerCase().includes(q)&&(filter==='all'||(filter==='running'?r.active:!r.active&&(filter==='unknown'?!['success','failure'].includes(r.verification):r.verification===filter))));$('history-runs').innerHTML=found.length?runButtons(found):empty('조건에 맞는 기록이 없습니다.');$('record-count').textContent=`${found.length} / ${runs.length}건`;$('run-select').innerHTML='<option value="">실행 기록 선택</option>'+runs.map(r=>`<option value="${esc(r.run_id)}">${esc(r.provider==='scenario'?'시나리오 점검':r.persona_id||'일반 AI')} / ${esc(verdict(r.verification))} / ${esc(r.run_id)}</option>`).join('');$('run-select').value=selectedRun||''; }
function metric(label,value){return `<div><span>${esc(label)}</span><strong>${esc(valueText(value))}</strong></div>`;}
function renderFeatureChecks(features) {
  const list=$('feature-checks'),runId=selectedRun||'';
  const opened=list.dataset.runId===runId?new Set([...list.querySelectorAll('details[open]')].map(row=>row.dataset.checkId)):new Set();
  list.dataset.runId=runId;
  list.innerHTML=features.length?features.map((f,i)=>{
    const status=['pass','fail','unknown','unsupported'].includes(f.status)?f.status:'unknown',id=String(f.id??i);
    const icon={pass:'✓',fail:'×',unknown:'?',unsupported:'–'}[status],label=f.label||f.id||'점검 항목';
    return `<details class="feature" data-status="${status}" data-check-id="${esc(id)}" ${opened.has(id)?'open':''}><summary aria-label="${esc(label)} ${esc(verdict(status))}, 근거 보기"><span class="feature-icon" aria-hidden="true">${icon}</span><strong>${esc(label)}</strong><span class="feature-state">${esc(verdict(status))}</span><span class="feature-chevron" aria-hidden="true">⌄</span></summary><p class="feature-evidence">${esc(valueText(f.evidence))}</p></details>`;
  }).join(''):empty('기능별 점검 근거가 없습니다. 외부 사이트는 성공 조건을 먼저 등록하세요.');
}
function wonderMarkup() {const thoughts=detail?.wonder?.thoughts||[],draws=detail?.wonder?.draws||[];if(!thoughts.length&&!draws.length)return '';return `<details class="raw-evidence"><summary>AI가 생성한 가정된 생각 ${thoughts.length}건</summary><p class="help">실제 사용자 기억이나 검증된 선호가 아닙니다. 1%는 시작된 Slow 작업당 실험 추첨률이며 인간 행동 확률이 아닙니다. 추첨 ${draws.length}회.</p>${thoughts.map(row=>`<p>${esc(row.text)} · 기억 저장: ${row.stored?'예':'아니요'}</p>`).join('')}</details>`;}
function renderDetail() {const run=state.runs.find(r=>r.run_id===selectedRun);const summary=detail?.summary||{}, m=detail?.metrics||{},rows=detail?.steps||[];$('screen-title').textContent=run?`${run.provider==='scenario'?'시나리오':run.persona_id||'일반 AI'} 실행 기록`:'실행을 선택하세요';$('run-status').textContent=run?`독립 판정: ${verdict(run.verification)} · 종료 상태: ${run.active?'진행 중':reasons[run.termination_reason]||run.termination_reason||'종료'}`:'독립 판정과 종료 상태를 함께 확인합니다.';const cost=m.estimated_cost_usd??m.cost_usd??summary.cost;$('run-metrics').innerHTML=`<div class="metric-grid">${metric('행동 시도',m.action_attempts??summary.action_attempts??run?.action_attempts)}${metric('실행 시간',summary.elapsed_ms==null?'미확인':`${(summary.elapsed_ms/1000).toFixed(1)}초`)}${metric('추정 API 비용',cost==null?'미확인':`$${Number(cost).toFixed(5)}`)}${metric('기록 확보율',m.recording?.rate==null?'미확인':`${(m.recording.rate*100).toFixed(1)}%`)}${metric('복구 사건',m.recovery?.episodes?.length??'미확인')}${metric('오류 후 재개율',recoveryRate(m.recovery))}</div>`;$('steps').innerHTML=rows.length?rows.map((s,i)=>{const a=s.action||{},result=s.result||{};return `<button class="step ${selectedStep===i?'selected':''}" data-step="${i}"><strong>${i+1}. ${esc(a.type||'모델 판단')} ${esc(a.target_id||a.url||'')}</strong><small>${esc(s.scenario_step||s.decision?.rationale_summary||s.decision?.finish?.summary||result.error?.message||'판단 설명 없음')}</small><small>${esc(a.type?(result.ok?'행동 실행됨':result.error?.code||'결과 미확인'):'실행 행동 없음')}</small></button>`;}).join(''):empty('기록된 행동이 없습니다.');const row=selectedStep==null?null:rows[selectedStep],obsId=selectedObservation||(row?(row.next_observation_id||row.observation_id):run?.latest_observation_id),obs=detail?.observations?.[obsId],src=obs?.screenshot_url;const wrap=$('shot-wrap');if(wrap.dataset.shot!==(src||'')){wrap.dataset.shot=src||'';wrap.innerHTML=src?`<img src="${esc(src)}" alt="테스트 화면">`:empty('이 실행에는 저장된 관찰 화면이 없습니다.');if(src)wrap.querySelector('img').onerror=()=>{wrap.innerHTML=empty('관찰 화면 파일을 읽지 못했습니다.');wrap.dataset.shot='';};}else if(!src){wrap.innerHTML=empty('이 실행에는 저장된 관찰 화면이 없습니다.');}const url=obs?.url||run?.latest_url||'';$('screen-url').textContent=url;$('screen-url').href=/^https?:\/\//.test(url)?url:'#';$('shot-caption').textContent=obs?`${selectedObservation?'선택 관찰':selectedStep==null?'최근 관찰':`행동 ${selectedStep+1} 이후`} · ${obsId}`:'저장된 관찰 없음';const features=summary.evaluator?.feature_checks||[];renderFeatureChecks(features);const p=detail?.persona;$('profile').innerHTML=p?`<h2>${detail?.run?.execution_mode==='scripted'?'검증 방식':'페르소나 맥락'}</h2><p class="help">${esc(p.background||(summary.execution_mode==='scripted'?'사전 정의한 동작과 코드 평가':'일반 AI 조건'))}</p><p class="help">숙련도: ${esc(p.digital_familiarity??'해당 없음')}<br>목표: ${esc(p.intent||'기록 없음')}</p>`:'<h2>페르소나 맥락</h2>'+empty('실행을 선택하세요.');$('profile').innerHTML+=wonderMarkup();const calls=detail?.calls||[];$('call-count').textContent=`${calls.length}회`;$('call-list').innerHTML=calls.length?`<div class="table-wrap"><table><thead><tr><th>제공자 / 모델</th><th>토큰 입력 / 출력</th><th>시간</th><th>추정 비용</th></tr></thead><tbody>${calls.map(c=>`<tr><td>${esc(c.provider)} / ${esc(c.model)}${c.error?`<p class="error">${esc(c.error)}</p>`:''}${c.fallback_reason?`<p class="muted">fallback: ${esc(c.fallback_reason)}</p>`:''}</td><td>${esc(c.input_tokens??'미확인')} / ${esc(c.output_tokens??'미확인')}</td><td>${esc(c.elapsed_ms??'미확인')} ms</td><td>${c.estimated_cost_usd==null?'미확인':'$'+Number(c.estimated_cost_usd).toFixed(5)}</td></tr>`).join('')}</tbody></table></div>`:empty('모델 호출 기록이 없습니다.');$('exports').innerHTML=selectedRun&&detail&&detailRead.status==='ready'?['json','csv','md','html'].map(f=>`<a class="btn" href="/api/export/${encodeURIComponent(selectedRun)}?format=${f}" download>${f.toUpperCase()} 다운로드</a>`).join(''):empty(selectedRun?'최신 실행 상세를 불러온 뒤 내보낼 수 있습니다.':'실행을 선택하면 내보낼 수 있습니다.');renderCards();renderBrain(); }
function evidenceButtons(card){return (card.evidence_step_ids||[]).map(id=>{const i=(detail?.steps||[]).findIndex(s=>s.step_id===id);return i<0?esc(id):`<button class="btn soft" data-evidence-step="${i}">행동 ${i+1} 근거 보기</button>`;}).join(' ');}
function cardReviewLabel(c){const v=c.latest_review?.verdict;return ({valid:'유효 후보',invalid:'무효 후보',deferred:'판단 보류',tool_error:'도구 오류',environment_error:'환경 오류'}[v]||(c.review_status==='deferred'?'판단 보류':c.review_status==='reviewed'?'검토 완료':'사람 검토 전'));}
// Drafts live only in this page and are scoped to the exact evidence version.
const reviewForms = new Map();
let detailRevision = 0, refreshQueued = false;
const reviewVerdicts = {valid:'유효 후보', invalid:'무효 후보', deferred:'판단 보류', tool_error:'도구 오류', environment_error:'환경 오류'};
function reviewKey(runId, card) { return JSON.stringify([runId, card.card_id, card.card_version]); }
function reviewForm(runId, card) {
  const key = reviewKey(runId, card);
  if (reviewForms.has(key)) return reviewForms.get(key);
  const form = document.createElement('form');
  form.className = 'review-form';
  form.setAttribute('aria-label', '사람 판정 입력');
  form.innerHTML = `<h4>사람 검토</h4>
    <p class="help">후보에 대한 검토입니다. 과업 성공 판정은 바뀌지 않습니다.</p>
    <div class="form-grid"><label>검토자 별칭<input name="reviewer_id" required maxlength="200" autocomplete="off" placeholder="검토자 이름 또는 별칭"></label>
    <label>판정<select name="verdict" aria-label="판정" required><option value="">선택하세요</option>${Object.entries(reviewVerdicts).map(([value,label])=>`<option value="${value}">${label}</option>`).join('')}</select></label>
    <label class="full">검토 메모<textarea name="note" maxlength="4000" placeholder="판단 근거를 적으세요. 키·개인정보는 입력하지 마세요."></textarea></label></div>
    <div class="actions gap-top"><button class="btn primary" type="submit">판정 저장</button><button class="btn soft" type="button" data-review-reload hidden>근거 다시 확인</button></div>
    <p class="help review-message" role="status" aria-live="polite"></p>`;
  const entry = {form, pending:false, blocked:false, runId, card};
  reviewForms.set(key, entry);
  const message = (text, error=false) => {
    const node = form.querySelector('.review-message');
    node.textContent = text;
    node.classList.toggle('error', error);
  };
  entry.message = message;
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (entry.pending || entry.blocked || detailRead.status!=='ready') return;
    const current = selectedRun === runId && detail?.cards?.find(c=>c.card_id===card.card_id && c.card_version===card.card_version);
    if (!current || !detail?.summary) {
      entry.blocked = true;
      message('실행 상태나 근거가 변경됐습니다. 근거를 다시 확인하세요.', true);
      updateReviewForm(entry);
      return;
    }
    const reviewer = form.elements.reviewer_id.value.trim();
    if (!reviewer) { message('검토자 별칭을 입력하세요.', true); form.elements.reviewer_id.focus(); return; }
    const payload = {card_id:card.card_id, card_version:card.card_version, reviewer_id:reviewer,
      verdict:form.elements.verdict.value, note:form.elements.note.value};
    if (!Object.hasOwn(reviewVerdicts, payload.verdict) || !form.reportValidity()) return;
    entry.pending = true;
    message('판정을 저장하고 있습니다.');
    updateReviewForm(entry);
    try {
      const record = await post('/api/reviews/'+encodeURIComponent(runId), payload);
      message('판정을 저장했습니다.');
      // Use the server-confirmed record, never an optimistic success verdict.
      if (selectedRun===runId) {
        detailRevision++; // Discard reads issued before this confirmed save.
        const target = detail?.cards?.find(c=>c.card_id===card.card_id && c.card_version===card.card_version);
        if (target) {
          detail.reviews = [...(detail.reviews||[]).filter(r=>r.review_id!==record.review_id), record];
          target.review_history = [...(target.review_history||[]).filter(r=>r.review_id!==record.review_id), record];
          target.latest_review = record;
          target.review_status = record.verdict==='deferred'?'deferred':'reviewed';
          renderCards();
        }
      }
    } catch (error) {
      entry.blocked = error.status===409 || error.status===404;
      const messages = {
        400:'입력 내용을 확인하세요. 별칭·판정·메모 형식 또는 민감정보 때문에 저장하지 못했습니다.',
        404:'실행 또는 후보를 찾지 못했습니다. 근거를 다시 확인하세요.',
        409:'실행 중이거나 카드 근거가 변경됐습니다. 근거를 다시 확인한 뒤 판정하세요.',
        500:'검토 이력을 읽거나 저장하지 못했습니다. 서버 상태를 확인하세요.'
      };
      message(messages[error.status] || '저장 여부를 확인하지 못했습니다. 중복 저장 전에 최신 판정과 서버 상태를 확인하세요.', true);
    } finally {
      entry.pending = false;
      updateReviewForm(entry);
    }
  });
  form.querySelector('[data-review-reload]').addEventListener('click', async () => {
    if (entry.pending || selectedRun!==runId) return;
    entry.pending = true;
    const revision = ++detailRevision;
    updateReviewForm(entry);
    try {
      const fresh = await api('/api/run/'+encodeURIComponent(runId));
      if (selectedRun!==runId || revision!==detailRevision) return;
      detailRevision++;
      detail = fresh;
      detailRead = {status:'ready', updatedAt:new Date().toLocaleTimeString('ko-KR')};
      renderReadStatus();
      entry.blocked = false;
      message('최신 근거를 확인하고 다시 판정하세요.');
      selectedStep = null;
      $('follow-live').checked = false;
      navigate('history');
      renderDetail();
    } catch (_) { message('근거를 불러오지 못했습니다. 입력을 유지합니다. 다시 시도하세요.', true); }
    finally { entry.pending = false; updateReviewForm(entry); }
  });
  return entry;
}
function updateReviewForm(entry) {
  const active = selectedRun===entry.runId && !detail?.summary;
  entry.form.querySelectorAll('input,select,textarea').forEach(node=>node.disabled=entry.pending);
  const submit = entry.form.querySelector('[type=submit]');
  submit.disabled = entry.pending || entry.blocked || active || detailRead.status!=='ready';
  submit.textContent = entry.pending?'저장 중…':'판정 저장';
  const reload = entry.form.querySelector('[data-review-reload]');
  reload.hidden = !entry.blocked;
  reload.disabled = entry.pending;
  if (active && !entry.pending) entry.message('실행이 끝난 뒤 검토를 저장할 수 있습니다.');
}
function mountReviewForms(cards, html) {
  const container = $('cards');
  const signature = JSON.stringify([selectedRun, cards.map(c=>[c.card_id,c.card_version]), html]);
  // Unchanged polling must not replace the user's in-progress form.
  const focused = document.activeElement;
  const selection = ['TEXTAREA','INPUT'].includes(focused?.tagName) && typeof focused.selectionStart==='number' ? [focused.selectionStart, focused.selectionEnd] : null;
  if (container.reviewSignature!==signature) {
    const expanded = new Set([...container.querySelectorAll('[data-history-key][open]')].map(node=>node.dataset.historyKey));
    container.innerHTML = html;
    container.querySelectorAll('[data-history-key]').forEach(node=>node.open=expanded.has(node.dataset.historyKey));
    container.reviewSignature = signature;
  }
  cards.forEach((card,index)=>{
    if (!selectedRun || !card.card_id || !card.card_version) return;
    const entry = reviewForm(selectedRun,card);
    const article = container.children[index];
    if (entry.form.parentNode!==article) article.append(entry.form);
    updateReviewForm(entry);
  });
  if (focused?.isConnected && focused.closest('.review-form') && document.activeElement!==focused) {
    focused.focus({preventScroll:true});
    if (selection) focused.setSelectionRange(...selection);
  }
}

function renderProvenance() {
  const run = detail?.run;
  const execution = run?.provider==='mock' ? 'Mock 데모' : ({ai:'AI 실행',scripted:'사전 정의 스크립트'}[run?.execution_mode]||'미확인');
  const source = {synthetic_fixture:'합성 테스트 환경',live_configured:'실제 사이트 (설정된 범위)'}[run?.source_kind]||'미확인';
  const html = run ? `<p>실행 방식: <strong>${execution}</strong> · 대상 출처: <strong>${source}</strong></p><p class="help">실제 사람의 행동·판단 데이터가 아닙니다. 사람 검토는 아래 별도 이력으로 확인하세요.${run.provider==='mock'?' Mock은 모델 API를 사용하지 않는 동작 확인용 데모입니다.':''}</p>` : '';
  ['run-provenance','board-provenance'].forEach(id=>{$(id).innerHTML=html;});
}
function reviewHistory(card) {
  const current = card.review_history||[];
  const previous = (detail?.reviews||[]).filter(r=>r.card_id===card.card_id && r.card_version!==card.card_version);
  const records = rows => rows.length ? [...rows].reverse().map(r=>{
    const date = r.created_at ? new Date(r.created_at) : null;
    const time = date && Number.isFinite(date.getTime()) ? `<time datetime="${esc(r.created_at)}">${esc(date.toLocaleString('ko-KR',{timeZoneName:'short'}))}</time>` : '시각 미기록';
    return `<li class="review-record"><p><strong>${esc(reviewVerdicts[r.verdict]||'판정 미확인')}</strong> · ${esc(r.reviewer_id||'별칭 미기록')}</p><p class="help">${time}</p><p class="review-note">${esc(r.note||'메모 없음')}</p><p class="help review-version">근거 버전: ${esc(r.card_version||'미기록')}</p></li>`;
  }).join('') : '';
  return `<details class="review-history" data-history-key="${esc(reviewKey(selectedRun,card))}"><summary>사람 검토 이력 (${current.length+previous.length}건)</summary><p class="help">저장 순서의 최신 항목부터 표시합니다. 별칭은 인증 신원이나 독립 2인 합의를 뜻하지 않습니다. AI 계획 검토와 독립 과업 판정은 별개입니다.</p><h4>현재 버전 검토 (${current.length}건)</h4>${current.length?`<ol>${records(current)}</ol>`:'<p class="help">현재 버전의 저장된 검토가 없습니다.</p>'}<h4>이전 버전 검토 (${previous.length}건)</h4><p class="help">이전 판정은 현재 근거에 자동 적용하지 않습니다.</p>${previous.length?`<ol>${records(previous)}</ol>`:'<p class="help">이전 버전의 저장된 검토가 없습니다.</p>'}</details>`;
}
function renderCards(){renderProvenance();const cards=detail?.cards||[];$('board-run-label').textContent=selectedRun?`선택 실행: ${selectedRun}`:'실행 기록에서 확인할 테스트를 선택하세요.';const category=c=>({system_error_candidate:'도구 오류 확인',unmet_checkpoint:'완료 조건 미충족'}[c.classification]||'사용성 후보');const html=cards.length?cards.map(c=>`<article class="card issue"><div class="section-head"><div><p class="issue-category">${esc(category(c))}</p><h3>${esc(c.title||c.issue_id)}</h3></div><span class="badge">${esc(cardReviewLabel(c))}</span></div><dl class="issue-facts">${[['관찰',c.observed_behavior],['가능한 원인',c.hypothesis],['수정 제안',c.recommendation],['완료 조건',c.acceptance]].map(([k,v])=>`<dt>${k}</dt><dd>${esc(valueText(v))}</dd>`).join('')}</dl><div class="actions gap-top">${evidenceButtons(c)||'<span class="muted">연결할 행동 기록 없음</span>'}</div>${c.latest_review?`<p class="help">검토: ${esc(c.latest_review.reviewer_id)} · ${esc(c.latest_review.note||'메모 없음')}</p>`:''}${reviewHistory(c)}<details class="raw-evidence"><summary>원자료</summary><pre>${esc(valueText(c.evidence))}</pre></details></article>`).join(''):empty(!selectedRun?'실행을 선택하세요.':!detail?'실행 상세를 불러온 뒤 후보를 확인할 수 있습니다.':'이 실행에서 발견한 개선 후보가 없습니다.');mountReviewForms(cards,html);}
function pairedSessions(sessions) { const pairs=new Map();for(const s of sessions){const key=`${s.pair_persona_id||s.persona_id||'세션'}:${s.repetition||1}`;if(!pairs.has(key))pairs.set(key,{});pairs.get(key)[s.condition]=s;} const cell=s=>s?`<button class="btn soft" ${s.run_id&&state?.runs?.some(r=>r.run_id===s.run_id)?`data-run="${esc(s.run_id)}"`:'disabled title="연결할 실행 기록이 없습니다"'}><span>${esc(verdict(s.verification))}</span> <small>${esc({running:'진행 중',completed:'종료',error:'오류',cancelled:'취소',not_started:'미실행'}[s.status]||s.status)}</small></button>`:'미등록';return `<div class="table-wrap gap-top"><table><thead><tr><th>대응 세션 / 반복</th><th>일반 AI</th><th>페르소나 AI</th></tr></thead><tbody>${[...pairs].map(([key,p])=>`<tr><td>${esc(key)}</td><td>${cell(p.general)}</td><td>${cell(p.persona)}</td></tr>`).join('')}</tbody></table></div>`;}
const sessionStatusLabels = {running:'진행 중',completed:'종료',error:'오류',cancelled:'취소',not_started:'미실행',unknown:'미확인'};
const measuredNumber = value => typeof value==='number' && Number.isFinite(value) && value>=0;
const countText = value => measuredNumber(value) ? String(value) : '미확인';
const measurementText = (value, money=false) => measuredNumber(value) ? (money?'$'+value.toFixed(5):String(value)) : '미확인';
const percentText = value => measuredNumber(value) ? `${(value*100).toFixed(1)}%` : '미확인';
function coverageText(known, unknown, requested) {
  return `완전 측정 ${countText(known)} / 예정 ${countText(requested)}회 · 누락 포함 ${countText(unknown)}회`;
}
function usageMeasurement(group, key, requested, money=false) {
  return `<div data-measure="${key}"><strong>전체: ${measurementText(group[key],money)}</strong><p>${measuredNumber(group[key])?'측정 합계':'측정 부분값'}: ${measurementText(group[key+'_known_total'],money)}</p><p class="help">${coverageText(group[key+'_known_sessions'],group[key+'_unknown_sessions'],requested)}</p></div>`;
}
function recordingMeasurement(recording={}, requested) {
  return `<div data-measure="recording"><strong>전체: ${recording.attempted===0?'대상 행동 없음':percentText(recording.rate)}</strong><p>전체 근거: ${countText(recording.complete)} / ${countText(recording.attempted)}행동</p><p>측정 범위: ${countText(recording.complete_known_total)} / ${countText(recording.attempted_known_total)}행동 · ${recording.attempted_known_total===0?'대상 행동 없음':percentText(recording.known_rate)}</p><p class="help">${coverageText(recording.known_sessions,recording.unknown_sessions,requested)}</p></div>`;
}
function comparisonMetadata(e) {
  const settings=e.settings||{}, study=settings.study||{};
  const models=[...new Set((e.sessions||[]).map(s=>s.model).filter(Boolean))];
  const fields = [
    ['실험 ID',e.experiment_id],['제공자',settings.provider],
    ['모델 설정',settings.model||study.provider_model||study.model],['실행에 기록된 모델',models.length?models.join(', '):null],
    ['과업',study.task],['대상 URL',study.start_url],['반복 수',settings.repetitions],
    ['화면 크기',study.viewport?`${study.viewport.width??'미기록'} × ${study.viewport.height??'미기록'}`:null],
    ['관찰 정책',study.observation_policy],['환경 식별자',settings.environment_id||study.environment_id],
    ['사이트 버전',settings.site_version||study.site_version],['프롬프트 버전',settings.prompt_version]
  ];
  return `<div class="comparison-metadata">${fields.map(([label,value])=>`<p>${label}: ${esc(value??'미기록')}</p>`).join('')}</div>`;
}
function comparisonBody(e) {
  const groups=e.groups||{}, conditions=['general','persona'], label=k=>k==='general'?'일반 AI':'페르소나 AI';
  const median=(g,key,population,unit='')=>`<strong>${measurementText(g[key])}${measuredNumber(g[key])?unit:''}</strong><p class="help">계산 대상 ${countText(g[population])} / 성공 ${countText(g.success)}회</p>`;
  return `<p class="help">${esc(providerName(e.settings?.provider||'제공자 미기록'))}${e.settings?.provider==='mock'?' — 동작 확인용 데모 (실제 AI 성능 근거 아님)':''}</p>
    <div class="table-wrap gap-top"><table class="comparison-results"><caption>과업 결과와 실행 상태</caption><thead><tr><th>조건</th><th>성공 / 예정</th><th>성공률</th><th>과업 결과</th><th>실행 상태</th><th>행동 중앙값</th><th>시간 중앙값</th></tr></thead><tbody>${conditions.map(k=>{
      const g=groups[k]||{};
      const statuses=Object.entries(g.statuses||{}).map(([status,n])=>`${esc(sessionStatusLabels[status]||status)} ${esc(n)}`).join(' · ')||'기록 없음';
      return `<tr><th scope="row">${label(k)}</th><td>${countText(g.success)} / ${countText(g.requested)}</td><td>${g.requested===0?'예정 세션 없음':percentText(g.rate)}</td><td>성공 ${countText(g.success)} · 실패 ${countText(g.failure)} · 미확인 ${countText(g.unknown)}</td><td>${statuses}</td><td>${median(g,'median_actions','median_actions_sessions','회')}</td><td>${median(g,'median_ms','median_ms_sessions',' ms')}</td></tr>`;
    }).join('')}</tbody></table></div><p class="help">성공률 분모는 예정 세션입니다. 취소·미실행도 제외하지 않습니다. 중앙값은 성공한 실행 중 측정 가능한 값만 사용하며 대응쌍 변화량이 아닙니다.</p>
    <div class="table-wrap gap-top"><table class="comparison-coverage"><caption>측정 범위와 누락</caption><thead><tr><th>조건</th><th>추정 API 비용</th><th>토큰 합계</th><th>기록 확보율</th></tr></thead><tbody>${conditions.map(k=>{
      const g=groups[k]||{};
      return `<tr data-condition="${k}"><th scope="row">${label(k)}</th><td>${usageMeasurement(g,'cost',g.requested,true)}</td><td>${usageMeasurement(g,'llm_tokens',g.requested)}</td><td>${recordingMeasurement(g.recording,g.requested)}</td></tr>`;
    }).join('')}</tbody></table></div><p class="help">미확인은 0이 아닙니다. 측정 부분값은 누락이 있는 세션에서 확인된 일부 호출도 포함하며 전체값으로 해석하지 않습니다. 기록 확보율은 확인된 행동 근거의 비율이며 과업 성공률과 다릅니다.</p>
    <details class="comparison-details" data-comparison-key="${esc(JSON.stringify([e.experiment_id,'details']))}"><summary>실험 조건과 측정 상세</summary>${comparisonMetadata(e)}${conditions.map(k=>{
      const g=groups[k]||{};
      return `<section data-condition="${k}"><h3>${label(k)} 사용량</h3><div class="comparison-measurements">${[['llm_request_count','요청 수'],['input_tokens','입력 토큰'],['output_tokens','출력 토큰']].map(([key,name])=>`<section><h4>${name}</h4>${usageMeasurement(g,key,g.requested)}</section>`).join('')}</div>${Object.entries(g.provider_usage||{}).map(([provider,usage])=>`<h4>${esc(providerName(provider))} 제공자별 사용량</h4><div class="comparison-measurements">${[['requests','요청 수'],['input_tokens','입력 토큰'],['output_tokens','출력 토큰'],['estimated_cost_usd','추정 비용']].map(([key,name])=>`<section><h4>${name}</h4>${usageMeasurement(usage,key,g.requested,key==='estimated_cost_usd')}</section>`).join('')}</div>`).join('')||'<p class="help">제공자별 측정 내역 없음</p>'}</section>`;
    }).join('')}</details>${pairedSessions((e.sessions||[]).filter(s=>s.execution_mode!=='scripted'&&s.provider!=='scenario'))}<p class="help">개별 결과를 누르면 실행 근거를 볼 수 있습니다. 기록이 없는 세션은 선택할 수 없습니다.</p>`;
}
function renderExperiments(){
  const container=$('experiments');
  const signature=JSON.stringify([experiments,comparisonRead.status,(state?.runs||[]).map(r=>r.run_id)]);
  if(container.comparisonSignature===signature)return;
  const expanded=new Set([...container.querySelectorAll('[data-comparison-key][open]')].map(node=>node.dataset.comparisonKey));
  container.innerHTML=experiments.length?experiments.map((e,i)=>i?`<details class="card" data-comparison-key="${esc(JSON.stringify([e.experiment_id,'experiment']))}"><summary>이전 비교 ${esc(e.started_at?new Date(e.started_at).toLocaleString('ko-KR'):e.experiment_id)}</summary>${comparisonBody(e)}</details>`:`<article class="card"><h2>최근 비교</h2>${comparisonBody(e)}</article>`).join(''):empty(comparisonRead.status==='failed'?'비교 자료를 불러온 뒤 확인할 수 있습니다.':'비교 기록이 없습니다. 새 비교 시작을 눌러 진행하세요.');
  container.querySelectorAll('[data-comparison-key]').forEach(node=>node.open=expanded.has(node.dataset.comparisonKey));
  container.comparisonSignature=signature;
}
async function refresh() {
  if (refreshing) { refreshQueued = true; return; }
  refreshing = true;
  try {
    state = await api('/api/state');
    initialize();
    if ($('follow-live').checked) {
      const ids = state.job?.run_ids || [];
      const live = state.runs.find(r=>r.active && (ids.length?ids.includes(r.run_id):true));
      if (live && live.run_id!==selectedRun) {
        selectedRun=live.run_id; selectedStep=null; selectedObservation=null; detail=null; detailRevision++; detailRead={status:'loading',updatedAt:null};
      }
    }
    if (!selectedRun && state.runs.length) { selectedRun=state.runs[0].run_id; detailRevision++; detailRead={status:'loading',updatedAt:null}; }
    const id=selectedRun, revision=detailRevision;
    const results=await Promise.allSettled([
      id?api('/api/run/'+encodeURIComponent(id)):Promise.resolve(null), api('/api/experiments')
    ]);
    // Selection can return to the same run while a previous request is in flight.
    if (id===selectedRun && revision===detailRevision) {
      if (results[0].status==='fulfilled' && (!id || results[0].value)) {
        detail=results[0].value; detailRead={status:id?'ready':'idle',updatedAt:id?new Date().toLocaleTimeString('ko-KR'):null};
      } else detailRead={...detailRead,status:'failed'};
    }
    if (results[1].status==='fulfilled') {
      const v=results[1].value; experiments=Array.isArray(v)?v:v.experiments||[];
      comparisonRead={status:'ready',updatedAt:new Date().toLocaleTimeString('ko-KR')};
    } else comparisonRead={...comparisonRead,status:'failed'};
    renderStats(); renderJob(); renderRuns(); renderDetail(); renderExperiments();
    renderReadStatus();
    $('connection').textContent=[detailRead,comparisonRead].some(r=>r.status==='failed')?'일부 조회 실패':'연결됨';
    $('updated').textContent='마지막 갱신 '+new Date().toLocaleTimeString('ko-KR');
  } catch(error) {
    $('connection').textContent='연결 오류';
    detailRead={...detailRead,status:'failed'}; comparisonRead={...comparisonRead,status:'failed'};
    if(state) { renderDetail(); renderExperiments(); }
    renderReadStatus();
    notify(error.name==='AbortError'?'서버 응답이 지연됩니다. 자동으로 다시 시도합니다.':error.message,true);
  } finally {
    refreshing=false;
    if (refreshQueued) { refreshQueued=false; void refresh(); }
  }
}
function checks(){const raw=$('evaluation-checks').value.trim();if(!raw){const goal=$('goal-text').value.trim();return goal?[{id:'goal-text',label:'완료 화면 문구',kind:'text_contains',selector:'body',expected:goal}]:[];}let value;try{value=JSON.parse(raw);}catch{throw new Error('기능 점검 JSON 형식을 확인하세요.');}if(!Array.isArray(value)||value.some(c=>!c||!c.id||!c.label||!['visible','text_contains','url_contains'].includes(c.kind)))throw new Error('기능 점검은 id, label, kind를 가진 배열이어야 합니다.');const goal=$('goal-text').value.trim();if(goal)value.push({id:'goal-text',label:'완료 화면 문구',kind:'text_contains',selector:'body',expected:goal});return value;}
async function chooseRun(id){detailRevision++;selectedRun=id||null;selectedStep=null;selectedObservation=null;detail=null;detailRead={status:id?'loading':'idle',updatedAt:null};$('follow-live').checked=false;navigate('history');renderDetail();await refresh();}
document.addEventListener('click',event=>{const run=event.target.closest('[data-run]');if(run)chooseRun(run.dataset.run);const evidence=event.target.closest('[data-evidence-step]');if(evidence){selectedObservation=null;selectedStep=Number(evidence.dataset.evidenceStep);$('follow-live').checked=false;navigate('history');renderDetail();}const step=event.target.closest('[data-step]');if(step){selectedObservation=null;selectedStep=Number(step.dataset.step);$('follow-live').checked=false;renderDetail();}const link=event.target.closest('[data-navigate]');if(link)navigate(link.dataset.navigate);});
document.querySelectorAll('[data-view]').forEach((button,i,list)=>{button.onclick=()=>navigate(button.dataset.view);button.onkeydown=event=>{if(['ArrowRight','ArrowDown','ArrowLeft','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();let n=event.key==='Home'?0:event.key==='End'?list.length-1:(i+(event.key==='ArrowRight'||event.key==='ArrowDown'?1:-1)+list.length)%list.length;navigate(list[n].dataset.view);list[n].focus();}};});
$('retry-data').onclick=()=>refresh();
$('setup-form').onsubmit=e=>e.preventDefault();$('run-batch').onclick=startFlow;$('run-compare').onclick=()=>{document.querySelector('[name=execution-mode][value=compare]').checked=true;navigate('test');setWizardStep(1);};$('refresh').onclick=refresh;$('run-select').onchange=()=>chooseRun($('run-select').value);$('follow-live').onchange=()=>{selectedStep=null;selectedObservation=null;refresh();};$('latest-shot').onclick=()=>{selectedStep=null;selectedObservation=null;renderDetail();};['target-url','task-input','persona-count-input','persona-background','provider','evaluation-checks','repetitions','goal-text'].forEach(id=>$(id).addEventListener('input',plan));
$('demo').onclick=()=>{if(!state)return;$('target-url').value=state.study?.start_url||'';$('task-input').value=state.study?.task||'';$('persona-background').value=state.persona_defaults?.background||'';$('persona-count-input').value=2;$('provider').value='mock';$('target-url').readOnly=false;$('task-input').readOnly=false;$('evaluation-checks').value='';$('goal-text').value='';syncModel();plan();notify('기본 데모 설정을 적용했습니다. 페르소나 생성 후 시작하세요.');};$('external-preset').onclick=()=>{$('target-url').value='';$('provider').value='gemini';$('target-url').readOnly=false;$('task-input').readOnly=false;syncModel();$('task-input').value='검색어로 상품을 검색하고 필터 적용·해제 후 조건에 맞는 상품의 상세 정보를 확인한다.';$('evaluation-checks').value='';plan();$('target-url').focus();notify('테스트 URL과 사이트에 맞는 성공 조건을 입력하세요.');};
$('connection-provider').onchange=()=>{$('fallback-field').hidden=$('connection-provider').value!=='jev';};$('connect-provider').onclick=async()=>{if(connecting)return;const key=$('api-key').value.trim(),fallback=$('fallback-key').value.trim(),provider=$('connection-provider').value;if((!key&&!state?.providers?.[provider])||(provider==='jev'&&!fallback&&!state?.providers?.gemini)){notify('연결에 필요한 API 키를 입력하세요.',true);return;}connecting=true;guideAvailability();try{const result=await post('/api/connection',{provider,...(key?{api_key:key}:{}),model:$('model-select').value,...(provider==='jev'&&fallback?{fallback_key:fallback}:{})});$('api-key').value='';$('fallback-key').value='';$('provider').value=provider;plan();notify('API 연결 완료');await refresh();}catch(e){notify(e.name==='AbortError'?'연결 요청 시간이 초과됐습니다. 상태를 확인하세요.':e.message,true);}finally{connecting=false;guideAvailability();}};
$('stop-job').onclick=async()=>{flowCancelled=true;if(posting)return;posting=true;renderJob();try{await post('/api/jobs/stop',{});notify('실행 중지를 요청했습니다. 종료 기록을 확인하세요.');}catch(e){notify(e.message,true);}finally{posting=false;await refresh();}};
window.addEventListener('error',event=>notify('화면 오류: '+event.message,true));async function poll(){await refresh();setTimeout(poll,1500);}poll();

function selectedMode(){return document.querySelector('[name=execution-mode]:checked').value;}
function syncModel(){const p=$('provider').value;syncModelChoice();$('connection-provider').value=p;$('model-connection').hidden=p==='mock'||p==='scenario';$('persona-settings').hidden=p==='scenario';$('scenario-settings').hidden=p!=='scenario';const compare=document.querySelector('[name=execution-mode][value=compare]');compare.disabled=p==='scenario';if(p==='scenario')document.querySelector('[name=execution-mode][value=batch]').checked=true;$('fallback-field').hidden=p!=='jev';$('primary-key-label').textContent=providerName(p)+' API 키';$('provider-status').textContent=p==='scenario'?'모델 API를 호출하지 않습니다.':p==='mock'?'연결 없이 시작할 수 있습니다.':connecting?'연결을 확인하고 있습니다.':guideUsesAI()?'연결됨. 다음으로 진행하세요.':state?.providers?.[p]?'선택한 모델로 연결을 확인하세요.':'키를 입력하고 연결 확인을 누르세요.';syncModelChoice();const links={live:'https://platform.openai.com/api-keys',claude:'https://console.anthropic.com/settings/keys',gemini:'https://aistudio.google.com/apikey',jev:'https://console.typesafe.ai/'};$('key-help').href=modelCatalog(p)?.key_url||links[p]||'#';$('provider-note').textContent=p==='scenario'?'사전 정의한 브라우저 동작과 코드 평가로 확인합니다. AI 판단이나 페르소나 효과 검증이 아닙니다.':p==='mock'?'번들 쇼핑 사이트에서 무료로 체험합니다.':p==='jev'?'Jev가 행동을 선택하고 Gemini가 검색어 생성과 예비 판단을 맡습니다. 두 연결이 필요합니다.':providerName(p)+' API 키로 연결합니다. ChatGPT·Claude 구독과 API 요금은 별개입니다.';}
function setWizardStep(n){wizardStep=n;for(let i=1;i<=4;i++){$('wizard-step-'+i).hidden=i!==n;document.querySelector('[data-wizard-label="'+i+'"]').setAttribute('aria-current',i===n?'step':'false');}$('wizard-back').hidden=n===1;$('wizard-next').hidden=n===4;$('run-batch').hidden=n!==4;$('wizard-position').textContent=n+' / 4';const demo=isDemoUrl($('target-url').value),scenario=$('provider').value==='scenario';$('goal-text-field').hidden=demo||scenario;$('goal-help').hidden=demo||scenario;$('evaluation-checks').closest('details').hidden=scenario;$('wizard-repeat').hidden=selectedMode()!=='compare';$('compare-plan').hidden=selectedMode()!=='compare';$('run-batch').textContent=scenario?'점검 실행':selectedMode()==='compare'?'비교 실행':'테스트 실행';syncModel();plan();}
function validStep(){const fields=wizardStep===1&&$('provider').value!=='scenario'?['target-url','task-input']:wizardStep===2&&$('provider').value!=='scenario'?['persona-background','persona-count-input']:[];for(const id of fields)if(!$(id).reportValidity())return false;if(wizardStep===3&&!['mock','scenario'].includes($('provider').value)&&(!state?.providers?.[$('provider').value]||state?.connection_models?.[$('provider').value]!==$('model-select').value)){notify('선택한 모델로 연결을 확인하세요.',true);return false;}if(wizardStep===3&&$('provider').value==='mock'&&!isDemoUrl($('target-url').value)){notify('내 사이트는 OpenAI, Claude, Gemini 또는 Jev를 연결해 사용하세요.',true);return false;}notify('');return true;}
async function startFlow(){if($('provider').value==='scenario')return startScenario();if(flowBusy||['running','stopping'].includes(state?.job?.status))return;for(const id of ['target-url','task-input','persona-background','persona-count-input']){if(!$(id).checkValidity()){setWizardStep(id.startsWith('persona')?2:1);$(id).reportValidity();return;}}if(!['mock','scenario'].includes($('provider').value)&&state?.connection_models?.[$('provider').value]!==$('model-select').value){setWizardStep(3);notify('선택한 모델로 연결을 확인하세요.',true);return;}try{checks();}catch(e){notify(e.message,true);return;}flowBusy=true;flowCancelled=false;renderJob();$('flow-progress').hidden=false;$('flow-progress').textContent='테스트할 사용자를 만들고 있습니다.';try{const payload={provider:$('provider').value,start_url:$('target-url').value.trim(),task:$('task-input').value.trim(),persona_count:Number($('persona-count-input').value),persona_background:$('persona-background').value.trim(),repetitions:Number($('repetitions').value),evaluation_checks:checks(),...(!['mock','scenario'].includes($('provider').value)?{model:$('model-select').value}:{})};const generated=await post('/api/jobs',{...payload,kind:'generate'});state.job=generated;const deadline=Date.now()+120000;let snapshot;while(Date.now()<deadline){if(flowCancelled)throw new Error('실행을 중지했습니다.');snapshot=await api('/api/state');if(snapshot.job?.job_id!==generated.job_id)throw new Error('작업이 변경됐습니다. 실행 상태를 확인하세요.');if(snapshot.job.status!=='running')break;await new Promise(resolve=>setTimeout(resolve,500));}if(snapshot?.job?.status!=='completed')throw new Error(snapshot?.job?.message||'사용자 생성 시간이 초과됐습니다.');if(flowCancelled)throw new Error('실행을 중지했습니다.');$('flow-progress').textContent='테스트를 시작합니다.';const job=await post('/api/jobs',{...payload,kind:selectedMode()});state.job=job;pendingJobId=job.job_id;selectedRun=null;selectedStep=null;$('follow-live').checked=true;notify('');navigate('history');}catch(e){notify(e.message,true);}finally{flowBusy=false;$('flow-progress').hidden=true;await refresh();}}
$('wizard-next').onclick=()=>{if(validStep())setWizardStep(wizardStep+1);};$('wizard-back').onclick=()=>setWizardStep(wizardStep-1);$('provider').addEventListener('change',()=>{if($('provider').value==='scenario')scenarioPreset();else{$('target-url').readOnly=false;$('task-input').readOnly=false;syncModel();}setWizardStep(wizardStep);});document.querySelectorAll('[name=execution-mode]').forEach(el=>el.onchange=()=>setWizardStep(4));['record-search','record-filter'].forEach(id=>$(id).addEventListener('input',renderRuns));

function scenarioPreset(){const live=$('scenario-case').value==='live';$('provider').value='scenario';$('target-url').value=live?'https://www.decathlon.co.kr/search?query=러닝화':'';$('target-url').placeholder=live?'공개 데카트론':'실행 시 로컬 주소 자동 생성';$('target-url').readOnly=true;$('task-input').value=live?'공개 검색 결과의 가격과 상세 상품명·가격 부분 확인':'준비된 스포츠 상품 재현 페이지에서 검색·필터·상세 정보를 점검';$('task-input').readOnly=true;$('scenario-source-note').textContent=live?'실제 공개 사이트의 부분 프로필입니다. 검색 폼 제출·색상·재고·픽업은 검증하지 않으며 사이트 변경 시 미확인일 수 있습니다.':'합성 상품 재현 페이지입니다. 실제 데카트론이나 AI 성능을 검증한 결과가 아닙니다.';$('scenario-defect').disabled=live;if(live)$('scenario-defect').value='';syncModel();plan();}
$('scenario-demo').onclick=()=>{scenarioPreset();notify('다음으로 진행해 점검할 과업을 선택하세요.');};$('scenario-case').onchange=scenarioPreset;
async function startScenario(){if(flowBusy||['running','stopping'].includes(state?.job?.status))return;flowBusy=true;renderJob();try{const job=await post('/api/jobs',{kind:'scenario',provider:'scenario',scenario_case:$('scenario-case').value,fixture_defect:$('scenario-defect').value||null});state.job=job;pendingJobId=job.job_id;selectedRun=null;selectedStep=null;$('follow-live').checked=true;notify('');navigate('history');}catch(e){notify(e.message,true);}finally{flowBusy=false;await refresh();}}

function modelCatalog(provider){return guideOptions?.providers?.[provider]||state?.model_catalog?.providers?.[provider];}
function syncModelChoice(){const p=$('provider').value,data=modelCatalog(p),paid=!['mock','scenario'].includes(p);$('model-field').hidden=!paid;$('provider-field').classList.toggle('full',!paid);$('key-guide').hidden=!paid;if(!data){$('model-note').textContent='';return;}if($('model-select').dataset.provider!==p){$('model-select').innerHTML=data.models.map(m=>`<option value="${esc(m.id)}">${esc(m.label)}</option>`).join('');$('model-select').value=modelChoices[p]||data.default_model;$('model-select').dataset.provider=p;}const item=data.models.find(m=>m.id===$('model-select').value);$('model-note').textContent=paid?(item?.note||''):'';$('key-steps').innerHTML=data.steps.map(step=>`<li>${esc(step)}</li>`).join('');$('key-note').textContent=data.note+' 키는 연결 자격정보이고 토큰은 요청·응답 사용량입니다. 계정 잔액·한도는 발급 사이트에서 확인하세요.';$('key-docs').href=data.docs_url||'#';}
function guideUsesAI(){const p=$('provider').value;return !['mock','scenario'].includes(p)&&!!state?.providers?.[p]&&state?.connection_models?.[p]===$('model-select').value;}
function guideAvailability(){const ai=guideUsesAI(),busy=connecting||guideBusy||!!state?.guide_busy||['running','stopping'].includes(state?.job?.status);$('guide-mode').textContent=ai?providerName($('provider').value)+' 사용':'무료 예시';if(guideLast&&guideLast.provider===$('provider').value&&guideLast.model===$('model-select').value)$('guide-usage').textContent=guideLast.text;else $('guide-usage').textContent=ai?'요청할 때만 API를 사용합니다. 도우미 최대 5회 · 토큰 예산 12,000 · 출력 1,000/회. 계정 잔액은 발급 사이트에서 확인하세요.':'연결 전에는 무료 예시를 제공합니다. 키는 AI 연결 화면에만 입력하세요.';['guide-send','guide-recommend','guide-connect','provider','model-select','connect-provider'].forEach(id=>$(id).disabled=busy);}
async function loadGuideOptions(){try{guideOptions=await api('/api/setup-guide/options');const titles={shopping:'쇼핑 검색',information:'정보 찾기',booking:'예약 안내','input-error':'입력 오류'};$('setup-presets').innerHTML=guideOptions.scenarios.map((v,i)=>`<button class="btn soft" type="button" data-preset="${i}" title="${esc(v.title+' · '+v.hint)}">${esc(titles[v.id]||v.title)}</button>`).join('');syncModelChoice();guideAvailability();}catch(e){$('guide-error').hidden=false;$('guide-error').textContent='설정 도우미를 불러오지 못했습니다. 서버를 다시 시작하세요.';}}
function applyGuidePersona(index){const item=guideCards[index];if(!item)return;if($('provider').value==='scenario'){notify('API 없는 점검은 정해진 행동을 사용합니다. AI 사용자 테스트에서 추천 사용자를 적용하세요.',true);return;}$('persona-background').value=item.background;$('persona-count-input').value=item.count;navigate('test');setWizardStep(2);notify('추천 사용자를 적용했습니다. 설명을 확인하고 다음으로 진행하세요.');}
async function askGuide(message){if(guideBusy)return;const requestedProvider=$('provider').value,requestedModel=$('model-select').value,ai=guideUsesAI(),p=ai?requestedProvider:'mock';guideBusy=true;$('guide-error').hidden=true;guideAvailability();try{const result=await post('/api/setup-guide',{provider:p,model:ai?$('model-select').value:null,message:p==='mock'&&!['mock','scenario'].includes(requestedProvider)?'현재 선택한 제공자: '+providerName(requestedProvider)+'. '+message:message,context:{target_url:$('target-url').value.slice(0,500),task:$('task-input').value.slice(0,1000),persona_background:$('persona-background').value.slice(0,1000)},history:guideHistory});guideHistory=[...guideHistory,{role:'user',content:message.slice(0,500)},{role:'assistant',content:result.answer.slice(0,500)}].slice(-6);guideCards=result.personas||[];guideTask=result.task_suggestion;$('guide-answer').textContent=(result.source==='ai'?'AI 추천 · '+result.model:'예시 추천')+' · '+result.answer;$('guide-personas').innerHTML=guideCards.map((v,i)=>`<button class="btn" type="button" data-guide-persona="${i}" title="${esc(v.background)}"><strong>${esc(v.title)} · ${esc(v.count)}명</strong><span>${esc(v.reason)} · 사용자 설명에 적용</span></button>`).join('');$('guide-apply-task').hidden=!guideTask;const u=result.usage||{};$('guide-usage').textContent=result.source==='ai'?`최근 응답 · 도우미 ${u.requests}/${u.max_requests}회 · 토큰 입력 ${u.input_tokens??'미확인'} / 출력 ${u.output_tokens??'미확인'} · 추정 비용 ${u.estimated_cost_usd==null?'미확인':'$'+Number(u.estimated_cost_usd).toFixed(5)}`:'무료 예시 · 실제 사용자 조사 결과가 아닙니다. 적용 전 설명을 확인하세요.';guideLast={provider:requestedProvider,model:requestedModel,text:$('guide-usage').textContent};$('guide-question').value='';}catch(e){$('guide-error').hidden=false;if(e.message.includes('키나 인증정보'))$('guide-question').value='';$('guide-error').textContent=e.name==='AbortError'?'추천 요청 시간이 초과됐습니다. 중복 요청 전에 상태를 확인하세요.':e.message;}finally{guideBusy=false;guideAvailability();}}
$('model-select').onchange=()=>{modelChoices[$('provider').value]=$('model-select').value;syncModel();guideAvailability();plan();};$('guide-form').onsubmit=e=>{e.preventDefault();const m=$('guide-question').value.trim();if(m)askGuide(m);};$('guide-question').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('guide-form').requestSubmit();}};$('guide-recommend').onclick=()=>askGuide('입력한 목표에 맞는 가정 사용자 3가지를 추천하고 선택 이유를 설명해 주세요.');$('guide-connect').onclick=()=>{navigate('test');setWizardStep(3);};$('guide-apply-task').onclick=()=>{if(guideTask&&$('provider').value!=='scenario'){$('task-input').value=guideTask;plan();notify('제안한 목표를 적용했습니다. 내용을 확인하세요.');}};
document.addEventListener('click',e=>{const preset=e.target.closest('[data-preset]');if(preset){const v=guideOptions?.scenarios?.[Number(preset.dataset.preset)];if(v){const demo=isDemoUrl($('target-url').value),scripted=$('provider').value==='scenario';if(scripted){$('target-url').readOnly=false;$('task-input').readOnly=false;}if(v.id!=='shopping'&&(demo||scripted)){$('provider').value='gemini';$('target-url').value='';syncModel();}else if(scripted){$('provider').value='mock';syncModel();}$('task-input').value=v.id==='shopping'&&demo&&$('provider').value==='mock'?(state.study?.task||v.task):v.task;navigate('test');setWizardStep(1);notify(v.hint);}}const persona=e.target.closest('[data-guide-persona]');if(persona)applyGuidePersona(Number(persona.dataset.guidePersona));});loadGuideOptions();


function renderBrain() {
  const target=$('brain-content'),trace=detail?.brain||{};
  const signature=JSON.stringify([selectedRun,trace,detail?.observations]);
  if(target.brainSignature===signature)return;
  const opened=new Set([...target.querySelectorAll('[data-brain-key][open]')].map(n=>n.dataset.brainKey));
  const stageNames={perception:'화면 인식',plan:'계획 생성',decision:'행동 제안',importance:'중요도 산정',reflection:'성찰 생성',plan_review:'이전 계획 검토',wonder:'Wonder 생성'};
  const statuses={scheduled:'예약',started:'진행',completed:'완료',skipped:'생략',failed:'실패',cancelled:'취소'};
  const sources=r=>`${(r.source_memory_ids||[]).some(id=>!(trace.memories||[]).some(m=>m.memory_id===id))?'<p class="error">일부 출처 기억의 원본을 찾지 못했습니다.</p>':''}<p class="help">기억 출처: ${esc(valueText(r.source_memory_ids))} · 관찰: ${esc(r.observation_id||valueText(r.source_observation_ids?.length?r.source_observation_ids:null))} · 행동 출처: ${esc(valueText(r.source_step_ids))} · 생성 단계: ${esc(r.source_stage_record_id||'미기록')} · 계획: ${esc(r.plan_id||'미기록')} / ${esc(r.plan_version??'미기록')} · snapshot: ${esc(r.snapshot_seq??'미기록')}</p>`;
  const stages=(trace.stages||[]).map(r=>`<details class="brain-record" data-brain-key="${esc('stage:'+r.record_id)}"><summary>AI 생성 · ${esc(stageNames[r.stage]||r.stage)} · ${esc(r.record_id)}</summary><pre>${esc(r.text)}</pre>${sources(r)}<p class="help">${esc(r.recorded_at||'시각 미기록')}</p>${detail?.observations?.[r.observation_id]?`<button class="btn soft" data-brain-observation="${esc(r.observation_id)}">관찰 ${esc(r.observation_id)} 보기</button>`:''}${r.action||r.finish?`<p class="help">제안이며 실행 결과가 아닙니다.</p><pre>${esc(valueText(r.action||r.finish))}</pre>`:''}</details>`).join('');
  const tasks=(trace.tasks||[]).map(r=>`<details class="brain-record" data-brain-key="${esc('task:'+r.task_id)}"><summary>${esc(statuses[r.status]||'미확인')} · ${esc(stageNames[r.kind]||r.kind)} · ${esc(r.task_id)}</summary>${sources(r)}<p>사유: ${esc(r.reason_code||'해당 없음')}</p><p>생성 기록: ${esc(valueText(r.output_record_ids))}</p><p class="help">${esc(r.recorded_at||'시각 미기록')}</p></details>`).join('');
  const memories=(trace.memories||[]).map(r=>`<details class="brain-record" data-brain-key="${esc('memory:'+r.memory_id)}"><summary>${esc(r.memory_id)} · ${r.evicted?'활성 목록에서 제거됨 · 원본 보존':'원본 기억'} · 중요도 ${esc(r.importance==null?'미산정':r.importance+' / '+r.importance_scale)}</summary><p>${r.content_status==='generated'?'AI 생성 기억':'저장된 관찰·행동 기억'}</p><pre>${esc(r.text)}</pre><p class="help">제거 사유: ${esc(r.eviction_reason||'해당 없음')} · 원본 순번: ${esc(r.seq??'미기록')}</p>${sources(r)}</details>`).join('');
  target.innerHTML=`<p class="help">AI 생성물은 실행된 행동·독립 평가·사람 검토와 별개입니다. 완료는 마지막 저장 사건의 상태이며 다음 행동에 반영됐음을 보장하지 않습니다.</p>${trace.available?'':empty('단계·비동기 기록이 없는 실행입니다. 기존 행동·평가 기록을 확인하세요.')}<div class="brain-counts">${Object.entries(statuses).map(([k,v])=>`<span class="badge">${v} ${esc(trace.task_counts?.[k]??0)}</span>`).join('')}</div>${trace.warnings?.length?`<p class="error">읽지 못한 기록 ${trace.warnings.length}건 · 일부 출처가 누락될 수 있습니다.</p><pre>${esc(valueText(trace.warnings))}</pre>`:''}<h3>단계별 생성 결과</h3>${stages||empty('저장된 생성 결과가 없습니다.')}<h3 class="gap-top">비동기 작업의 마지막 상태</h3>${tasks||empty('저장된 작업 사건이 없습니다.')}<h3 class="gap-top">원본 기억과 제거 이력</h3>${memories||empty('저장된 기억이 없습니다.')}`;
  target.querySelectorAll('[data-brain-key]').forEach(n=>n.open=opened.has(n.dataset.brainKey));
  target.brainSignature=signature;
}
document.addEventListener('click',event=>{
  const button=event.target.closest('[data-brain-observation]');
  if(button&&detail?.observations?.[button.dataset.brainObservation]){
    selectedObservation=button.dataset.brainObservation;selectedStep=null;$('follow-live').checked=false;renderDetail();
    $('shot-caption').scrollIntoView({block:'center'});
  }
});
