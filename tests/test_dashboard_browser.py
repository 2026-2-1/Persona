import json
import re
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, expect

from uxagent.monitor import Dashboard, make_handler

ROOT = Path(__file__).resolve().parents[1]


def test_provider_model_and_key_guide_send_selected_model(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        connected=[]
        def connect(route):
            connected.append(route.request.post_data_json)
            route.fulfill(json={'provider':'live','configured':True,'model':'gpt-4.1-mini'})
        page.route('**/api/connection',connect)
        page.goto(local_dashboard)
        page.locator('#wizard-next').click()
        page.locator('#wizard-next').click()
        page.locator('#provider').select_option('live')
        expect(page.locator('#model-select option')).to_have_count(2)
        page.locator('#model-select').select_option('gpt-4.1-mini')
        expect(page.locator('#key-help')).to_have_attribute('href','https://platform.openai.com/api-keys')
        expect(page.locator('#key-steps li')).to_have_count(3)
        page.locator('#api-key').fill('test-ui-credential')
        page.locator('#connect-provider').click()
        assert connected[0]['model']=='gpt-4.1-mini'
        expect(page.locator('#api-key')).to_have_value('')
        browser.close()


def test_setup_guide_template_requires_apply_and_preserves_input(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        page.goto(local_dashboard)
        expect(page.locator('#setup-presets button')).to_have_count(4)
        original=page.locator('#target-url').input_value()
        page.locator('#setup-presets button').first.click()
        expect(page.locator('#target-url')).to_have_value(original)
        page.locator('#guide-recommend').click()
        expect(page.locator('#guide-result')).to_contain_text('예시 추천')
        expect(page.locator('#guide-personas button')).to_have_count(3)
        before=page.locator('#persona-background').input_value()
        page.wait_for_timeout(1700)
        expect(page.locator('#persona-background')).to_have_value(before)
        page.locator('#guide-personas button').first.click()
        expect(page.locator('#wizard-step-2')).to_be_visible()
        assert page.locator('#persona-background').input_value()!=before
        assert page.evaluate('localStorage.length+sessionStorage.length')==0
        browser.close()


def test_ai_guide_uses_verified_model_and_keeps_token_usage(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        baseline=page.request.get(local_dashboard+'/api/state').json()
        page.route('**/api/state',lambda route:route.fulfill(json={**baseline,'providers':{**baseline['providers'],'live':True},'connection_models':{'live':'gpt-4.1-mini'}}))
        submitted=[]
        def answer(route):
            submitted.append(route.request.post_data_json)
            route.fulfill(json={'source':'ai','provider':'live','model':'gpt-4.1-mini','answer':'목표에 맞는 사용자 예시','personas':[],'task_suggestion':None,'usage':{'requests':1,'max_requests':5,'input_tokens':42,'output_tokens':12,'estimated_cost_usd':None}})
        page.route('**/api/setup-guide',answer)
        page.goto(local_dashboard)
        page.locator('#guide-connect').click()
        page.locator('#provider').select_option('live')
        page.locator('#model-select').select_option('gpt-4.1-mini')
        expect(page.locator('#provider-status')).to_contain_text('다음으로')
        page.locator('#model-select').select_option('gpt-4o-mini')
        expect(page.locator('#provider-status')).to_contain_text('선택한 모델로')
        page.locator('#model-select').select_option('gpt-4.1-mini')
        page.locator('#guide-recommend').click()
        expect(page.locator('#guide-answer')).to_contain_text('AI 추천')
        expect(page.locator('#guide-usage')).to_contain_text('42')
        page.wait_for_timeout(1800)
        expect(page.locator('#guide-usage')).to_contain_text('42')
        assert submitted[0]['model']=='gpt-4.1-mini' and submitted[0]['provider']=='live'
        assert 'api_key' not in submitted[0]
        browser.close()


def test_connection_stays_disabled_during_polling(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        pending=[]
        page.route('**/api/connection',lambda route:pending.append(route))
        page.goto(local_dashboard)
        page.locator('#guide-connect').click()
        page.locator('#provider').select_option('live')
        page.locator('#api-key').fill('test-ui-credential')
        page.locator('#connect-provider').click()
        page.wait_for_timeout(1800)
        expect(page.locator('#connect-provider')).to_be_disabled()
        expect(page.locator('#provider')).to_be_disabled()
        assert len(pending)==1
        pending[0].fulfill(json={'provider':'live','configured':True,'model':'gpt-4o-mini'})
        expect(page.locator('#api-key')).to_have_value('')
        browser.close()


def test_check_status_rows_keep_distinct_states_and_open_evidence(local_dashboard, tmp_path):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':1280,'height':720})
        payload=page.request.get(local_dashboard+'/api/run/run-0').json()
        payload['summary']['evaluator']['feature_checks']=[
            {'id':'search','label':'검색 결과','status':'pass','evidence':'검색어와 표시 결과 일치'},
            {'id':'filter','label':'가격 필터','status':'fail','evidence':'상한보다 비싼 상품 표시'},
            {'id':'detail','label':'상품 상세','status':'unknown','evidence':'재고 정보 부족'},
        ]
        page.route('**/api/run/run-0',lambda route:route.fulfill(json=payload))
        page.goto(local_dashboard)
        page.get_by_role('tab',name='실행 기록',exact=True).click()
        page.locator('#run-select').select_option('run-0')
        expect(page.locator('#feature-checks details.feature')).to_have_count(3)
        for status,label in [('pass','통과'),('fail','실패'),('unknown','미확인')]:
            expect(page.locator(f'.feature[data-status="{status}"] .feature-state')).to_have_text(label)
        row=page.locator('.feature[data-check-id="filter"]')
        row.locator('summary').click()
        expect(row).to_have_attribute('open','')
        expect(row.locator('.feature-evidence')).to_contain_text('상한보다 비싼 상품')
        page.wait_for_timeout(1800)
        expect(row).to_have_attribute('open','')
        row.locator('summary').click()
        row.locator('summary').press('Tab')
        ring=row.locator('summary').evaluate("el=>{el.focus();const s=getComputedStyle(el);return {visible:el.matches(':focus-visible'),width:parseFloat(s.outlineWidth),offset:parseFloat(s.outlineOffset)}}")
        assert ring['visible'] and ring['width']>0 and ring['width']+ring['offset']<=0
        page.locator('#feature-panel h2').click()
        page.locator('#feature-panel').screenshot(path=str(tmp_path/'check-status-preview.png'))
        row.locator('summary').click()
        expect(row).to_have_attribute('open','')
        page.locator('#run-select').select_option('run-1')
        expect(page.locator('#feature-checks details.feature')).to_have_count(0)
        page.locator('#run-select').select_option('run-0')
        expect(page.locator('#feature-checks details.feature')).to_have_count(3)
        expect(row).not_to_have_attribute('open','')
        browser.close()


@pytest.mark.parametrize("viewport", [{"width":1365,"height":768},{"width":1280,"height":720}])
def test_desktop_workspace_fits_and_keeps_results_beside_evidence(local_dashboard, tmp_path, viewport):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport=viewport)
        baseline=page.request.get(local_dashboard+'/api/state').json()
        job={'job_id':'finished','kind':'scenario','status':'completed'}
        page.route('**/api/state',lambda route:route.fulfill(json={**baseline,'job':job}))
        page.goto(local_dashboard)
        expect(page.locator('#test-runs .run-row')).to_have_count(3)
        expect(page.locator('#page-title')).not_to_be_visible()
        setup=page.locator('.wizard-card').bounding_box()
        recent=page.locator('#recent-panel').bounding_box()
        assert recent['x'] >= setup['x']+setup['width']
        assert max(setup['y']+setup['height'],recent['y']+recent['height']) <= viewport['height']
        page.get_by_role('tab',name='실행 기록',exact=True).click()
        page.locator('#run-select').select_option('run-0')
        expect(page.locator('#feature-checks .feature')).to_have_count(3)
        expect(page.locator('#run-status')).to_contain_text('성공 확인')
        expect(page.locator('#job-status-card')).not_to_be_visible()
        primary=page.locator('#history-primary').bounding_box()
        checks=page.locator('#feature-panel').bounding_box()
        assert checks['x'] >= primary['x']+primary['width']
        assert page.evaluate('document.documentElement.scrollHeight <= innerHeight')
        page.get_by_text('자료 내보내기',exact=True).click()
        expect(page.locator('#exports').get_by_text('JSON 다운로드',exact=True)).to_be_visible()
        page.get_by_text('자료 내보내기',exact=True).click()
        page.screenshot(path=str(tmp_path/'compact-history.png'))
        job['status']='running'
        expect(page.locator('#job-status-card')).to_be_visible()
        expect(page.locator('#stop-job')).to_be_visible()
        job['status']='failed'
        page.reload()
        page.get_by_role('tab',name='실행 기록',exact=True).click()
        expect(page.locator('#job-status-card')).to_be_visible()
        expect(page.locator('#job-line')).to_contain_text('실패')
        expect(page.locator('#stop-job')).not_to_be_visible()
        browser.close()


def test_scenario_wizard_has_registered_checks_and_no_key_or_generation(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        requests=[]
        def accept(route):
            requests.append(route.request.post_data_json)
            route.fulfill(json={'job_id':'scenario-ui','kind':'scenario','status':'completed'})
        page.route('**/api/jobs',accept)
        page.goto(local_dashboard)
        page.locator('#scenario-demo').click()
        page.locator('#wizard-next').click()
        expect(page.locator('#scenario-settings')).to_be_visible()
        expect(page.locator('#persona-settings')).not_to_be_visible()
        page.locator('#wizard-next').click()
        expect(page.locator('#model-connection')).not_to_be_visible()
        page.locator('#wizard-next').click()
        expect(page.locator('#plan-preview')).to_contain_text('등록된 과업별 코드 평가')
        expect(page.locator('#goal-text-field')).not_to_be_visible()
        expect(page.locator('#evaluation-checks')).not_to_be_visible()
        page.locator('#run-batch').click()
        expect(page.locator('#view-history')).to_be_visible()
        assert requests==[{'kind':'scenario','provider':'scenario','scenario_case':'flow','fixture_defect':None}]
        browser.close()


@pytest.fixture
def local_dashboard(tmp_path, monkeypatch):
    dashboard=Dashboard(tmp_path/"runs",tmp_path/"personas",ROOT/"configs/study.json")
    monkeypatch.setattr(dashboard,"_verify_connection",lambda provider,model=None:None)
    for i in range(14):
        run=dashboard.runs_dir/f"run-{i}"
        run.mkdir(parents=True)
        (run/"run.json").write_text(json.dumps({"run_id":run.name,"started_at":f"2026-10-09T00:00:{i:02d}","model":"claude-sonnet-4-6" if i==13 else "mock-v1"}),encoding="utf-8")
        (run/"persona.json").write_text((ROOT/"configs/persona.json").read_text(encoding="utf-8"),encoding="utf-8")
        (run/"summary.json").write_text(json.dumps({"verification":"failure" if i==1 else "success","termination_reason":"max_steps" if i==1 else "verified_success","evaluator":{"feature_checks":[{"id":str(j),"label":label,"status":"pass","evidence":{"scope":"fixture"}} for j,label in enumerate(["공개 검색 URL과 표시 이름","공개 검색의 최대 가격","공개 상품 상세의 이름·가격"])]} if i==0 else {}}),encoding="utf-8")
    experiment=dashboard.runs_dir/"experiments"/"e1"
    experiment.mkdir(parents=True)
    (experiment/"experiment.json").write_text(json.dumps({"experiment_id":"e1","sessions":[
        {"condition":"general","pair_persona_id":"p1","repetition":1,"run_id":"planned-only","status":"not_started","verification":"unknown"},
        {"condition":"persona","pair_persona_id":"p1","repetition":1,"run_id":"run-0","status":"completed","verification":"success"}
    ]}),encoding="utf-8")
    server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(dashboard))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown();server.server_close();thread.join(timeout=3)


def test_tabs_preserve_form_and_run_selection_during_polling(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.goto(local_dashboard)
        expect(page.locator("#connection")).to_have_text("연결됨")
        page.locator("#task-input").fill("입력 중인 과업")
        page.get_by_role("tab",name="AI 비교",exact=True).click()
        expect(page.locator("#view-compare")).to_be_visible()
        page.get_by_role("tab",name="실행 기록",exact=True).click()
        page.locator("#run-select").select_option("run-0")
        page.wait_for_timeout(2200)
        expect(page.locator("#run-select")).to_have_value("run-0")
        page.get_by_role("tab",name="과업 테스트",exact=True).click()
        expect(page.locator("#task-input")).to_have_value("입력 중인 과업")
        assert errors == []
        browser.close()


def test_key_explicit_connection_is_cleared_and_never_browser_stored(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        page.goto(local_dashboard)
        page.get_by_role('button',name='다음',exact=True).click()
        page.get_by_role('button',name='다음',exact=True).click()
        page.locator("#provider").select_option("live")
        page.locator("#api-key").fill("test-ui-credential")
        page.get_by_role("button",name="연결 확인",exact=True).click()
        expect(page.locator("#api-key")).to_have_value("")
        assert page.evaluate("localStorage.length + sessionStorage.length") == 0
        assert "test-ui-credential" not in page.request.get(local_dashboard+"/api/state").text()
        assert page.request.post(local_dashboard+"/api/connection",data={"provider":"live","api_key":"test-other"},headers={"Origin":"https://evil.test"}).status == 403
        browser.close()


def test_mobile_layout_has_no_horizontal_overflow(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={"width":390,"height":844})
        page.goto(local_dashboard)
        expect(page.locator("#view-test")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.get_by_role("tab",name="개선 보드",exact=True).click()
        expect(page.locator("#view-board")).to_be_visible()
        browser.close()


def test_unstarted_session_does_not_link_to_nonexistent_run(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        page.goto(local_dashboard)
        page.get_by_role("tab",name="AI 비교",exact=True).click()
        expect(page.locator("#experiments").get_by_role("button",name=re.compile("미확인.*미실행"))).to_be_disabled()
        assert page.locator('#experiments [data-run="planned-only"]').count()==0
        page.locator('#experiments [data-run="run-0"]').first.click()
        expect(page.locator("#view-history")).to_be_visible()
        expect(page.locator("#run-select")).to_have_value("run-0")
        browser.close()


def test_wizard_validates_and_preserves_inputs(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        page.goto(local_dashboard)
        expect(page.locator('#wizard-step-1')).to_be_visible()
        expect(page.locator('#persona-background')).not_to_be_visible()
        page.locator('#target-url').fill('')
        page.get_by_role('button',name='다음',exact=True).click()
        expect(page.locator('#wizard-step-1')).to_be_visible()
        page.locator('#target-url').fill('http://127.0.0.1:8000/shop.html')
        page.locator('#task-input').fill('검은 가방 찾기')
        page.get_by_role('button',name='다음',exact=True).click()
        expect(page.locator('#wizard-step-2')).to_be_visible()
        page.get_by_role('button',name='다음',exact=True).click()
        expect(page.locator('#wizard-step-3')).to_be_visible()
        page.locator('#provider').select_option('jev')
        expect(page.locator('#api-key')).to_be_visible()
        expect(page.locator('#fallback-key')).to_be_visible()
        assert page.locator('#provider option[value="claude"]').count()==1
        page.get_by_role('button',name='이전',exact=True).click()
        page.get_by_role('button',name='이전',exact=True).click()
        expect(page.locator('#task-input')).to_have_value('검은 가방 찾기')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        browser.close()


def test_history_search_and_filter_reach_records_beyond_twelve(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        page.goto(local_dashboard)
        page.get_by_role('tab',name='실행 기록',exact=True).click()
        page.get_by_text('기록 검색·필터',exact=True).click()
        expect(page.locator('#history-runs .run-row')).to_have_count(14)
        page.locator('#record-filter').select_option('failure')
        expect(page.locator('#history-runs .run-row')).to_have_count(1)
        expect(page.locator('#history-runs [data-run="run-1"]')).to_be_visible()
        page.locator('#record-filter').select_option('all')
        page.locator('#record-search').fill('run-0')
        expect(page.locator('#history-runs .run-row')).to_have_count(1)
        page.wait_for_timeout(1700)
        expect(page.locator('#record-search')).to_have_value('run-0')
        page.locator('#history-runs .run-row').click()
        expect(page.locator('#run-select')).to_have_value('run-0')
        page.locator('#record-search').fill('claude-sonnet-4-6')
        expect(page.locator('#history-runs [data-run="run-13"]')).to_be_visible()
        browser.close()


@pytest.mark.parametrize('generation_status,expected_jobs',[('completed',['generate','batch']),('failed',['generate'])])
def test_wizard_automatically_chains_only_successful_generation(local_dashboard,generation_status,expected_jobs):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        baseline=page.request.get(local_dashboard+'/api/state').json()
        job=None
        submitted=[]
        def state_route(route):
            route.fulfill(json={**baseline,'job':job})
        def job_route(route):
            nonlocal job
            body=route.request.post_data_json
            submitted.append(body['kind'])
            job={'job_id':body['kind'],'kind':body['kind'],'status':generation_status if body['kind']=='generate' else 'completed','message':'사용자 생성 실패' if generation_status=='failed' else '완료'}
            route.fulfill(status=202,json={**job,'status':'running'})
        page.route('**/api/state',state_route)
        page.route('**/api/jobs',job_route)
        page.goto(local_dashboard)
        for _ in range(3):
            page.get_by_role('button',name='다음',exact=True).click()
        page.get_by_role('button',name='테스트 실행',exact=True).click()
        if generation_status=='completed':
            expect(page.locator('#view-history')).to_be_visible()
        else:
            expect(page.locator('#notice')).to_have_text('사용자 생성 실패')
            expect(page.locator('#view-test')).to_be_visible()
        assert submitted==expected_jobs
        browser.close()


def test_guide_connect_survives_initial_state_load(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        pending=[]
        page.route('**/api/state',lambda route:pending.append(route))
        page.goto(local_dashboard)
        page.locator('#guide-connect').click()
        expect(page.locator('#wizard-step-3')).to_be_visible()
        response=page.request.get(local_dashboard+'/api/state').json()
        pending[0].fulfill(json=response)
        expect(page.locator('#target-url')).to_have_value(response['study']['start_url'])
        expect(page.locator('#wizard-step-3')).to_be_visible()
        browser.close()
