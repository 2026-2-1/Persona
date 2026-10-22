# 검증 기록

## 2026-10-21 입력 검사2차: 동일 토크나이저·구역 선택·제한된 복구

- 기준 실패20261021T031048-4faff60e: 첫decision에서 prompt_preflight_error: protected task/control data cannot fit,0행동/33910ms. 당시 긴 지침과 문자 추정이 보호 컨트롤을 과대 계산했다. 원본 run/설문을 수정하지 않았다.
- CPU 토큰 계산 서비스·클라이언트가 없는 상태에서 새 검사3건은 모듈 미구현으로 수집 실패했다. 구현 후 초기 관련106건, 새 계수/보호 정보/500대상 선택15건, 통합127건, 최종 조각 JSON 복구/의미 구역 포함129건이 각각 통과했다. 초기 계층 선택 검사에서 가짜 동기 I/O를 async로 잘못 만든 시험 도구 오류1건을 고쳐 동기 transport로 확인했다.
- 실제 관리 GPU를 정상 종료·기존 소유 할당 반환 확인 후 chat venv의 CPU 토큰 계산 서비스를 추가해 다시 시작했다. 원래 api_server.py 파일과 모델 설정은 바꾸지 않았다. 모델 경로/이름 상수는 AST로 읽고 같은 tokenizer/템플릿 옵션을 사용한다.
- 저장된 동일 실패 화면의 실제 Qwen 행동 제안을 재검증했다. **사전 입력2863토큰 = 서버 usage2863토큰**, 출력36토큰,1생성 요청,2444ms, 유효한Close 클릭 제안이었다. 짧은 지침/중복 제거를 적용한 재구성 입력의 문자 추정6993과 달리 정확 계수에서 허용됐고 추가 요약 요청은0회였다. 브라우저 행동은0회이며 전체 과업 성공/처리 시간 비교로 일반화하지 않는다. 원본/재검사 호출은 비공개 runs/private에 분리했다. 입력 지침과 중복 표현을 수정했으므로 원래 실패한 요청 전문을 동일하게 재전송한 검사는 아니다.
- 500대상 검사는 가짜 GPU 제공자에서 모든 대상 수가 구역 개요에 포함되고 여러 단계 선택 후24개 이하의 세부 대상으로 줄며 최종 제안이 원래 semantic ID로 복원됨을 확인했다. 실제 대형 메뉴의 선택 품질·전체 과업 성공률은 미검증이다. 명시 과업/실행 사실/선택 구역의 ID·이름·값·옵션은 요약하지 않는다.
- Mock 통합은 전체 suite와 포트가 겹치지 않게 먼저 단독 실행했다.20261021T055943-a47985ca에서30행동/종료max_steps/독립success였다. 출력은 운영 runs 밖 임시 경로에 두었다.
- compileall, 저장소 검사0 problems(새 코드/검사/매뉴얼 포함), git diff --check, doctor Chromium available/study_errors=[]를 확인했다. 최종 전체 suite는 **603 passed in362.32s**였다. Mock 통합과 직렬 수행해 포트 충돌 없이 모두 통과했다. 커밋·PR은 만들지 않았다. 최종 코드 반영을 위해 유휴 대시보드를 정상 종료/소유 GPU 반환 확인 후 다시 켰다.8765/8001/8002/8003이 모두HTTP200, GPU connected, Qwen persona-qwen, 임베딩cuda:0, 토큰 계산 한도8192를 확인하고 브라우저를 열었다.

## 2026-10-21 Qwen 공통 전송 전 검사와 계층 요약

- 기준 오류는20261020T141809-878faf84의 questionnaire 요청이다. system2577자+user27830자였다. 기존 화면 인식 분할이 설문 전체 기억에 적용되지 않았다. 원격 api_server.py를 기존 SSH master로 읽어 입력8192토큰/출력최대512토큰을 확인했다. 원격 서버 파일은 수정하지 않았다.
- 준비 기능 미구현 상태에서 새 회귀3건이 실패했다. 구현 후 검사 범위를 다단계 병합/보호 정보 거부/행동 컨트롤·페르소나 보존/잘못된 요약 로그까지 확장해 prompt_guard7건을 통과했다. 설문 통합을 포함26건, GPU/Fast/Slow/설문 기존 관련82건도 통과했다. 실제 GPU 추론 요청은 수행하지 않았다.
- 같은 실패 요청을 로컬 가짜 요약기로 재생한 결과30407→8627자,8요약 요청,최종 추정5407입력토큰이었다. 질문지와 실제 execution_trace는 원문 동일, budget requests8/reserved0이었다. 원본 run/설문은 덮어쓰지 않았다. 실제 Qwen 요약의 정확성·완전성·지연을 검증한 결과가 아니다.
- Mock 통합20261021T025325-9d4de8ab:30행동/종료max_steps/독립success였다. 운영 runs 밖 임시 경로에 기록했다. 전체 회귀 결과와 후속 확인은 아래에 기록한다.

- 전체 회귀는 **590 passed,1 failed in338.43s**였다. 실패1건은 test_runner_distinguishes_false_finish_and_repeated_state의 localhost:8000 Page.goto ERR_CONNECTION_RESET이었다. 같은 포트를 쓰는 Mock 통합과 병렬 실행해 fixture 수명이 겹쳤다. 별도 임시 summary에서도 browser_error/0행동을 확인했다. Mock 종료 후 해당 검사만 단독 재실행해 **1 passed in4.82s**였다. 전체를 한 번에591개 통과했다고 쓰지 않는다. 이후 실제 서버 포트를 공유하는 Mock 통합과 전체 suite는 직렬 수행해야 한다.
- compileall, 저장소 검사0 problems, git diff --check를 통과했다. 새 guard/검사/기존 비공개 매뉴얼도 저장소 검사 대상에 포함해 확인한다. 이번 작업에서 실제 Qwen 추론·공개 사이트 자율 실행·커밋·PR은 수행하지 않았다. 이전 실제 run은 보존했다.

## 2026-10-20 사용자 요청: AI 전체 실행 시간 제한 해제

- StudyConfig의 run_timeout_seconds 기본값과 기본/데카트론/공개 데카트론 study를 null로 변경했다. runner는 null이면 전체 deadline을 설정하지 않으며 asyncio.timeout(None)을 사용한다. 대시보드의600초 예외는 제거했다. 양수를 명시한 사용자 study는 제한을 유지한다.
- 기존 등록 과업의 시간 제한 기대값만 null로 맞췄다. 사용자 지시에 따라 테스트·라이브 과업 실행·검증 명령은 수행하지 않았다. 이전581/54건 통과 기록은 이번 변경을 검증한 결과가 아니다.

## 2026-10-20 팝업·실행 피드백·설문·사후 평가·인식 지연 순차 수정

- 기준 실패는20261020T121820-e98c2e82: 300초,4시도/1성공,action_timeout3건,unknown_evaluator. 원본 run/설문을 수정하지 않고 단계별 검증 사본은 운영 runs 밖의 임시 경로에 생성했다.
- 1단계: 닫기 아이콘 누락과 큰 GPU 입력의 modal 문맥 누락 회귀2건이 수정 전 실패했다. 후33건 통과. 실제 공개 데카트론에서 role=button/aria-label=Close가 관찰·모델 입력에 남고 ActionExecutor로 닫기 및 후속 러닝 클릭이 성공했다.
- 2단계: 실행 결과 누락/미실행 제안 오인 회귀2건이 수정 전 실패했다. runner 연결 검사까지 포함46건 통과. 실제 Qwen에 원래 실패한 클릭을 last_action_result로 전달하자 타임아웃 실패·URL 미변경으로 해석했다. 실행 허가 제한·평가 답을 추가하지 않았다.
- 3단계: 생성 기억/실행 실패 분리·오류 수 누락/불일치·오래된 survey 노출 회귀5건이 수정 전 실패했다. 민감 실행 입력 회귀 포함17건 통과. 첫 실제 Qwen 재생은 주관식 reason 누락으로 올바르게 거부됐고, 필수 필드 지시 강화 후 오류3건과 검색어 입력 성공/검색 미제출을 구분한 유효 답변을 얻었다. 오류 수만 기계 검증하며 주관적 문장 전체를 사실로 인증하지 않는다.
- 4단계: 등록 과업 평가기 연결과 홈페이지 미도달 회귀가 수정 전 실패했다. GPU/평가 관련37건 통과. 실제 홈페이지를 독립 평가하면 failure/detail_product_mismatch였다. 다른 사이트·다른 가격 목표는 등록된8만원 기준으로 평가하지 않는다.
- 5단계: control XML 중복으로 같은 인식 조각이 불필요하게 나뉘는 회귀를 수정했다. 최종 Fast/관찰/runner/설문64건 통과. 동일 저장 화면에서 행동 입력3,161자·3조각에 비해 인식 입력1,364자·1조각이었다. 실제 인식 호출은3회8,595ms에서1회3.72초로 줄었고 유효한 관찰을 반환했다. 시간은 다른 시점/부하에서의 단일 측정이며 처리량·과업 성공률 비교가 아니다.
- 6단계: 첫 자율 재실행은5행동 모두 도구상 성공했으나 이미 열린 러닝화 메뉴를 반복해300초에 종료됐다. 현재 메뉴의 하위 항목·열림 상태·모두 보기 링크를 계획에도 전달하도록 보완했다. 실제 Qwen 계획/행동과 ActionExecutor를 연결한 검사에서 러닝화모두 보기 선택 후 `/c/러닝/러닝화.html` 이동을 확인했다. 열림 상태는 관찰된 하위 경로로 추정하며 DOM의 aria-expanded 원문이라고 주장하지 않는다.
- 7단계: 원격 api_server.py를 읽어 ThreadingHTTPServer의 generate가 단일 lock으로 직렬 실행됨을 확인했다. 제공자 인스턴스별 단일 요청 큐와 Fast 우선/최대3회 후 Slow 한 차례 배정을 추가했다. 우선순위·취소·진행 중 호출 중복 방지·Slow 기아 방지 회귀를 통과했다. 실제3요청도 Slow:first→Fast:plan→Slow:waiting 순서로 완료됐다. 여러 프로세스 간 전역 큐나 실행 중인 원격 추론 선점은 구현하지 않았다.
- 후속 실제300초 검사 `20261020T133558-7d99656e`: 팝업 닫기→검색어 입력→검색 결과 이동→가격 필터 열기→80000 입력까지 **5시도/5성공**, 설문completed/오류수0 일치. 그러나6번째 판단 도중300.49초에 종료돼 독립 과업 판정은failure였다. 모델의 배열 대신 문자열 반환과 긴 feedback의512토큰 절단을 추가로 확인했다. 실패 기록을 성공으로 바꾸지 않는다.
- 8단계: 단일 관찰 문자열의 내용 보존 변환 회귀가 수정 전 실패했다. GPU 조각 응답에서만 한 원소 배열로 감싸고 다른 타입/내부 JSON 오류/빈 관찰의 기존 거부를 유지했다. feedback은1~2개 짧은 문장으로 제한하도록 지시했다. 같은 실패 입력을 실제 Qwen에 재생하자1회5.18초/70출력토큰으로 유효한 피드백을 반환했다. 프롬프트 지시가 모든 미래 출력의 정확성을 보장하는 것은 아니다.
- 전체 suite는 후속 단일 문자열 회귀 추가 직전 **580 passed in 344.05s**였다. 마지막 parser/feedback 보완 후 관련 **89 passed in 15.81s**. 후속 검사 최초 실행은 sandbox의 로컬 HTTP bind/Chromium 권한 제한으로10실패·3오류였고 같은 검사를 허용 환경에서 재실행해89건 모두 통과했다.
- 최종 mock 통합 `20261020T133809-0aaa1b15`:30행동, 종료max_steps, 독립판정success, 설문completed/오류수0 일치. 실제 GPU/공개 사이트 성공의 근거로 사용하지 않는다. compileall, parser/dashboard node --check, doctor Chromium available/study_errors=[], 저장소 검사 및 diff 공백 검사도 확인했다.
- 최종 전체 재검사는 **581 passed in 376.47s**. 이후 실제 평가 프로필 범위 회귀1건을 추가한 뒤 평가/GPU 관련 **40 passed in 12.26s**를 확인했다. 따라서581건은 마지막 프로필 변경 직전 전체 결과이고40건은 그 변경을 포함한 결과다.
- 기본300초 제한을 유지한 별도600초 진단 `20261020T134547-3f5dc86a`: **394,702ms**,7행동 모두 성공,8번째 판단에서 모델terminate/agent_finished, 설문completed/실행오류0건 일치였다. 팝업 닫기→검색→최대가격80000 적용→상품 상세 도달 후 모델이 종료했다. 모델/전송/JSON 오류는 없었다. 기본300초 내 완료를 확인한 것은 아니다.
- 9단계: 위 진단의 원래 독립 평가는unknown/basic_detail_evidence_unavailable_or_ambiguous였다. 별도 실제 BrowserSession 재검사에서 상품79,900원2곳과 함께 구매 합계109,700원이 기존 가격 선택자에 섞이는 것을 재현했다. 실제 관찰한 #product-summary-container 내부로 공개 프로필의 detail_price를 좁혔다. 합계 제외/실제 상품 가격 충돌unknown/상품 가격 부재unknown 회귀가 수정 전 실패했고 수정 후 통과했다. 동일 실제 상품 페이지를 새 브라우저에서 재검사해 **success/partial_detail_name_price_verified**, 상품명 `남성 러닝화 킵코어`, 가격79,900원을 확인했다. 원래run의unknown 기록은 덮어쓰지 않았다. 이 별도 재검사를 원래 자율 실행의 최종 판정이었던 것처럼 집계하지 않는다. 색상·사이즈·재고·픽업은 미검증이다.


- 10단계: 실제394.70초 소요에 맞춰 등록된 공개 데카트론 study의 실행 제한을600초로 조정했다. 기본 대시보드의 데모 study에서 정확히 등록된 데카트론 과업으로 전환하고 provider=gpu인 경우만 이 예산을 채택한다. 다른 과업/사이트/제공자 및 별도 사용자 study의 명시 제한은 유지한다.600초 적용 회귀는 수정 전300초로 실패했고 사용자 study의123초 보존도 함께 검사했다. 수정 후 GPU 제공자·독립 평가·runner 관련 **54 passed in 30.37s**. 이는 지연 제거가 아니라 실행 예산 조정이며 기본300초 실측 실패를 소급해 성공으로 바꾸지 않는다.

- 최종 대시보드를 정상 종료/소유 할당 반환 확인 후 재시작했다.8765 /api/state HTTP200/connected,8001 /health HTTP200/persona-qwen,8002 /health HTTP200/설정 임베딩 모델/cuda:0를 확인하고 브라우저를 열었다. 새 과업은 자동 시작하지 않았다. 커밋·PR은 만들지 않았다.

## 2026-10-20 GPU 연결 복구·JSON 오류 분리·운영 매뉴얼

- 실제 최초 증상: 작업19375는 RUNNING인데 로컬 채팅8001/임베딩8002와 SSH master가 모두 사라졌다. 기존 대시보드는 이전 연결 성공만 보고 연결됨으로 표시하고 실행을 허용했다. Fast가 전송 재시도 후 JSON 수정까지 시도해 `model_output_error: provider_transient:ConnectionRefusedError`로 남겼다.
- 실패 재현7건을 먼저 확인했다. health 감시·실행 전 검사·소유 할당 터널 복구·로그인 master 재인증 반환·전송 오류의 JSON 수정 차단·runner 연결 오류 분리를 적용한 뒤 관련96건, 전체557건이 통과했다.
- 실제 fault injection에서 단순 포트 bind가 종료된 TCP의 TIME_WAIT를 사용 중으로 판단해 복구가 지연되는 추가 문제를 발견했다. 살아 있는 listener 거부와 종료 직후 재사용을 구분하는 실제 TCP 테스트는 수정 전 실패했다. SO_REUSEADDR와 복구 시 OpenSSH의 ExitOnForwardFailure 검사 사용으로 수정 후 GPU·SSH 키·키체인 관련48건을 통과했다.
- 최종 실제 작업19378의 login/compute SSH master만 유휴 상태에서 중단했다. 같은 작업ID·이름을 유지하며 **6.92초** 만에 복구됐고 Fast 생성3회 시도 중 세 번째에 유효한 UPerception JSON을 얻었다. JSON 수정 요청은0회였다. 후속 대시보드8765·Qwen8001·임베딩8002 health는 모두 HTTP200, 모델persona-qwen 및 임베딩cuda:0를 확인했다. 시작 시 별도384차원 벡터 probe도 통과했다. 기록은 비공개 runs/private에 보존한다. 실제 Decathlon 자율 과업은 이번 검사에서 수행하지 않았다.
- 기존19375 반환,19376의 4시간 TIMEOUT,19377 정상 종료/반환을 확인했다. Slurm walltime 만료는 터널 단절과 구분하며 자동 새 할당을 무한 생성하지 않는다.
- doctor는 최초 sandbox의 Chromium 권한 제한으로 실패했고 허용 환경에서 Chromium available/study_errors=[]로 통과했다. mock 통합은20261020T022716-a447361b에서 독립판정success·종료max_steps·30행동이었다. 대량 호출 로그는 대시보드 조회 부하를 피하기 위해 운영 runs 밖의 임시 경로로 이동하고 요약만 비공개로 보존했다.
- [운영 매뉴얼](model-json-operations.md)에 증상별 대응·복구/중단 기준·JSON 교정 범위·검사 순서를 정리하고 AGENTS와 문서 진입점에 연결했다. 최종 전체 검사는 **558 passed in 344.50s**. compileall, dashboard/parser의 node --check, 저장소 검사0 problems, git diff --check도 통과했다. sandbox에서의 ssh-agent 검사 실패도 허용 환경의 관련48건 검사에서 통과했다. 커밋·PR은 만들지 않았다.

## 2026-10-19 코드 검토 5건 후속 수정

- 기준: 최신 #99 `f121aaf` + #100 `ae18a8f`, 동기화 `dc2a473`. 실제 GPU·유료 API·공개 사이트를 호출하지 않았다.
- password: 기존 Chromium 합성 재현과 같은 소스를 확인하고 대소문자 3종 × 초기/런타임 값 2종으로 회귀를 확장했다. 이번 로컬 브라우저 실행 승인 요청은 자동 검토 모델 용량 부족으로 실행되지 않았다. 로컬 doctor도 Chromium 권한 제한으로 실패했다. 브라우저 성공으로 기록하지 않는다.
- Slow: 신규 민감 출력 6개 수정 전 실패 → 수정 후 관련 Slow/호출/기록/출력 **28 passed**.
- GPU: hover/select 조작 정보 2개 수정 전 실패 → 수정 후 Fast/기억/호출 **34 passed, 2 deselected**(실제 브라우저 2개 제외).
- 취소: 실제 runner의 I/O를 대체한 6개 취소 시점 수정 전 실패 → 수정 후 취소/비교/지표 **30 passed, 5 deselected**(브라우저 실행 제외).
- 설문: 성공→6종 실패→새 답변 성공 복구 6개 수정 전 실패 → 수정 후 설문/D 결과/호출/출력 **32 passed**.
- 합산 재실행: GPU 수명주기·Fast/Slow·기억·취소·설문·D 검토/결과/출력·비교/usage·모델 설정의 브라우저 없는 회귀 **243 passed, 14 deselected in 2.85s**. 각 집중 검사와 중복되므로 검사 수를 서로 더하지 않는다.
- `compileall`, Node의 dashboard/parser 문법, `git diff --check` 통과. repo/staged 검사는 각 커밋에서 수행한다. 전체 pytest·doctor·Mock 통합의 원격 CI 결과는 PR에서 실제 실행 완료 후 확인한다.
- 명령과 PR별 중복/남은 조건: [인수인계](handoffs/2026-10-19-review-fixes.md).

## 2026-10-18 D/U 종료 후 결과·검토·출력 후속

- 대상: `codex/d-u-integration-verification-20261018`, 선행 #99 `aafea5a` + prototype `0fad8e5` 동기화. 코드 커밋 `d90ee6d` / `14ea5c8` / `ac04b04`. 원격 #95–#99 head는 변경하지 않았다. [PR 상태·재현·남은 조건](handoffs/2026-10-18-d-u-integration.md)을 따른다.
- 실패 재현 후 설문/Wonder projection, 최종 관찰/카드 버전, CLI 공개 호출, attachment 다운로드와 구형 기록 배치를 보완했다. 첫 전체 검사는 543 passed/3 failed(구형 Wonder 저장 1건, desktop 배치 2건)였고 수정 후 최종 **547 passed in 344.24s**였다. 새 검사는 `tests/test_u_result_views.py`, `tests/test_u_result_views_browser.py`, CLI 회귀는 `tests/test_call_evidence.py`에 있다.
- doctor: Python 3.13.13, Playwright 1.55.0, Chromium available, study_errors 없음. 브라우저 실행과 로컬 서버를 허용한 환경에서 검사했다. compileall, Node 문법, repo/staged 검사, diff 공백 검사 통과.
- 실제 현재 prototype 합성 필터 결함 `20261018T105758-e225f9f1`: 행동 6 PNG → valid 저장 → 새로고침 → 이력/메모/버전 유지. 독립 failure는 유지됐다. U 서버에서도 같은 구형 카드 버전을 유지하고 네 형식 다운로드와 대조했다.
- 실제 U runner+결정적 Fake 제공자 `u-d-integration-demo`: 독립 failure/agent_finished, 최종 관찰 `obs-d94b925fcb`, Slow 1worker/16cycles, Wonder 16응답/15빈응답/2생각/저장 2개, 종료 active 0. 설문을 실제 생성 경로로 작성해 AI 자기보고/질문/답변/전체 trace 출처를 확인했다.
- 최종 기본 무료 Mock `20261018T111848-04cbdb13`: 독립 success, 종료 max_steps, 행동 30회, 기록 확보율 100%, Mock 요청 로그 8,016회. 이 수는 무제한 U Slow 반복을 포함한 합성 호출 수이며 유료 API 호출 수가 아니다. 실제 GPU 호출 없이 기본 실행 경로를 확인했다.
- 같은 U 후보에서 최종 평가 화면 → deferred 저장 → 새로고침 → 이력 1건 → JSON/CSV/Markdown/HTML 실제 앱 내 브라우저 다운로드를 확인했다. JSON 카드 전체 및 네 형식의 카드 ID/근거 버전/판정/메모/별칭을 대조했다. HTML은 수정 전 download timeout 재현 후 attachment 보완으로 실제 다운로드에 성공했다. 다른 실행 왕복·자동 갱신 중 미저장 초안도 유지됐다.
- 합성 fixture/Mock 검증이다. 기업/실제 사람 데이터, GPU Qwen 생성 품질, 공개 사이트 과업 성공은 검증하지 않았다. #95/#97 생산 모듈 문제, 팀원 독립 재현, 최종 prototype 병합/CI 재확인은 남아 있다. 로컬 검사와 원격 CI는 구분한다.

## 2026-10-18 #87 U 행동 집합·AI 실행 정책

- `feat/87-u-transition-05`에서 U dispatcher의 행동(semantic click/type/raw type, 좌표 click, 방향 scroll, hover/select/clear, 전역·대상 key press, URL/history/reload, 탭 열기·전환·닫기)을 `ActionExecutor`에 연결했다. AI 행동 경로의 allowed-origin, 최신 observation/registry, capability 및 option 사전 제한을 제거하고, DOM/session 부재와 Playwright 실행 오류는 도구 결과로 남긴다. `allowed_origins` 호환 입력과 scripted offline scenario의 별도 origin guard는 보존했다.
- API/서버 bind 제한, 로컬 파일 경로 검사, credential redaction, 예산·timeout·action 한도 및 stop 동작은 유지했다. 마지막 탭 닫기 거부는 브라우저 세션 생명주기 조건이다.
- 변경 전 집중 테스트에서 기존 stale observation·origin 제한·키보드/입력 정책과 U 동작 차이가 실패로 재현됐다. 집중 회귀: `tests/test_u_actions.py tests/test_extended_actions.py tests/test_core.py tests/test_u_fast.py tests/test_runner_flow.py tests/test_offline_scenarios.py` **77 passed in 71.02s**.
- 전체 회귀 최초 실행은 **515 passed, 2 failed**였다. U 안내 프롬프트 교체에서 OpenAI 호환 단계의 rationale/finish/action field 설명이 빠진 것을 확인하고 복원했다. 해당 회귀 **2 passed** 후 전체 suite를 다시 실행해 **517 passed in 278.25s**를 확인했다.
- `python3 -m compileall -q src/uxagent tests`, `python3 scripts/check_repo.py` (PASS, 0 problems), `git diff --check` 통과.
- 브라우저 동작은 로컬 테스트 서버 두 개에서 cross-origin redirect/history와 offline scenario 경계를 확인했다. GPU Qwen 라이브 생성, 공개 Decathlon 과업 성공, 실제 사용자 사이트 행동은 수행하지 않았다.
- 이 브랜치는 선행 #86 커밋 `94b6890`에서 갈라졌으며 #83–#86 변경을 포함한다. PR은 prototype 대상으로 stacked diff임을 알리고 리뷰를 요청한다.

## 2026-10-16 최신 Brain + D/C 통합 (#69/#47/#36)

- `codex/latest-pr-integration-20261015`에 #79 고정 head `1f82379b0139`, 별도 분기된 #78 `28f912b90a7f` 및 #75 `9c397b4f94e1` 후속을 통합했다. D #68/C 측정/문서 #80을 보존했다. [통합 범위·재현·한계](handoffs/2026-10-16-latest-pr-integration.md)를 따른다.
- 최신 Fast kind·adopted/discarded·Wonder와 검증 reader/별칭의 불일치를 전용 3개 실패 테스트, 채택 배지 누락을 390px 브라우저 실패로 먼저 재현했다. reader/단일 패널/타입별 출력을 통일한 뒤 통과했다.
- 전체 pytest: 처음 402 passed/1 failed(기존 #75 중복 패널 제목), 통합 패널에 맞춰 생성/실행/독립 결과 회귀를 보존한 최종 **403 passed in 168.98s**. 이후 #75의 데이터 갱신 대기 1줄을 별도 merge하고 해당 Chromium 검사 **1 passed in 3.51s**. #78 초기화 관련 2개도 통과했다.
- doctor: Python 3.13.13, Chromium available, study_errors 없음. Node 문법, Python compileall, repo/staged 검사와 diff 공백 검사 통과. 원격 CI는 통합 PR의 현재 head 검사로 확인한다.
- 실제 무료 Mock `20261015T145603-83f78314`: 6행동·60요청·독립 verified_success, 생성 60·작업 사건 193·기억 30·Wonder 추첨 12/당첨 1·읽기 경고 0. 최신 상태 completed 47/adopted 6/discarded 7. plan_review는 stale 5 + 종료 미소비 1로 전부 폐기됐고 reflection 5/Wonder 1이 채택됐다. 실제 계획의 출처 관찰 `obs-3fda456cc3`을 화면에서 열었다.
- 실제 scripted 합성 필터 결함 `20261015T145630-7a949075`: 후보 `feature-6-filters`의 행동 6 이미지 확인 → deferred 초안 입력 → 다른 실행 왕복/자동 갱신 유지 → 저장 → 새로고침 → 이력 1건 유지. 독립 failure는 변하지 않았다.
- 두 실행의 JSON/CSV/Markdown/HTML을 저장해 상세 API와 전체 Brain/카드 ID·버전·판정·메모를 대조했다. Brain CSV 330행의 타입별 JSON과 step trace도 일치했다. 실제 인앱 JSON 다운로드는 확인했고 나머지 실제 형식은 응답을 대조했다. 자동 Chromium 회귀에서는 네 형식 모두 다운로드했다. 인앱 다운로드 도구의 긴 지연과 검증 방법을 인수인계에 명시했다.
- 유료 API·실제 사이트·사람 판단 유사성·기업 데이터는 이 검증에 사용하지 않았다. B #58/#60/#62와 prototype/main 병합은 별도다. 결과/스크린샷/원자료는 로컬 ignored/임시 폴더에 유지했다.

## 2026-10-15 23:27 KST 최신 원격 구현 반영 정정

- 직접 GitHub PR/이슈 목록과 prototype SHA를 다시 조회하고 #66/#71~#79 본문·고정 head, #79의 Brain/Runner/Slow/Memory/Schema/비교 코드를 읽었다. #78/#79의 분기와 #78 후속 패치도 확인했다. [최신 확인 기록](handoffs/2026-10-15-latest-github-review.md)에 근거를 남겼다.
- 실험/회의/제출 문서의 preview 미포함과 최신 PR 구현 포함을 구분했다. 강제 Slow 활성, 점수화 결합, 현재 검색 profile, 동일 계획 검토 채택, 8상태/D 소비 중복, 분기된 후속 수정이 연구·통합 안건에 반영됐다.
- 실제 검사: repository check PASS(0 problems), 관련 문서 6개 링크/표/펜스/문자 검사 PASS, git diff --check PASS. 새 원격 기능을 통합하거나 pytest/Mock/브라우저/유료 API를 새로 실행한 것은 아니다.

## 2026-10-15 연구·회의·제출 문서 정리

- 사용자 제공 팀 대화와 미수령 확인을 반영해 Slow 실행 빈도→검색 정책 실험 계획, 회의 안건/결정표, 기업 데이터·시스템 구조·Novelty 제출 초안을 작성했다. 기업체 자료 확보 수량은 0건이며 요청 목표·18/90/216세션은 제안으로 구분했다.
- 원문 조사로 기존 구조·성찰 비교·버전 검증 선행과 기여 후보를 별도 기록했다. 연구 신규성과 인간 재현성을 확정하지 않았다.
- 기존 메모리 계획은 2차 상세로 연결하고 현재 상태·Brain 생성 기록 계약의 오래된 표현을 preview에 맞게 정정했다. 실행 코드·스키마 변경은 없다.
- 실제 수행: repository check PASS(0 problems), 새/관련 연구 문서 5개의 로컬 링크·표 열 수·코드 펜스 검사 PASS, git diff --check PASS, 문서 커밋 전 staged 검사 PASS.
- 문서 변경이므로 pytest·Mock·유료 API·기업/사람 실험을 새로 실행하지 않았다. 324개 통과는 앞선 통합 preview의 검증 기록이며 이번 문서 작업 결과로 재사용하지 않는다.

## 2026-10-14 #40 메모리 입력 분리 첫 단계

Fast 모델 입력에서 점수 상위 기억(후보 선택 모델 4개, 생성 모델 6개)과 최근 행동 이력을 별도 필드로 전달하도록 수정했다. 변경 후 `git diff --check`와 관련 Python 파일의 `compileall`은 통과했다. pytest·실제 모델 호출·브라우저 실행은 아직 수행하지 않았다. 이 기록은 #40 전체의 완료 검증이 아니다.

## 2026-10-14 #39 Brain 기록 계약

로컬 Python 3.14에서 새 `BrainStageRecord`의 생성물·출처·계획 참조·시간대 검증 7개를 먼저 실패 재현(모델 미정의)한 뒤 통과시켰다. `python3 -m pytest -q tests/test_brain_schema.py tests/test_core.py tests/test_metrics.py`는 fixture 서버의 소켓 바인딩이 제한된 실행 환경에서 4개 실패·22개 통과였고, 소켓이 허용된 실행에서 **26개 통과**했다. `python3 scripts/check_repo.py`와 `git diff --check`도 통과했다.

후속 단계에서는 비동기 작업 사건, 메모리 변경 사건, 구버전 `MemoryEntry` 읽기, `max_active_memories` 예약 필드, 제거 후 단조 순번과 Slow 출처를 추가했다. 제거 뒤 Slow가 목록 길이를 snapshot 순번으로 쓰는 실패를 재현하고 수정했다. 양의 N을 입력해도 실제 상한이 적용되지 않는 문제를 실패 테스트로 확인한 뒤 명시적 미지원 오류로 막았다. 첫 전체 검사인 로컬 Python 3.14의 `python3 -m pytest -q`는 **197 passed in 80.46s**였다. 유료 API나 실제 외부 사이트 호출은 하지 않았다.

예약 필드의 미지원 검증을 추가한 뒤 `tests/test_brain_schema.py tests/test_core.py tests/test_dashboard.py tests/test_experiments.py` 관련 **35개가 통과**했다. `doctor --study configs/study.json`은 제한된 실행 환경에서 Chromium 권한 오류였고 허용된 환경에서 재실행한 결과 Playwright Chromium 사용 가능·설정 오류 없음이었다. `scripts/check_repo.py`와 `git diff --check`도 통과했다.

이 결과는 새 기록 스키마의 직렬화와 기존 mock/메모리·지표·대시보드·보고서 경로의 호환성 검사다. Runner가 새 Brain 단계/작업 사건을 실제로 쓰거나 두 루프가 동작한다는 검증은 아니다. 활성 N개 상한도 아직 적용하지 않는다.

이후 사용자 결정에 따라 새 메모리 중요도를 1~10으로 제한하고 구버전 1.0의 0~5점을 버전별로 읽도록 변경했다. 위 검사 수치는 이 변경 전 실행 결과이며 변경 후 검사는 아직 수행하지 않았다.

## 2026-10-09 Windows 1차 MVP

환경: Windows, Python 3.13.5, Playwright 1.55.0, Chromium 140.0.7339.16 (build 1187). 원본 e4dfa98에서 개발한 작업 트리 기준이다.

- 초기 baseline: 기존 pytest 20개 통과, doctor 오류 없음, mock 과업 6행동/6성공·verified_success.
- 최종 전체 테스트: 47 passed in 43.85s. Repository check: PASS (0 problems), staged 검사와 diff whitespace 검사 통과.
- 브라우저 검사: 4 passed in 10.23s. 메뉴 이동·입력 유지·실행 선택 유지·API 키 명시 연결/비저장·교차 origin 요청 거절·390px 모바일 overflow·미실행 근거 링크 비활성 확인.
- 비교 CLI: experiment 20261009T030843-c7571fb3, 일반 6/6 성공·페르소나 6/6 성공, system_errors 0. mock 비교이며 persona 효과를 측정한 실험이 아니다.
- 최종 리뷰의 4개 지적에 회귀 검사를 추가하고 수정했다: 기존 검색어 교체, post-action capture 누락 분모, 일반 실행 표시, 중지 세션의 사전 run ID. 미실행 ID는 실제 근거가 생기기 전 클릭하지 못하게 했다.
- 테스트에서 초기 Page.goto의 5초 제한이 한 번 초과했다. 동일 검사 단독 실행은 통과했고, 실패 유도 통합 테스트만 로컬 준비 시간을 15초로 설정한 뒤 전체 46개가 통과했다. 제품의 시간 제한은 임의 변경하지 않았다.

## 검증 범위

실제 API 키 호출, ChatGPT 구독 OAuth, 실제 데카트론의 4개 과업, 사람 검토/사용성 효과, Linux CI는 로컬 검사만으로 완료라고 판단하지 않는다. GitHub CI 결과와 마지막 통합 검사 결과는 아래에 추가한다. 인증/키 연결은 fake provider를 사용해 rollback/비노출을 검증했다.

원자료 runs/는 로컬에만 존재하고 push하지 않는다. 스크린샷의 fixture는 연구 검증용 데모다.

## 브라우저 실제 버튼 통합

기본 데모 설정 → 2명 생성 → 반복 1회 AI 비교 → 대응 세션 근거 클릭을 실제 Chromium에서 실행했다. Experiment 20261009T032000-19e8ec07: 일반 2/2·페르소나 2/2 성공, system_errors 0. 총 4세션을 예정 분모에 유지했다. API 연결과 구독 연결의 실사용 결과를 뜻하지 않는다.

## 실패 조건·내보내기와 원격 검사

- 검증용 미충족 조건을 의도적으로 등록한 fixture 실행 20261009T032454-95b9bbf3에서 실패 카드 표시와 JSON/CSV/Markdown/HTML 네 가지 HTTP 출력이 모두 정상 동작했다. 실제 발견한 사이트 결함 사례가 아니다.
- 최종 UI 변경 후 브라우저 테스트 4개 재통과. API 키 연결 실검증은 수행하지 않았다.
- GitHub 검사: https://github.com/2026-2-1/Persona/actions/runs/37879085009 (소스 커밋 e57db11). Ubuntu/Python 3.11 job 통과를 확인했다. Windows/Python 3.13 job은 이 기록 작성 당시 실행 중이며 해당 링크에서 최종 상태를 확인한다.

추가 확인: 위 e57db11 소스 기준 GitHub 검사에서 Ubuntu/Python 3.11과 Windows/Python 3.13 두 job 모두 success로 완료됐다. 이후 문서 변경 커밋은 동일 소스를 유지하며 자동 검사를 다시 실행한다.

## 2026-10-09 화면 간소화

사용자 요청으로 로컬 Pretendard Variable(-0.03em 자간), 새 SVG 심볼, 짧은 제목/작업 상태를 적용했다. 반복 연구 안내와 점으로 연결한 상태 문장을 제거했다. 기존 설정/메뉴/선택/키 비저장 회귀는 dashboard browser + MVP 검사 9개 통과. 인앱 브라우저에서 새 폰트 family와 14px 기준 자간 -0.42px, 로고 경로, 갱신된 화면을 확인했다. API/평가/비교 실행 계약은 유지한다.

로고 후속 변경: 참고 이미지의 기하학 느낌을 반영한 사각 P + ersona 벡터 워드마크와 흰색 버전, 파비콘용 P를 적용했다. 브라우저 회귀 4개 통과, 인앱 화면에서 로고 표시 확인.

이미지 로고 적용: 이미지 생성 PNG 심볼을 첫 글자 P 대신 사용하고 ersona를 연결했다. 원본 투명 알파와 전체 생성 로고를 프로젝트 assets에 보존했다. 동일 PNG 파비콘 적용, 인앱 화면 확인, 브라우저 회귀 4개 통과.

## 대시보드 단일 흐름·Claude PR

- 전체 검사: 63 passed in 43.18s. Claude fake HTTP/API 연결·rollback/비노출, 실제 FastLoop 제공자 집계, 위저드 입력 유지·키 gate·자동 생성 성공/실패 분기, 14개 기록·모델명 검색/필터·모바일을 포함한다.
- 인앱 실제 버튼: 무료 데모 → 다음 3회 → AI 비교 선택 → 비교 실행. 사용자 생성과 4세션 비교가 자동으로 이어졌다. Experiment 20261009T050944-c254441f, 일반 2/2·페르소나 2/2 성공. mock 흐름 검증이며 실행 시간 차이를 persona 효과로 해석하지 않는다.
- Claude Sonnet 4.6 Messages API 제공자를 추가했다. 실제 키 호출은 수행하지 않았으며 fake HTTP 계약으로 검증했다. Claude 비용은 미확인으로 유지한다.
- 코드 리뷰에서 모델명 검색 대상 누락을 발견해 실패 재현 후 수정했다. 상위 #6/#7/#8은 미완성 범위를 유지하고 이 작업의 하위 #13/#14/#15를 별도 완료 처리한다.


## 2026-10-11 API 없는 과업 점검 (#2 / #3)

검증 환경: Windows, Python 3.13.5, Playwright 1.55 Chromium. LLM 제공자 API 키 호출 없이 실행했다. Mock 회귀의 `complete` 호출은 로컬 모의 제공자이며 유료 API 호출이 아니다.

| 사전 정의한 합성 과업 | 실행 ID | 독립 판정 |
|---|---|---|
| 검색·색상/가격 필터·상세 | 20261010T154055-3ac4bff2 | success |
| 빈 결과·검색어 변경 | 20261010T154101-aefd008f | success |
| 필터 초기화·결과 복원 | 20261010T154105-28253f19 | success |
| 스크롤·픽업 안내 표시 | 20261010T154111-d81d66cc | success |
| 검색 결과 불일치 주입 | 20261010T154115-db985e5d | failure |
| 필터 미반영 주입 | 20261010T154202-53d0e9d7 | failure |
| 상세 누락 주입 | 20261010T154256-8954defb | failure |
| 초기화 실패 주입 | 20261010T154306-066b4f34 | failure |

위 8개 실행 모두 LLM 요청 0, 기록 확보율 100%. 합성 결함이어서 실제 사이트 결함 발견 사례가 아니다. 원자료는 Git 제외 `runs/offline-validation/`에만 보관한다.

실제 공개 사이트 실행 `20261010T153846-0c0a13c5`는 지정 `search?query=러닝화` URL부터 가격 최대 80000 적용, 상품 8926930 상세 진입까지 6개 동작을 수행했다. 표시 카드의 검색어 포함, 필터 후 표시 카드 12개 가격 <=80000, 상세 `남성 러닝화 킵코어` 79900을 확인했다. 부분 독립 판정 success, 17.134초, API 요청·토큰·비용 0, 기록 확보율 100%였다. 사이트 자체의 상품 조회 요청은 사용됐으며 LLM API 호출과 구분한다.

홈페이지 한글 검색 입력·Enter 제출 실험 `20261010T153352-0871d10a`는 입력창 `러닝화`는 확인했지만 URL 검색어가 없어 unknown으로 종료했다. 부분 결과는 제출 성공·전체 카탈로그·의미 관련성·색상·사이즈·용도·재고·픽업의 성공 증거가 아니다. 후속 확대는 [#19](https://github.com/2026-2-1/Persona/issues/19)에 기록했다.

인앱 실제 버튼: API 없는 과업 점검 → 다음 → 필터 미반영 선택 → 다음 → 다음 → 점검 실행. 사용자 생성/키 연결 없이 실행 `20261010T154423-e85c7f87` 종료, 필터 독립 failure와 카드가 생성됐다. `행동 6 근거 보기`가 최종 상세가 아니라 필터 적용 직후 화면 `obs-a7a19a85d1`로 이동하는 것을 확인했다. API 모델 호출 0회, 8개 행동·기록 확보율 100%, 8.7초였다.

리뷰에서 마지막 checkpoint가 시간 상한 뒤 success로 종료할 수 있는 문제를 재현했다. 남은 시간으로 전체 비동기 브라우저 실행을 취소하도록 수정하고, 중단 중 행동/결과를 보존하며 timeout은 unknown으로 기록한다. 행동/수동 검사/시작 중 timeout 회귀 4개를 통과했고 재리뷰에서 추가 중요 결함이 없었다.

최종 전체 pytest: **122 passed in 259.84s**. JavaScript 문법 검사, repository check(0 problems), doctor(설정 오류 없음), staged 경로/민감정보 검사와 diff 공백 검사 통과. 기존 Mock 실행 `20261010T153943-678dd2cd`는 6행동 verified_success/success, 기록 확보율100%였다. API 금지 패치 회귀와 키 없는 대시보드 job/브라우저 회귀를 포함한다. GitHub CI는 PR에서 별도 확인한다.


## 2026-10-11 오전 실제 부분 재점검·한 화면 배치

2026-10-11 09:28 KST에 실행한 `20261011T002846-0a102689`: 지정된 검색 URL/표시 이름, 최대80000 가격 필터, 킵코어 상세 이름/가격 3개 체크 pass. 상세 79900, 필터 후 표시 카드12개 상한 이내, 6개 행동 모두 성공, 21.079초, 기록100%, 모델 API0. 실행 summary와 대시보드 `/api/run/<id>`를 함께 확인했다. API 결과에서 개선 cards는 0개였다. 실패/오류가 없으므로 문제 카드를 임의 생성하지 않았다.

검색 폼 제출·재고·픽업·전체 사이트 사용성은 이 결과로 검증되지 않는다. 원자료는 runs/live-check에만 보관한다. 인앱 탭은 이전 연결 오류의 data URL에 머물러 브라우저 정책상 직접 제어하지 않았다. UI 검증은 독립 로컬 dashboard browser 회귀로 수행하며 실제 실행/카드 확인은 제공 API 응답으로 수행한다.

화면 검증은 내용이 비어 있는 시점이 아니라 세 판정과 성공 상태가 로드된 뒤 높이를 측정한다. 완료 job 배너가 남아 공간을 차지하는 회귀도 실패 재현 후 숨김 처리했고, 진행 중 배너/중지 접근은 유지한다.

최종 전체 pytest: **124 passed in 353.51s**. 1365×768 및 1280×720에서 세 판정 로드 후 완료 배너 숨김/페이지 높이, 진행 중 중지 접근, 실패 후 새로고침 시 안내 유지, 내보내기 접근을 포함한다. 기존 Mock 실행 `20261011T003722-1b102b4d`는 6행동 verified_success/success였다. JS 문법·repo/staged 경로/민감정보·공백 검사 통과. 리뷰의 실패 안내 숨김 문제를 재현·수정하고 재리뷰에서 추가 중요 결함은 없었다. 원격 검사는 PR에서 별도로 기록한다.


## 2026-10-11 점검 상태 체크리스트 (#23)

항목/상태 배지가 떨어져 보이던 표시를 아이콘·항목·상태·펼침 한 행으로 정리했다. 판정 데이터와 평가기/개선 카드 데이터는 바꾸지 않았다. 통과·실패·미확인 구분, 근거 내용, polling 뒤 펼침 유지와 실행 변경 초기화를 확인했다. 키보드 초점 테두리의 바깥 잘림을 2px+4px offset으로 재현한 뒤 안쪽 offset으로 수정해 검증했다. 이미지 예시는 독립 로컬 테스트의 합성 데이터다.

최종 전체 pytest: **125 passed in 601.70s**. JS 문법·repo/staged 경로/민감정보·공백 검사 통과. 기존 desktop 높이·모바일·위저드·키 비저장·검색 회귀를 포함한다. 코드 리뷰의 중요 초점 표시 지적을 수정했다. 원격 CI는 PR에서 별도로 기록한다.

## 2026-10-11 설정 도우미 / #25

- 전체 pytest: 184 passed (190.34s). 최종 UI 상태 문구 변경을 포함한 focused 브라우저·도우미·HTTP·모델 검사 71 passed (100.10s). 독립 리뷰의 지적 3건 수정 후 병합 차단 사항 없음.
- doctor: Python 3.13.5 / Playwright 1.55.0 Chromium / study_errors 없음.
- mock 통합: verified_success, 검색·필터·상세 pass, 6행동 / 기록 6건. 실제 LLM 호출 없음.
- node --check / git diff --check / repository check: 통과.
- 1365×768 실제 로컬 화면 캡처: 두 열·가로 넘침 없음. 유료 연결/추천은 fake 응답으로 테스트하며 실제 API 계정 지원이나 과금은 미검증이다.
- 추천은 source template/ai를 구분하고 사용자가 적용해야 사용자 설명을 바꾼다. 키·인증 URL·Unicode 이스케이프 응답 우회와 요청/토큰 한도를 재현 검사한다.

최종 화면 확인에서 초기 상태 로딩과 도우미 이동의 경합을 발견해 실패 테스트로 재현 후 수정했다. 브라우저 회귀 17 passed (249.58s). 모델 발급 안내 간격도 줄였다. 앞선 커밋의 Windows/Ubuntu CI는 모두 통과했다.

## 2026-10-11 C/P05·P06

- Baseline reports/metrics/experiments 10 passed.
- P05 계약·보고서 집중25 passed; 한글/긴 카드 ID와 동일 observation ID의 내용 변경 회귀를 포함한다. 구현자 시나리오/회귀 포함38 passed, 작업 리뷰 지적2건 수정 후 blocker 없음.
- P06 새 저장/HTTP/출력·계약·UI 집중37 passed. 보안 보완 후 candidate_reviews/setup_guide/HTTP 68 passed. 따옴표·역슬래시·개행 환경 비밀값 우회9건 실패 재현 후 통과했다.
- 합성 필터 결함 scenario 실제 실행 ID `20261011T105939-438c89d8`: failure, 검색/상세 pass·필터 fail, 8행동/기록8, LLM0. 로컬 HTTP로 테스트 판정 deferred→valid 저장 후 새 Dashboard에서 이력2건/최신valid 조회, 독립verification은failure 유지, JSON/CSV/MD/HTML 일치.
- 위 integration-test 검토는 개발용 가상 판정이며 실제 사람/독립2인검토 결과가 아니다. runs 원자료는 Git에 추가하지 않는다. 실제 사이트·유료API 검증은 이번 작업 범위가 아니다.

## 2026-10-11 C/P08

- 集중 지표·실험 검사15 passed (2.78s), 구현자 MVP/회귀 포함25 passed. scripted 분모7→5, 비유효 중앙값, null status, 저장 누락/legacy stale rate, bool 요청수의 거짓0을 실패 재현 후 수정했다.
- 무료 비교 `20261011T110414-9c0c68e4`: 일반/페르소나 각각 성공1/예정1, 요청6, 기록6/6·rate1. 비용은null/unknown1로 유지한다. 실제 LLM 성능 비교나 사람 행동 재현 증거가 아니다.
- doctor Python3.13.5/Playwright1.55.0/Chromium, study_errors없음. Mock 통합 `20261011T110505-f74829ea`: verified_success, 검색·필터·상세pass, 행동6/기록6.
- P08 작업 리뷰 지적1건 수정 후 해당 범위 blocker없음. 전체검사와 최종통합리뷰는 아래에 추가한다.

## C 최종 통합 검사

- 최종 코드 전체 pytest: **257 passed in 225.28s**. 수정 전236개 통과만으로 완료 처리하지 않고 새 실패 재현을 추가했다.
- Unicode JSONL과 실제 usage 누락 보완의 집중/통합 검사121 passed (211.83s), 안전 실행 ID 계약/저장51 passed. 통합 코드 리뷰의 두 지적과 추가 ID 호환 보완 후 Important/Critical blocker없음.
- 최종 CLI Mock `20261011T112434-c256adcb`: success, 검색·필터·상세pass, 6행동/기록6, 실제 측정토큰0/complete=true. 비용complete=false로 유지한다. 외부 유료 API 호출0.
- doctor / node --check / repo 검사 / diff 검사 통과. 1365×768 개선 보드에서 최신 판정·테스트 메모를 확인하고 가로 넘침없음. 기존 입력폼은 D 후속 범위다.
- 메모의 Unicode 구분자, 환경 비밀값 이스케이프, 동시저장/손상/경로, 비용·토큰·기록의 부분값, 실제 실행기→비교 저장→조회 경로를 검사했다.
- CI와 prototype 병합의 최종 상태는 관련 PR 기록에서 확인한다. 사람 독립 판정·실제 LLM 성능·실제 사이트 전체 평가는 이번 검사에 포함하지 않는다.

## 2026-10-13 D-01 (#32) 검토 입력·저장

- 기준: C PR #30의 b5bdffd 기반 `feat/32-candidate-review`. prototype 통합은 선행 PR 병합 후 별도 확인한다.
- 구현 전 실제 로컬 브라우저에서 `.review-form` 부재 실패를 재현했다. C 저장 API는 재사용한다.
- D-01 브라우저 12 passed (13.46s): 5종 판정 실제 HTTP 저장/새로고침, 과업 verification 유지, 메모 escaping, 400/404/409/500 입력 보존, 중복 제출 방지, 별칭·판정 필수, 실제 근거 버전 충돌 후 재조회, 모바일 가로 넘침 확인.
- 최종 기능 코드 전체 pytest: **269 passed in 91.55s**. 캡처 경로는 Windows 호환 `tmp_path`를 사용한다.
- doctor: Python 3.13.13 / Playwright 1.55.0 Chromium / study_errors 없음. JavaScript 구문·repo·diff 검사 통과.
- CLI mock 실행 `20261013T115852-e6bf1c84`: 독립 success, 검색/필터/상세 pass, 행동6·기록6/6. 외부 유료 API 호출 없음.
- 1365px 데스크톱 검토 폼 캡처를 확인했다. 390px 화면은 가로 넘침 없이 입력/저장 버튼을 제공한다.
- 위 판정은 개발용 합성 데이터·테스트 별칭이며 실제 사람 평가나 실사이트 UX 검증 결과가 아니다. 전체 이력 UI·전환/경합 회귀 확대·비교표·통합 시연은 #33~#36 후속이다.

## 2026-10-13 D-02 (#33) 초안·지연 응답

- D-01 PR #37의 59f67dc 기반. 자동 갱신·두 실행/카드 초안 보존·지연 저장 성공/실패는 기존 코드에서 통과했고, 지연 GET이 최신 판정을 미검토로 되돌리는 실패를 재현했다.
- 수정 후 전체 pytest **276 passed in 110.36s**. D-01 12개와 D-02 7개 브라우저 사례를 포함한다. 텍스트 포커스/선택, A→B→A 도중 옛 조회 무시, 실패 재시도와 다른 실행 저장 오염 방지를 검증했다.
- doctor Python 3.13.13/Playwright 1.55.0 Chromium 정상, JS 구문·repo·diff 검사 통과. CLI mock 검색/필터/상세 성공. 유료 API 호출 없음.
- 8765의 실제 화면에서 합성 상세 실패 실행 `20261013T121542-8e24cdfd`에 별칭·보류·미저장 메모를 넣고, 필터 실패 실행 `20261013T120550-f9b8ce5e`에 별도 초안을 작성한 뒤 왕복해 원래 값을 확인했다. 자동 갱신 후에도 유지됐다. 이번 수동 검사는 저장 버튼을 누르지 않았다.
- 새로고침/탭 종료 뒤 미저장 입력 복원은 지원하지 않는다. 카드 버전이 달라지면 이전 초안을 자동 적용하지 않는다. 실제 사용자 판단 데이터나 외부 사이트 검증이 아니다.

## D-03 사람 검토 이력·출처 (2026-10-14)

- D-02 PR #38 f196579 기반, #34. 관련 후속 #47은 Brain 기록 표시이며 이번 범위에 포함하지 않았다.
- 구현 전 새 이력 펼침 요소가 없어 브라우저 검사 1건 실패를 재현했다. 첫 샌드박스 실행은 로컬 소켓 권한 때문에 시작되지 않아 브라우저 실행 권한으로 다시 검사했다.
- 관련 브라우저 24개 통과(새 5개 포함), 전체 pytest 281개 통과(115.49초). 현재/이전 버전 분리, 두 번 저장·새로고침, 서버 시각, 메모 HTML 이스케이프, 390px 긴 버전 표시, 누락 출처 추정 금지, D-02 초안/지연 응답을 확인했다.
- repo 검사·diff 검사 통과. doctor: Python 3.13.13 / Chromium Playwright 1.55.0, study_errors=[]; 샌드박스 안에서는 Chromium 실행이 제한되어 허용된 환경에서 재실행했다.
- mock 통합 run 20261014T123055-19814b54: verification=success, verified_success, 6행동, 검색/필터/상세 pass. 실제 유료 모델·실제 사이트 검증이 아니다.
- 실제 로컬 대시보드에서 기존 합성 필터 결함 실행 20261013T120550-f9b8ce5e를 열었다. 사전 정의 스크립트/합성 테스트 환경 출처와 기존 검토를 확인하고 D03-화면검증 별칭의 테스트 보류 판정 1건을 추가했다. 기존 기록을 덮어쓰지 않고 2건이 표시되며 새로고침 뒤에도 별칭·판정·메모·시각이 유지됨을 확인했다. 이 기록은 실제 사용자 판단 데이터가 아니다.
- Mock 실행의 데모/미확인 출처도 실제 화면에서 확인했다. AI/live_configured 표시는 가상 API 표본으로 검증했다. 이전 버전 분리는 임시 실행의 근거를 변경하는 실제 HTTP/Chromium 테스트로 검증했다.
- 선행 #30 → #37 → #38과 prototype 통합 후의 검증 및 팀원 승인은 남아 있다. 이번 PR에서 병합하지 않는다.

## D-04 비교 측정 범위·누락 (2026-10-14)

- D-03 #49 aa3e115 기반 #35. 기존 C 집계를 재사용했으며 집계/저장 스키마 변경 없음.
- 구현 전 비교 범위 요소가 없는 실패 1건 재현. 신규 브라우저 5개 통과; 기존 D 검토 포함 29개 통과. 첫 전체 검사에서 없는 실행 버튼에 이동 ID가 남은 회귀 1건을 검출(285 통과/1 실패). 이동 ID 제거 후 관련 6개 및 최종 전체 **286개 통과 (123.01초)**.
- 실제 HTTP 집계→Chromium에서 2/5=40%, 성공0, 예정0, 취소/미실행, 부분값과 완전 측정/누락 포함 세션 수, 실제0/전체 누락, 기록0행동, 중앙값 계산 대상, scripted 제외, 없는 실행 비활성, 데이터 변경/자동 갱신 뒤 펼침 유지, 390px 가로 넘침 없음을 검사했다.
- 실제 로컬 화면은 기존 실행과 분리한 `/tmp/persona-d04-preview/runs`의 가상 표본을 8766 포트로 제공했다. 비용 전체 미확인·부분 $0.125, 토큰 부분120, 기록 전체 미확인·측정3/4=75%, 실제0원과 기록 대상행동 없음, 모델/환경 누락, 존재하는 실행 이동과 없는 실행 버튼 비활성을 확인했다. 가상 성능 수치이며 유료 모델/실제 사람/실제 사이트 결과가 아니다.
- doctor: Python 3.13.13 / Playwright 1.55.0 Chromium, study_errors=[]. Mock 20261014T124427-00482481: 6행동, verification=success, verified_success.
- repo/staged/diff 검사 통과. 선행 PR들의 prototype 통합 및 원격 CI/팀원 리뷰는 별도로 확인해야 한다. 회의록 정리는 이번 기능 문서와 별도 후속이다.

## codex 자동 CI와 D-03 D-04 원격 검사 (2026-10-14)

- push 대상에 codex/**를 추가했다. 수동 실행 없이 push 이벤트로 자동 시작됐으며 기존 권한과 검사 항목은 유지했다.
- D-03 #49의 2c42f67: [실행 38571360128](https://github.com/2026-2-1/Persona/actions/runs/38571360128). Ubuntu/Python3.11 281 passed (155.33초), Windows/Python3.13 281 passed (198.71초).
- D-04 #50의 f618818: [실행 38571422499](https://github.com/2026-2-1/Persona/actions/runs/38571422499). Ubuntu/Python3.11 286 passed (163.32초), Windows/Python3.13 286 passed (202.53초).
- 두 PR의 현재 head에 두 성공 check가 연결됨을 확인했다. 각 환경 repo 검사, doctor study_errors=[], Mock verification=success.
- D-04에 D-03 CI 변경을 병합하며 트러블슈팅 문서의 추가 문단 충돌을 해결했다. 양쪽 기록을 모두 보존했고 실행 코드 변경은 없다.
- prototype 병합과 팀원 승인은 별도다. 다른 브랜치도 이 워크플로 변경을 포함해야 codex push 검사가 실행된다.

## 2026-10-14 D-05 검토·내보내기 (작업 브랜치)

- 브랜치: `codex/36-review-export-verification`, 선행: D-04 #50 / 공유 문서 #51.
- 실제 합성 실행 `20261014T133938-52036475`: 후보 → 행동 6 화면/평가 근거 → valid 저장 → 새로고침 후 이력 1건 유지 → JSON/CSV/Markdown/HTML 대조 통과.
- HTML은 앱 내 브라우저 다운로드 도구 시간 초과 후 별도 Chromium의 실제 링크 다운로드로 확인했다. 나머지 세 형식은 앱 내 브라우저에서 다운로드했다.
- 신규 회귀 3개 포함 전체 pytest: **289 passed** (macOS, Python 3.13.13). 집중 검토·내보내기 검사: 30 passed.
- doctor: study_errors=[]; Mock: `20261014T135237-026b2a38`, verified_success, 6 actions. 실제 사용자/유료 모델 검증 아님.
- repo 검사 PASS. CI 결과는 해당 PR의 head 검사에서 확인한다.
- 근거 변경 시 Markdown/HTML에 현재 카드 버전이 없는 문제를 실패 테스트로 재현한 뒤 수정했다.
- 팀원 독립 재현, 전체 예외 상태 시연 및 prototype 통합 재검증은 남았다. [절차와 한계](tasks/d-review-export-verification.md).

## 2026-10-15 D 조회·출처·복구·예외 상태

- 선행 PR #52의 최종 CI [38575931790](https://github.com/2026-2-1/Persona/actions/runs/38575931790): Ubuntu 3.11/Windows 3.13 모두 success.
- `codex/d-dashboard-hardening`, #64/#65: 실패 테스트(조회/복구 4건, 출처 2건) 재현 후 수정. 집중 조회/검토 31 passed, 출처 3 passed, D-05/비교 12 passed.
- 전체 pytest **303 passed** (macOS Python 3.13.13). doctor 정상, repo 검사 PASS.
- 실제 Mock `20261014T165640-9f1f7163` verified_success. 새 run.json의 AI 실행/합성 출처 기록 확인.
- 실제 합성 실패 `20261014T165643-1173dceb`: 별도 임시 검토 이력 파일을 손상시켜 실제 API 오류 유발 → 마지막 정상 시각·초안 유지·저장 비활성 화면 확인 → 테스트 파일 복구 후 자동 재조회 회복 → 보존된 초안으로 deferred 저장 → 새로고침 후 이력 1건 확인. 개인/기존 실행 파일은 변경하지 않았다.
- 390px 정상/중단/빈 결과/근거 누락과 네 형식 내보내기 회귀를 추가했다. 독립 팀원 재현·prototype 통합은 남아 있다.

## 2026-10-15 Fast 단계별 생성 (#41)

- Fast의 perception·plan·decision을 별도 생성 요청으로 수행하고 단계별 입력 기억 ID, observation ID, plan ID, 생성 결과를 `brain_stages.jsonl`에 기록한다. perception·plan 생성 결과는 다음 단계 전에 메모리에 저장한다.
- Jev의 후보 선택과 생성 fallback, 완료 선언과 독립 평가 구분을 유지했다. Slow 작업 예약과 Brain 신규 조율은 포함하지 않았다.
- 전체 검사: **199 passed in 85.68s**. `python3 -m compileall -q src tests/test_fast_stages.py`, `python3 scripts/check_repo.py` (0 problems), `git diff --check` 통과.
- Doctor: Python 3.14.5, Playwright 1.55.0 Chromium available, study_errors 없음.
- mock runner 통합은 독립 성공 판정, false-finish, 반복 상태 종료와 단계 기록·중간 메모리 저장을 확인했다. 실제 유료 LLM API는 호출하지 않았다.
## 2026-10-15 D Brain 기록 소비 (#47)

- 브랜치 `codex/47-brain-trace-viewer`, 선행 D 하드닝 PR #67.
- 기존 brain 필드/화면 패널 부재를 실패 재현하고 선택적 JSONL 읽기·6상태·제거 원본·내보내기를 연결했다.
- 전체 pytest **310 passed** (macOS Python 3.13.13), doctor 정상, repo/diff 검사 PASS.
- 첫 전체 검사에서 데스크톱 기본 화면의 세로 넘침 1건 발생: Brain과 비용의 접힌 패널을 같은 카드로 묶은 후 데스크톱 두 크기/390px/정확한 관찰 연결 및 전체 검사를 다시 통과했다.
- 소비 가상 표본: append 상태·원본 제거 이력·손상/교차 실행/심볼릭 링크·비밀값 제거·네 형식 대조. 생성 실행기와의 실제 Mock 통합은 별도 격리 체크아웃 검증으로 기록한다.
- D 하드닝 CI [38602694973](https://github.com/2026-2-1/Persona/actions/runs/38602694973): Ubuntu 3.11/Windows 3.13 모두 success.

## 2026-10-15 A+D 격리 통합 (#69)

- D 소비 d79a9b8 + A Fast 2c5f72a를 별도 checkout/preview에서 통합. 실행 출처와 Brain writer, C 실측 usage completeness를 함께 보존했다.
- 전체 pytest **324 passed** (macOS Python 3.13.13), doctor 정상, repo 검사 PASS. 테스트한 src/tests 트리와 최종 통합 merge 트리의 diff=0을 확인했다.
- 기존 C 사용량 기대값을 3 Fast+4 중요도 요청에 맞춰 보완하고 fast-stages-1 버전 기록을 실패 재현 후 구분했다.
- 실제 무료 Mock `20261014T171511-3d562d94`: 6 actions/42 interface requests/verified_success, 42 stage records/72 task events/24 latest tasks/24 original memories/warnings 0. 브라우저의 계획→정확한 관찰 연결 및 네 형식 다운로드 대조 통과.
- B live PR과 Slow 전체 조율, 팀원 재현·prototype 통합은 미포함. [아침 인수인계](handoffs/2026-10-15-morning.md).
추가 실제 시연에서 긴 Brain 목록의 출처 버튼이 이미지만 바꾸고 근거를 화면 밖에 남기는 문제를 발견했다. 30개 선행 기록을 넣어 viewport 검사 실패를 재현하고, 선택한 관찰 설명으로 이동하도록 수정했다. 출처/데스크톱 집중 4개를 통과했다.

원본 기억의 source_observation_ids/source_step_ids/source_stage_record_id도 표시한다. 단일 단계의 observation_id만 읽어 관찰 출처를 미기록으로 보이던 경우를 브라우저 실패로 재현하고 수정했다. 최종 소비 전체 310개 검사를 다시 통과했다.

최종 preview는 원본 기억 출처 보완 e20d7fb까지 포함해 전체 324개 검사를 다시 통과했다. 출처 화면 이동 보완 뒤 실제 브라우저의 선택 관찰도 viewport 안에서 확인했다. CI 결과는 각 PR의 현재 head 검사를 기준으로 읽는다.

### #41 PR 코드 리뷰 보완

형식이 틀린 첫 응답과 복구된 두 번째 응답을 fake provider로 재현했다. 수정 전에는 예산 요청 2회에 비해 Fast 호출 로그가 1건이었고, 수정 후 두 응답의 사용량을 각각 기록한다. `tests/test_fast_stages.py`: 3 passed, 전체 pytest: 200 passed (81.18s). 유료 API 호출 없음.

Jev가 입력 후보를 고른 뒤 생성 모델이 `give_up`을 반환하는 경로에서 null action 검사가 실패하는 것을 재현했다. 종료 선언을 보존하도록 수정했고 Fast·Jev 관련 검사 9개, 전체 pytest 201개(81.56s)가 통과했다. 유료 API 호출 없음.

## 2026-10-15 Slow 성찰·계획 검토 (#42)

- 전체 pytest: **204 passed in 80.86s**. Slow 전용 테스트는 대기열 무제한 예약, 비동기 호출, 성찰/계획 검토 기록, 고정 snapshot, provider 실패·timeout 기록과 mock runner 연결을 확인했다.
- `python3 -m compileall -q src tests/test_slow_loop.py tests/test_core.py`, `python3 -m json.tool docs/tasks/manifest.json`, `python3 scripts/check_repo.py` (0 problems), `git diff --check` 통과.
- 신규 메모리 중요도는 5로 고정되며 점수 산정 API/작업은 실행되지 않는다. Slow 결과는 기존 계획을 바꾸지 않고 기록·메모리 후보만 추가한다.
- 네트워크 기반 유료 LLM 호출은 하지 않았다. 브라우저 통합 검사는 로컬 fixture와 mock provider를 사용했다.

### #42 PR 코드 리뷰 보완

Slow 모델이 잘못된 JSON을 반환해 작업이 실패해도 응답의 입력·출력 토큰을 별도 호출 로그에 기록한다. 수정 전에는 예산 요청 1회에 사용량 로그 0건이었다. fake provider 기반 Slow/Fast 관련 검사 4개, 선행 #41 수정 병합 후 전체 pytest 207개(81.38s) 통과. 유료 API 호출 없음.

## 2026-10-15 Brain 두 루프 조율 (#43)

- 전체 pytest: **212 passed in 82.28s**. fake provider 검사에서 stage 경계 reflection 채택, observation/plan ID/version이 맞는 plan review만 decision 문맥에 전달, stale 결과 폐기, 종료 시 실행 중·대기 작업 취소, general 조건 persona context 축소, run 메모리 격리를 확인했다.
- mock runner에서는 legacy `enable_slow_loop=false` 입력에도 Fast/Slow가 구성되고, Fast stage task ID와 stage record 연결, reflection/plan review 예약·상태 기록을 확인했다.
- `python3 -m compileall -q src tests/test_brain.py tests/test_brain_schema.py tests/test_slow_loop.py tests/test_fast_stages.py tests/test_model_selection.py`, `python3 -m json.tool docs/tasks/manifest.json`, `python3 scripts/check_repo.py` (0 problems), `git diff --check` 통과.
- 요청 수/총토큰 제한은 기본 `null`이며 대기열 상한을 추가하지 않았다. 테스트는 가짜 provider와 로컬 fixture를 사용했고 실제 유료 API는 호출하지 않았다.

### #43 PR 코드 리뷰 보완

채택한 reflection을 일반 검색 결과에서 제외해도 다음 Fast decision 입력에 전달되도록 경계 결과를 우선 삽입한다. 기존 계획 검토의 정확한 observation/plan/version 검사와 입력 개수 상한은 유지한다. fake provider 및 mock runner로 재현했다. 선행 #41·#42 수정 병합 후 전체 pytest 216개(83.73s) 통과. 유료 API 호출 없음.

## 2026-10-15 Runner 평가 순서 (#44)

- 코드 변경: 초기 `evaluate()`의 조기 종료를 제거하고 행동 후 재관찰 또는 `finish` 선언 때 독립 평가한다. 단계 기록에 평가 근거와 관찰 시각을 연결한다.
- 검증 상태: 초기 성공·종료 선언·실행기 차단·후속 관찰 실패·모델 시간 초과·행동 중 중지의 mock runner 검사 6개와 전체 pytest 225개(91.75s)가 통과했다. 후속 관찰 뒤 summary가 이전 관찰을 가리키는 문제는 실패 재현 후 수정했다. 중지 시 현재 행동 기록과 비교 실행의 미시작 세션 보존, 페르소나 생성 중지에서 다른 실행을 건드리지 않는 동작은 전용 테스트로 확인했다. 실제 대시보드 하위 프로세스 검증에서는 `stopping` → `cancelled`, 취소 요약과 행동 시도·단계 기록 각 1건을 확인했다. `python3 -m uxagent run --study configs/study.json --provider mock --headless`는 처음에 로컬 포트 바인딩이 샌드박스에서 거부되어 실패했고, 허용된 권한으로 최종 재실행해 6회 행동 뒤 `verified_success`·기록 완전성 6/6을 확인했다. `node --check src/uxagent/dashboard/app.js`, Python compileall, 저장소 검사도 통과했다. 실제 유료 API/공개 사이트 성공은 확인하지 않았다.

## 2026-10-15 Persona 기반 Wonder (#45)

- 먼저 Wonder 전용 실패 재현 테스트를 작성했고, 초기에는 새 생성자 인자가 없어 5개가 실패했다. 구현 후 `python3 -m pytest -q tests/test_wonder.py` **13 passed**, 전체 `python3 -m pytest -q` **238 passed in 90.84s**.
- 고정 seed 139의 당첨·비당첨, 시작된 Slow 작업 ID별 1회 추첨, 일반 조건의 공통 제약만 전달, 제공자 내부 재시도, 요청 예산 부족, 활성 기억 N=10에서 과업 기억 보존과 기존 Wonder 우선 제거, 실행 종료 취소, 비밀 패턴 출력 거부, 대시보드·보고서 가정 표시를 확인했다.
- `python3 -m uxagent run --study configs/study.json --provider mock --headless`: 로컬 fixture에서 행동 6회 후 `verified_success`, 기록 완전성 6/6, 시작된 Slow 작업 12개와 Wonder 추첨 12개. 무작위 seed 실행이라 이 실행에서는 당첨이 없었고, 고정 seed 139 당첨은 전용 mock runner 테스트로 확인했다.
- `git diff --check`, `node --check src/uxagent/dashboard/app.js`, `python3 -m compileall -q src tests/test_wonder.py`, `python3 -m json.tool docs/tasks/manifest.json`, `python3 scripts/check_repo.py`: 통과. `python3 -m uxagent doctor --study configs/study.json`는 샌드박스의 Chromium 프로세스 등록 제한으로 첫 시도에 실패했고, 허용된 권한으로 재실행해 browser available·study_errors 없음으로 통과했다. 로컬 fixture와 mock/fake provider만 사용했고 유료 API·실제 사람 행동은 검증하지 않았다.

## 2026-10-15 두 루프 제공자·예산·비교 호환 (#46)

- 먼저 #46 전용 실패 재현 5개가 각각 예산 원인·Fast 재시도 로그·Slow 실제 provider·Jev 사전 차단·실행 모델 경로의 누락으로 실패했다. 구현 후 전용 검사는 14개가 통과했다.
- mock runner: `python3 -m uxagent run --study configs/study.json --provider mock --headless`에서 6회 행동 후 `verified_success`, 기록 완전성 6/6, LLM 호출 30회, Slow 작업 12개. 기본 요청/총토큰 상한은 `null`, 실행 상한은 30회 행동·300초로 유지했다. 이 결과는 이후 30회 행동의 비용/성공을 예측하지 않는다.
- 가짜 Jev/Gemini 제공자를 쓴 로컬 browser fixture에서 perception·plan·reflection·plan_review는 Gemini 모델, 후보 선택은 `jev-latest`로 기록되는 것을 확인했다. 키 누락·미지원 embedding은 실행 기록 또는 비교 세션 생성 전에 거부되는지 확인했다. 실제 유료 API 호출·계정별 모델 접근은 검증하지 않았다.
- 일반 조건에서 Fast·Slow·Wonder 생성 입력 전체에 persona 배경·숙련도·선호가 전달되지 않는지 확인했다. 의도치 않은 Slow persona 필드가 들어오면 비교를 차단하는 검사도 통과했다.
- `python3 -m pytest -q`: **252 passed in 96.24s**. `python3 -m uxagent doctor --study configs/study.json`: Chromium available, study_errors 없음. `python3 -m compileall -q src tests/test_provider_budget.py`, `python3 -m json.tool docs/tasks/manifest.json`, `python3 scripts/check_repo.py`, `git diff --check`: 통과.

## 2026-10-15 두 루프 기록 소비 (#47)

- 새 기록 소비 실패를 먼저 재현했다. 단계·작업·기억 로그를 만든 실행 상세에 `brain_tasks`와 `trace`가 없어 전용 테스트 2개가 실패했다. 구현 후 로컬 기록 소비·보고서 관련 24개가 통과했고, 새 Chromium 표시 테스트 1개와 데스크톱 높이 회귀 검사 2개가 통과했다.
- 첫 전체 검사에서는 새 최상위 기록 카드가 1365×768 화면 높이를 넘겨 **253 passed, 1 failed**였다. 기록 펼침을 기존 모델 호출 카드 안으로 옮겨 해당 브라우저 회귀를 수정했다. Wonder 부모 연결과 테스트 fixture 보완을 포함한 최종 `python3 -m pytest -q`는 **255 passed in 105.35s**였다.
- `python3 -m uxagent run --study configs/study.json --provider mock --headless`: `20261015T060054-5e8459e2`, 6회 행동·30회 모델 호출·12개 Slow 작업 뒤 `verified_success`, 기록 확보율 6/6. 해당 실제 로컬 기록의 상세 API에서 행동 trace 6건, 생성 단계 30건, 작업 사건 102건, 원본 기억 29건을 읽었고 JSON/CSV/Markdown/HTML 출력이 모두 열리는지 확인했다. 이는 로컬 fixture와 mock 모델의 동작 확인이며 실제 API/사이트 성과가 아니다.
- `python3 -m uxagent doctor --study configs/study.json`: Chromium available, study_errors 없음. `node --check src/uxagent/dashboard/app.js`, Python compileall, manifest JSON 파싱, `python3 scripts/check_repo.py`, `git diff --check`: 통과. 실제 유료 API·공개 사이트·인간 행동 유사성은 검증하지 않았다.

## 2026-10-15 공유 기억 중요도 산정 (#40)

- 원본 기억은 `null` 점수로 남기고 동일 ID·순번·생성 시각에 1~10점 변경을 적용하는 실패 재현 테스트를 작성했다. Slow의 비동기 점수 호출, 공통 예산, 제거된 기억의 늦은 응답 폐기, 잘못된 점수와 예산 소진 기록을 확인했다. 중요도 전용 5개 테스트가 통과했다.
- 첫 전체 pytest는 이전의 5회 모델 호출을 고정한 모델 선택 테스트 때문에 **257 passed, 1 failed**였다. fake provider와 호출 단계 기대값에 importance를 추가했다. 실패·예산 테스트 2개를 포함한 최종 전체 pytest는 **260 passed in 99.54s**, 중요도 전용 검사는 **5 passed**였다.
- `python3 -m uxagent run --study configs/study.json --provider mock --headless`: 로컬 fixture 실행 `20261015T061604-f58f1f64`에서 6회 행동 후 독립 판정 `verified_success`, 기록 확보율 6/6. 총 모델 요청 58회 중 중요도 요청 28회가 완료됐고, 원본 기억 29개는 모두 `null`로 남으며 28개 점수 변경 사건이 따로 기록됐다. 마지막 기억 1개는 종료 시 아직 산정 작업이 예약되지 않아 실행 요약 `importance_scoring_status=pending`이다. 이는 종료 시점의 미산정 상태를 숨기지 않는다.
- `python3 scripts/check_repo.py`, `python3 -m compileall -q src tests/test_memory_importance.py tests/test_model_selection.py`, manifest JSON 파싱, `git diff --check`: 통과. 위 검사는 mock/fake provider와 로컬 fixture만 사용했다. 실제 유료 모델의 점수 품질·추가 비용·공개 사이트 성공은 검증하지 않았다.

## 2026-10-15 메모리 검색 정책 (#54)

- 같은 입력에서 #40 동일 I/Q/R 기준선과 Fast 계획·행동 결정의 종류 가중치, Slow 최신성 가중 검색 순서를 비교했다. 미산정 기억과 점수 갱신, 60초 반감기, 알 수 없는 검색 mode를 전용 검사 5개로 확인했다.
- 첫 전체 pytest는 Slow 검색이 현재 관찰 원본을 밀어내 성찰 채택 테스트가 **263 passed, 1 failed**였다. 현재 관찰을 Slow snapshot의 필수 기억으로 추가한 뒤 관련 Brain·Slow·검색 검사 18개가 통과했다.
- 최종 전체 `python3 -m pytest -q`: **265 passed in 97.89s**. `python3 scripts/check_repo.py`, Python compileall, manifest JSON 파싱, `git diff --check`도 통과했다.
- `python3 -m uxagent run --study configs/study.json --provider mock --headless`: 로컬 fixture `20261015T062424-1aa372d6`에서 6회 행동, 총 58회 mock 모델 요청, 독립 판정 `verified_success`, 기록 확보율 6/6, reflection 채택 5건을 확인했다. 실제 유료 API나 공개 사이트의 성공·시간 가중치 품질은 검증하지 않았다.

## 2026-10-15 활성 기억 제거 경계 (#55)

- 먼저 N=10 현재 단계 보호, N=12 미산정 대기 보존, N=10 대기 제거 이유, 임베딩 요청 중 제거 테스트를 작성했다. 4개 중 3개가 보호 API·우선순위·이유 누락으로 실패했다. 구현 후 오래된 Slow snapshot의 원본 출처 테스트도 포함해 전용 **5 passed**였다.
- 최종 `python3 -m pytest -q`: **270 passed in 97.54s**. 현재 단계·최근 10개가 충돌해도 활성 상한을 지키고, 제거 원본 ID와 Slow 출처, 제거 후 늦은 embedding 결과의 캐시 미복원을 확인했다. 최신 10개는 Wonder를 제외한 과업 기억에서 센다.
- `python3 -m uxagent run --study configs/study.json --provider mock --headless`: 로컬 fixture `20261015T063224-537d7a15`에서 6회 행동·58회 mock 모델 요청 후 독립 판정 `verified_success`, 기록 확보율 6/6. 기본 상한 64개에서 제거 경계는 발생하지 않았고 N=10/12 충돌은 전용 테스트로 확인했다. 실제 유료 API·공개 사이트·사람 행동은 검증하지 않았다.

## 2026-10-15 기억 점수·상한·출처 종합 검증 (#56)

- `tests/test_memory_integration.py`의 로컬 mock runner 2개(활성 상한 10·64)와 빈 기억·오래된 고점 제거/순번 테스트 1개를 추가했다. **3 passed in 6.84s**. 상한 10 실행에서는 제거 사건이 발생했고, 64 실행에서는 발생하지 않았다. 두 실행 모두 원본 기억 ID·점수 변경·Slow 작업/단계 출처·호출 수와 공통 예산을 대조했다. Fast 계획의 검색 기억 최대 6개와 별도 최근 행동 이력도 확인했다.
- 전체 `python3 -m pytest -q`: **273 passed in 102.92s**. 여기에는 #40의 점수 실패·예산·늦은 응답, #47의 이전 JSONL·null 행동, #54 검색 순위, #55의 N=10/12·Slow snapshot·embedding 경합, 기존 Slow 취소 회귀가 포함된다.
- mock/fake provider와 로컬 fixture만 사용했다. 실제 유료 API·공개 사이트 성공·사람 행동 유사성은 검증하지 않았다.
## 2026-10-15 실제 OpenAI 연결 / #57

- 증상: 실제 `gpt-4o-mini`로 합성 shop.html 과업을 실행하면 첫 결정에서 `model_error`로 종료됐다. 첫 실행은 `perception` 객체·`finish: false`, 프롬프트 1차 수정 후에는 `observation_id` 누락·`value` 필드 사용으로 `AgentDecision`/`Action` 검증에 실패했다.
- 원인: Fast Loop 시스템 프롬프트가 필드 이름만 나열하고 필드 형식과 행동별 허용 필드를 명시하지 않았다. mock·fake HTTP 테스트에서는 드러나지 않았다.
- 해결: 문자열 필드, action/finish 중 하나만 객체, finish 구조, 행동별 허용 필드를 프롬프트에 명시했다. 프로젝트 모델 목록의 OpenAI 단가(gpt-4o-mini 0.15/0.60, gpt-4.1-mini 0.40/1.60 USD per 1M, 표준 요금)를 추가했다. 공식 요금표 변경 시 갱신이 필요하다.
- 실제 실행(유료 API, 키는 로컬 `.env`): 수정 전 `20261014T153403-c958d7b5` model_error, 1차 수정 후 `20261014T154056-7b12da8f` model_error($0.00063), 최종 `20261014T154123-dda0d05a` verified_success 3행동·3요청·5,617토큰·$0.00102·10.8초, `20261014T154144-e76d8432` verified_success 2단계·2요청·3,556토큰·$0.00065·6.3초. 원자료 runs는 커밋하지 않는다.
- 전체 pytest 188 passed, 재현 테스트 3 passed, doctor 정상, mock verified_success, repository check PASS.
- 남은 범위: 데카트론 페이지의 AI 실행·판정 연결(P04), 실제 데카트론 검색 제출(#19), Claude/Gemini 경로의 같은 프롬프트 실측은 미검증이다. 반복 실행 수가 적어 형식 오류 재발률은 확인하지 않았다.

## 2026-10-16 prototype 병합 준비: #31/#58 호환

- 원격 보호 설정 승인 전 격리된 로컬 준비본에서만 작업했다. prototype 병합/브랜치 삭제 완료를 뜻하지 않는다.
- #31 협업 문서와 최신 #81의 연구/상태 링크를 모두 보존했다.
- #58의 행동 필드 명세를 최신 3단계 Fast의 decision 프롬프트에 연결했다. 기존 단일 decide 전제 테스트를 실제 decision API에 맞췄다.
- 날짜 snapshot 응답 모델의 비용 미확인과 프롬프트 필드 명세 누락을 2개 실패로 재현했다. 실제 응답 모델 식별을 유지하고 명시적으로 확인한 snapshot만 단가표에 추가했다. 알 수 없는 모델은 null을 유지한다.
- 단가는 [GPT-4o mini 공식 모델 문서](https://developers.openai.com/api/docs/models/gpt-4o-mini)와 [GPT-4.1 mini 공식 모델 문서](https://developers.openai.com/api/docs/models/gpt-4.1-mini)를 2026-10-16 확인했다. 입력/출력 토큰 기준 추정이며 계정 청구액·캐시 할인·기타 서비스 요금의 실측값이 아니다.
- 최종 준비본 전체 pytest 406 passed in 168.43s. 무료 Mock `20261015T164134-c9f17515` 종료 `verified_success`, doctor·Node·compileall·repo/staged·diff 검사 통과. 원격 prototype 병합은 보호 설정 변경 명시 허용 대기다.

## 2026-10-16 사용자 명시 허용 후 순차 병합

이번 작업에 한해 승인 수 1→0→1의 일시 변경을 허용받았다. CI·strict·관리자 적용은 유지하며 각 시도 직후 복원한다. 위 준비 당시 허용 대기 기록과 현재 권한을 구분한다. 원격 결과는 개별 PR의 squash commit과 최신 CI에서 확인하며, 전체 절차·로컬 검증·남은 문제는 [병합 기록](handoffs/2026-10-16-prototype-merge-queue.md)을 따른다.

#57 단계별 추가 호환: 팀원의 `fix/57-staged-openai-format`에서 인식·계획의 평문 문자열 요구를 보존했다. 해당 명세 누락 실패 1개를 재현한 뒤 수정했고 Fast/OpenAI/예산 관련 23개가 통과했다. 행동 결정의 기존 필드·미확인 모델 null 규칙은 유지한다. 실제 API 재검증은 수행하지 않았다.
## 2026-10-15 단계별 OpenAI 응답 형식 (#57, 팀원 staged 브랜치 기록)

- 단계별 Fast의 자료형·행동 필드와 `gpt-4o-mini` 가격 누락에 대한 테스트 2개가 수정 전 실패하고 수정 후 통과했다.
- `python3 -m pytest -q --tb=line`: **275 passed in 103.92s** (로컬 브라우저 서버 사용을 허용한 실행). 제한된 샌드박스 첫 시도는 소켓 생성 불가로 45 failed, 209 passed, 21 errors였으며 코드 회귀 판정에 사용하지 않았다.
- `python3 scripts/check_repo.py`: 0 problems. 실제 API 호출은 `OPENAI_API_KEY`가 현재 실행 환경과 로컬 `.env`에 없어 수행하지 못했다. 모델 형식의 실호출 성공은 미검증이다.
- `python3 -m uxagent run --study configs/study.json --provider mock --headless`: 로컬 fixture 실행 `20261015T064911-78e45798`에서 6회 행동·58회 mock 모델 요청 후 독립 판정 `verified_success`, 기록 확보율 6/6이었다. Python compileall과 `git diff --check`도 통과했다.

## 2026-10-15 합성 데카트론 AI 평가 연결 (#59)

- 평가 기대값을 설정에 넣은 실패 재현 3개가 기존 StudyConfig의 extra field 오류로 실패했다. 구현 후 가짜 단계별 제공자를 사용한 실제 로컬 브라우저 실행에서 일치 상세는 `verified_success`, 불일치 상세 2개는 `agent_finished`·`failure`였다. 정답 상품명은 모델 과업 문장에 넣지 않았다.
- 첫 전체 pytest는 기존 runner의 평가기 mock에 새 인자를 넘겨 **277 passed, 2 failed**였다. 기대값이 없는 기존 study의 호출을 유지하도록 수정한 뒤 관련 **10 passed**, 최종 전체 **279 passed in 108.03s**였다.
- `python3 scripts/check_repo.py`, Python compileall, study JSON 파싱, `git diff --check` 통과. 실제 OpenAI API 호출은 현재 로컬 키가 없어 수행하지 못했다. 제공자 실호출의 과업 성공은 미검증이다.

## 2026-10-15 공개 데카트론 AI 부분 평가 연결 (#61)

- 프로필 설정 수용·공개 설정 파일·상품명 키워드 판정의 실패 재현 3개가 수정 전 실패했다. 수정 후 데카트론 AI/평가기 관련 **28 passed in 16.12s**, 전체 **282 passed in 107.54s**였다.
- 로컬 Playwright DOM에서 다른 적합 러닝화 2개는 이름·8만원 이하 가격으로 성공하고, 신발 종류가 다르거나 가격이 99,900원이면 실패했다. 이 판정은 표시 상품명·가격의 부분 범위에 한정된다.
- `python3 scripts/check_repo.py`, Python compileall, live study JSON 파싱, `git diff --check` 통과. 실제 OpenAI API 키를 사용할 수 없어 공개 사이트 AI 실행은 수행하지 않았다. 이전 브랜치의 공개 사이트 기록을 현재 단계별 Fast 구현의 실호출 결과로 간주하지 않는다.

## 2026-10-16 원본 PR 순차 통합 최종 준비본

- A/B/C/D 통합 전체 pytest **416 passed in 174.46s**. 실제 브라우저의 검토·초안·새로고침·네 형식 출력, Brain 기록 및 합성 데카트론의 일치/불일치·profile 전달을 포함한다.
- 원본 #60의 다른 상품 종류 거부를 단계별 가짜 제공자에서도 보존했다. #58의 perception·plan 문자열 명세 누락을 실패 재현 후 팀원 staged 수정으로 보완했다. 제공자/호출 비용/예산 집중 23개, 데카트론 집중 29개 통과.
- 최종 무료 Mock `20261015T220538-00787cd2`: `verified_success`, 독립 success, 6행동·기록 6/6, 58 mock 요청. 계획 검토 채택 0건은 알려진 실행 순서 문제이며 해결 또는 연구 효과로 표시하지 않는다.
- Doctor Python 3.13.13 / Playwright 1.55.0 Chromium / study_errors 없음. Node 구문·repo/staged·diff 검사 통과. 유료 API·실제 공개 사이트·사람 평가 재검증은 수행하지 않았다.
- 원격 필수 Ubuntu/Windows CI를 각 최신 PR head에서 다시 확인한 뒤 squash 병합한다. 이 로컬 통과로 CI·승인 상태를 대체하지 않는다. [병합 절차와 남은 제한](handoffs/2026-10-16-prototype-merge-queue.md).

## 2026-10-16 Wonder seed 정밀도 보완 후 최종 검사

- 실제 생성된 7930736020609184225와 2**63-1에서 Chromium 표시가 바뀌는 실패 2개를 재현했다. 원본 정수·JSONL·출력 계약과 난수 정책을 유지하고 검증 draw 순서의 `wonder_seed_texts` 문자열로 표시한다.
- 화면·JSON/CSV/Markdown/HTML·원본 로그 불변을 실제 HTTP/Chromium으로 검증했다. 기존 Brain 소비·안전 읽기 포함 15 passed in 5.50s.
- 보완 후 최종 A/B/C/D 전체 **418 passed in 175.90s**. 앞선 416개 검증은 이 표시 보완 전 기록이며 합산하지 않는다. Node 문법·repo/staged·diff 검사 통과.
- 실제 유료 API·기업·사람 평가를 완료한 결과가 아니다. 계획 검토 실제 입력 도달·종료 집계 문제는 여전히 후속이다.

## 2026-10-16 #74 Windows 검사 안정화

동일 head의 Windows 결과가 달라 두 실패 사례를 분리했다. 기본 로컬 집중 2개, 성찰 12회 반복과 실제 Windows 집중 12회×2개가 통과했다. 6초 지연 조건에서는 성찰 0건·판정 행 0개 실패를 재현했고, 조회 준비 및 테스트 초기화 조건 보완 후 동일 루프 2개가 17.12초에 통과했다. 기능 검증 조건을 제거하지 않았으며 테스트의 실제 decision 도달을 추가 확인한다. 실제 PR의 Ubuntu/Windows 전체 CI를 다시 실행한다. 디버그 계측·축소 workflow는 병합 준비본에 넣지 않는다.

- 준비 조건 보완 후 #74 범위의 전체 **377 passed in 159.10s**, 최종 A/B/C/D 통합 범위의 전체 **418 passed in 176.77s**였다. 전체 검증 범위를 줄이지 않았다.
- 두 운영체제 원격 검사는 최신 PR head와 최종 prototype에서 별도로 확인한다. 진단용 부분 검사와 로컬 통과 기록은 원격 필수 CI 통과를 대신하지 않는다.

## 2026-10-16 로컬 GPU Qwen 연결

- 사용자 로컬 SSH 터널의 `/health`가 HTTP 200과 `{"status":"ok","model":"persona-qwen"}`을 반환했다. `/v1/chat/completions`는 기본 요청과 `response_format=json_object` 요청 모두 HTTP 200, `choices[0].message.content`와 `usage`를 반환했다.
- 새 `gpu` 제공자 코드의 실제 짧은 요청은 `{"ok":true}`와 입력 24·출력 8토큰을 반환했다. 대시보드의 연결 확인 경로도 실제 서버에서 `configured=true`, `validated=true`를 반환했다. 이 결과는 채팅 연결 확인이며 전체 과업 성공이나 모델 품질 검증이 아니다. 호출 비용은 미확인이다.
- 새 제공자·설정 도우미·대시보드·모델 선택 집중 검사는 **65 passed, 1 deselected**였다. 선택 모델의 전체 runner 검사는 합성 fixture가 로컬 8000번 포트를 필요로 해 제외했다. Node 구문과 Python compileall 통과.
- 전체 pytest는 GPU 터널이 합성 fixture와 같은 로컬 8000번 포트를 점유한 상태에서 **407 passed, 15 failed**였다. 실패한 mock 실행은 합성 페이지 제목 대신 빈 제목을 관찰했고, 같은 환경의 `/health`는 GPU API를 반환했다. 포트 분리 후 전체 재검사는 남아 있다.

## 2026-10-16 대시보드 평가 프로필 경로 수정

- 실제 실행 `dashboard-321082b0c6`의 두 세션 모두 `runs/.dashboard/decathlon_live_profile.json` 파일 없음으로 실패했고, 생성된 임시 study에 `evaluation_profile_file: decathlon_live_profile.json`이 남아 있음을 확인했다.
- 대시보드 실행용 study에는 원본 `configs/study-decathlon-live.json` 위치를 기준으로 해석한 절대 평가 프로필 경로를 저장한다.
- 전용 회귀는 수정 전 실패하고 수정 후 통과했다. GPU 제공자·대시보드 MVP·모델 선택 인접 검사는 **19 passed, 1 deselected**였다. 제외한 1개는 현재 GPU 터널과 같은 8000번 포트를 요구하는 전체 runner 검사다.

## 2026-10-16 개별 실행 실패 후 batch 계속 진행

- 실제 GPU 실행 `20261016T083126-9ee286d9`는 6단계에서 Qwen의 잘못된 `finish` 필드 때문에 `model_output_error`로 종료됐고 독립 판정은 `unknown`이었다. 이 실행 오류와 batch 전체 상태를 구분한다.
- 가짜 runner로 두 페르소나가 연속 실패하는 조건에서 두 호출이 모두 수행되고 실패 2건과 로그가 보존되며 batch가 완료 상태를 반환하는 회귀를 추가했다.
- 완료된 batch의 실패 모달에서 실패 수, 페르소나 ID, `model_output_error` 로그를 확인하고 닫는 브라우저 회귀를 추가했다. batch 계속 실행과 모달의 신규 회귀 2개는 수정 전 실패하고 수정 후 통과했다. 대시보드 완료 상태 회귀를 포함한 관련 검사는 최종 **18 passed in 4.15s**였다.

## 2026-10-17 Qwen 적용 PR 준비 검증

- `feat/90-qwen-application`에서 기존 수정 17개와 신규 `tests/test_gpu_provider.py`를 함께 검토했다. GPU 연결·모델 전달·평가 프로필 경로·개별 오류를 포함한 batch 완료·실패 모달 회귀를 포함한다.
- 로컬 8000번 포트가 비어 있는 환경에서 `python3 -m pytest -q`: **426 passed in 206.72s**. 앞선 포트 충돌 상태의 407 passed / 15 failed와 구분한다. Python 3.14.5 / pytest 8.4.2 / Playwright 1.55.0 Chromium에서 실행했으며, Python 3.11에는 pytest와 런타임 의존성이 없어 해당 버전 로컬 검사는 수행하지 않았다. Ubuntu 3.11 / Windows 3.13 검증은 원격 CI 결과를 별도로 확인한다.
- `python3 -m uxagent doctor --study configs/study.json`: Chromium available, study_errors 없음. 첫 샌드박스 실행은 Chromium의 macOS Mach port 권한 제한으로 실패했고 브라우저 실행을 허용한 환경에서 재검사해 통과했다.
- `python3 -m uxagent run --study configs/study.json --provider mock --headless --output runs/qwen-pr-mock-2026-10-17`: `verified_success`, 독립 `success`, 6행동·기록 6/6·58 mock 요청. GPU나 실제 공개 사이트의 성공을 뜻하지 않는다.
- `python3 scripts/check_repo.py`는 0 problems, Python compileall·Node 구문 검사·`git diff --check`도 통과했다. push 전 staged 경로·민감정보 검사와 파일 목록을 다시 확인한다.
- 이번 검증에서는 실제 GPU/유료 API/공개 데카트론을 새로 호출하지 않았다. 2026-10-16의 짧은 실제 GPU 연결 성공 및 전체 과업의 `model_output_error`·독립 `unknown` 기록을 그대로 유지한다. GPU 임베딩과 비용은 미확인이다.

## 2026-10-17 #83 U Fast 판단 전환

- 브랜치 `feat/83-u-transition-01`, 선행 Qwen 커밋 `264bd985ce3bd1744d4e692af52efdc719e61b00`, U 기준 `4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd`. 구현 범위와 U 대비 차이는 [#83 작업 문서](tasks/83-u-fast.md)를 따른다. 이 기록은 prototype 병합이나 #84~#90 완료를 뜻하지 않는다.
- 새 U 회귀 8개는 구현 전 실패, 구현 후 통과했다. 첫 전체 검사는 **426 passed / 8 failed in 198.43s**였다. 기존 응답 형식/Slow 예약 정책의 fake와 Mock 내부 재호출 집계 문제를 확인했다. 같은 잘못된 종료·반복·선택 모델·독립 평가 상황을 U 응답으로 옮기고 Mock 내부 변환을 실제 요청과 분리한 뒤 집중 **42 passed in 13.75s**였다.
- 최종 제품 코드의 전체 `python3 -m pytest -q --tb=short`: **439 passed in 203.56s**. 이후 추가한 가짜 GPU HTTP 두 차례 통합 1개도 통과했다. 해당 추가 사례를 포함한 `tests/test_u_fast.py` 전체는 **14 passed in 2.68s**이며 13개는 앞선 전체 검사와 겹친다. 이를 전체 440개 일괄 실행 결과로 표현하지 않는다.
- 신규 회귀는 Event 기반 후속 feedback/perceive 동시 시작·같은 HTML·첫 feedback 금지, old_plan/next_step 질의·계획 rationale/Thought 순서, 빈/복수 actions, 빈 observations, 잘못된 plan/JSON의 실제 토큰 기록·예산, 동시 호출 실패/취소의 형제 정리, 일반 조건 persona 비노출, 미지원 행동 원본 보존을 확인했다. 실제 Chromium type+Enter 제출과 도구 실패 이전의 제안 기억 파일 존재도 확인했다.
- 가짜 GPU HTTP 통합은 실제 `LocalQwenProvider`의 HTTP 요청/응답 처리와 runner·Chromium을 사용했다. 두 차례 클릭과 한 차례 feedback, persona-qwen 모델 유지·U 제안 및 도구 결과를 확인했다. 실제 GPU 서버 응답이나 공개 사이트 성공 검증은 아니다.
- doctor: Python **3.14.5**, Playwright **1.55.0** Chromium available, study_errors 없음. 무료 Mock 통합은 `verified_success`, 독립 success, **6행동·기록 6/6·28 mock 요청**, perception/plan/decision 각 6회와 feedback 5회 완료였다. 기존 성공 시 조기 종료 평가 정책은 #89까지 유지한다.
- `pip wheel --no-deps --no-build-isolation --no-index --no-cache-dir`로 패키징했다. wheel 안의 U 프롬프트 4개가 고정 원문과 byte 단위로 같고, 격리 Python의 wheel import에서 리소스를 읽는 것을 확인했다. repo 검사 0 problems, Python compileall·Node 구문·diff 공백 검사 통과. push 전 staged 검사와 파일 목록을 재확인한다.
- 실제 로컬 GPU `/health`는 URLError로 응답을 얻지 못했다. 실제 GPU 채팅·공개 데카트론 과업은 실행하지 않았다. Qwen 문맥/출력 한도, 큰 페이지 인식 완전성, 실제 과업 성능은 미검증이다. 선행 #91의 원격 Ubuntu/Python 3.11·Windows/Python 3.13 CI는 성공했지만 #83 head의 원격 결과를 대신하지 않는다.

## 2026-10-17 #84 U Slow·Wonder 반복

- 브랜치 `feat/84-u-transition-02`, 선행 Fast `4e42109a94898fb772a7c214221115ce25b75d66`와 Qwen #91을 포함한다. [작업 문서](tasks/84-u-slow.md)의 범위이며 prototype 병합·#85~#90 완료와 구분한다. 환경은 Python 3.14.5 / pytest 8.4.2 / Playwright 1.55.0 Chromium이다.
- 신규 7개는 구현 전 실패했고 신규 회귀 전체 **11 passed**였다. Event로 두 번 이상 순환·Fast 병행·최근50개·64개 이후 cursor·빈 입력/출력·ID 제거 뒤 늦은 응답·두 run 분리·취소/JSON/예산 실패를 검증했다. 새/옛 Slow **21 passed, 1 deselected**, 관련 Fast/Slow/모델/기억 **87 passed in 21.18s**였다.
- 첫 전체 `python3 -m pytest -q --tb=short`: **448 passed / 3 failed in 208.54s**. 종료 시 아직 응답하지 않은 Slow 요청의 usage도 측정됐다고 기대하던 테스트를 실제 시도/반환 횟수·미확인 전체값·측정 부분합을 확인하도록 수정했다. 제품의 usage 집계 정책은 바꾸지 않았다. 관련 **26 passed in 12.61s**였다.
- 두 번째 전체: **450 passed / 1 failed in 202.73s**. 반복 상태 판정 전에 `Page.screenshot`이 30초 시간 초과로 browser_error를 반환했다. 같은 사례 단독 **1 passed in 3.45s**였다. 브라우저 정책이나 제한을 수정하지 않았다.
- 마지막 전체: **448 passed / 3 failed in 217.96s**. 대시보드 클릭 30초, Chromium launch 180초 시간 초과와 모델 호출 전 브라우저 관찰 실패가 발생했다. 실패한 `test_check_status_rows_keep_distinct_states_and_open_evidence`, `test_demo_states_keep_verification_termination_and_missing_evidence[failure-scenario_failed-checks2]`, `test_runner_comparison_persists_actual_usage[missing]`를 이어 재실행해 **3 passed in 14.70s**였다. **전체 일괄 통과는 확보하지 못했으며** Chromium 전체 검사 안정성을 PR의 남은 검증으로 명시한다. 부분 재실행을 전체 통과로 합산하지 않는다.
- doctor: Chromium available, study_errors 없음. Mock CLI 합성 통합은 verified_success / 독립 success, **6행동·기록 6/6·1,302 mock 요청**이었다. Slow worker 1개·623회 순환, 종료 후 active/pending 0·cancelled·reserved_tokens 0·embedding_status=not_configured였다. 응답 전 취소 1건의 토큰은 미확인이며 brain 상태는 incomplete로 보존됐다. Mock의 빠른 응답/반복/요청 수는 GPU 속도·비용 지표가 아니다.
- 로컬 wheel 빌드에서 U Slow 프롬프트 3개가 고정 원문과 byte 단위로 같고 격리 import에서 읽힘을 확인했다. repo 검사 0 problems, Python compileall·git diff 공백 검사 통과. push 전 staged 검사·파일 목록을 확인한다. 별도 lint/typecheck 설정은 없다.
- 실제 GPU 채팅·embedding·공개 데카트론은 이번 작업에서 호출하지 않았다. GPU embedding은 미지원이며 설정 없이는 importance만 갱신한다. urllib의 이미 시작된 원격 HTTP 강제 취소·실제 과금 중단은 보장하지 않는다. #91/#92의 Ubuntu/Windows CI 통과는 이 브랜치의 새 head CI 결과를 대신하지 않는다.

## 2026-10-17 #85 U 기억 검색 선행 구현 (진행 중)

- `feat/85-u-transition-03`에서 [작업 문서](tasks/85-u-memory.md)의 순수 검색 수식·최근 목록·query embedding 계측을 구현했다. 실제 embedding 경로와 64개 초과 제거 순서는 이슈에서 요구한 사용자 결정 대기 상태다. PR/전체 구현 완료가 아니다.
- 점수/최근 경계/중복/top20/미준비/차원 8개 구현 전 실패 → 통과. query 호출·사용량/검증 오류 2개도 구현 전 실패 → 통과. 취소와 run 캐시 분리 포함 신규 전체 **11 passed in 0.16s**. 관련 순수 회귀 **36 passed in 0.25s**였다.
- Chromium 통합 첫 검사 **31 passed / 1 failed in 11.75s**. 임베딩 미설정인데 예전 단어 검색의 Action 4개 이상 입력을 기대한 사례였다. U 최근 목록만 반환하는 조건으로 기대값을 바꾸되 입력 Action 존재·원본/점수/제거·출처 검증은 유지했다. 해당 메모리 통합+신규 검색 **14 passed in 6.63s**였다.
- repo 검사0 problems·compileall·diff 공백 검사 통과. 전체 pytest·doctor·Mock CLI·실제 embedding·새 head CI는 아직 실행하지 않았다. 실제 GPU/데카트론 호출도 수행하지 않았다. 남은 결정을 반영한 뒤 실행한다.

- 후속 사용자 결정: 64개 초과는 중요도 낮은 순·동점 오래된 seq 순. 종류/단계 보호를 제거하는 신규2개가 변경 전 실패 후 통과했다. 검색·제거·점수·Slow 관련 **39 passed in 0.20s**. 미산정 null은 제거 순서에만0으로 취급하고 원본 null을 유지한다. 원격 GPU 임베딩 사용 의사는 확인했지만 실제 서버/모델/포트는 확인 중이며 SSH 비밀번호를 앱에 저장하지 않는 연결 안내를 development에 추가했다.

## 2026-10-17 #85 추가 결정·대시보드 GPU 수명주기

- 사용자 결정: 중요도 낮은 순·동점 오래된 seq 순. 이후 미산정0 우선 제거 시 채점된64개 뒤 새 기억이 성찰 전에 사라지는 실패를 재현했고, 사용자가 채점 전 임시 최상위 보존을 확정했다. 신규 회귀는 변경 전 실패 후 통과했다. 앞선0점 순서 기록은 이 최종 결정을 뜻하지 않는다.
- 사용자 제공 srun 옵션과 서버 실행법에 맞춰 sbatch/SSH master/분리 임베딩/준비 검사/소유 작업 반환을 추가했다. 기존 Qwen 환경은 수정하지 않는다. 상세 계약과 최초 준비는 [GPU 수명주기](tasks/gpu-dashboard-lifecycle.md)에 있다.
- 수명주기10개와 분리 embedding7개, U memory14개가 신규이며 모듈/메서드 부재·정책 차이 실패를 먼저 확인했다. 신규·기존 Slow/제거/중요도 집중 **52 passed in 0.92s**였다. 사용자 최종 결정 이전의 통합+신규 관련 검사는 **57 passed in 9.30s**였다. 첫 전체는 **477 passed / 3 failed in 207.10s**로 기존 종류/단계 보호·Wonder 우선 제거 기대와 새 중요도 정책이 달랐다. 해당 회귀의 입력/원본 기록 보존·점수·상한 검증은 유지하고 새 기대값으로 갱신했다.
- 임베딩 HTTP 검사는 실제 로컬 HTTPServer/urllib 전송을 쓰되 encoder와 벡터는 가짜다. 별도 embedding transport가 채팅의 embed를 호출하지 않고 같은 예산에 반영됨을 확인했다. 실제 CUDA/한국어 모델 품질 검증이 아니다.
- 원격 SSH 읽기 전용 점검은 BatchMode/StrictHostKeyChecking으로 수행했고 Permission denied(publickey,password)로 종료됐다. Slurm 명령/서버/GPU에는 접근·변경하지 않았다. 실제 Slurm 할당·서버 설치·모델 다운로드·GPU API/반환·공개 데카트론은 미검증이다. 로컬 비공개 설정과 첫 실행 안내를 runs/private에 준비했으며 저장소에 포함하지 않는다.
- 최종 정책 반영 전체 `python3 -m pytest -q --tb=short`: **482 passed in 224.32s**. 이 전체 실행 도중 반환 직전의 squeue 작업ID·고유 이름 동시 대조를 보강했고, 해당 보강 이후 신규/Slow/제거/중요도 집중 **52 passed in 0.81s**였다. 새 커밋 전체 원격 CI 결과는 PR에서 별도로 확인한다.
- doctor: Python3.14.5 / Playwright1.55.0 Chromium available, study_errors 없음. Mock CLI 합성 통합: verified_success / 독립 success, **6행동·기록6/6·1,262 mock 요청**, 단일 Slow worker·603회 순환·종료후active/pending0·cancelled. 임베딩 미설정/not_configured 조건이며 실제 GPU 임베딩이나 성능 지표가 아니다. 종료 취소 usage는 미확인으로 보존한다.
- wheel 빌드 후 gpu_session.py/embeddings.py/embedding_server.py가 현재 파일과 byte 단위로 같고 격리 import에서 원격 helper 리소스를 읽는 것을 확인했다. 예시 설정으로 생성한 원격 job script의 bash -n 통과. repo 검사0 problems·Python compileall·diff 공백 검사 통과. 별도 lint/typecheck 설정은 없다. staged 검사와 실제 파일 목록을 push 전에 확인한다.

## 2026-10-18 실제 Qwen health·반환과 SSH 키 인증 후속

- 사용자 터미널에서 최초 login/compute 비밀번호를 입력해 시작한 Qwen-only smoke에 Codex가 실제 요청을 보냈다. localhost8001/health에서 HTTP200/status=ok/model=persona-qwen을 확인하고 작업19346의 squeue 소멸·반환, phase=finished/released=true, 복구 파일 삭제를 확인했다. 원자료는 runs/private에만 남겼다. 임베딩·생성 추론·키 인증을 검증한 것은 아니다.
- 신규 키 등록 모듈 부재 실패를 먼저 확인한 뒤 관련 **31 passed in 0.26s**였다. 기존 키/제한 옵션 보존·실패 시 비활성화·양쪽 새 인증·모델 없는 임시 할당을 확인했다. 격리 ssh-agent 소켓 검사는 첫 샌드박스 실행에서 막혀 허용 환경에서 재실행했다.
- 실제 agent 서명은 테스트용 임시 키와 새 agent로 검증하고 생성한 agent를 종료했다. 사용자 키·원격 authorized_keys·SSH 전역 설정은 변경하지 않았다. 사용자 실제 최초 등록은 터미널에서 gpu-key-setup 실행 후 확인해야 한다.

- 후속 전체 로컬 검사 **497 passed in207.93s**. 그 뒤 공개 키 추가 중 외부 프로세스의 동시 append를 덮어쓰는 실패를 재현해 O_APPEND로 수정했다. 수정 후 관련 **32 passed in0.28s**이며, 이 마지막 변경을 포함한 전체 결과는 새 head CI에서 확인한다.
- doctor: Python3.14.5/Playwright1.55.0 Chromium available·study_errors 없음. Mock CLI는 verified_success/독립 success,6행동·기록6/6·1,238 mock 요청이었다. 실제 GPU 추론·임베딩 결과가 아니다.
- 최종 wheel 빌드·새 모듈 byte 비교·격리 import와 inspect 기반 원격 공개 키 설치 코드 생성, repo0 problems·compileall·diff 검사를 확인했다. 사용자 실제 키 등록과 무인 원격 시작 검증은 사용자 터미널의 최초 설정 완료 후 수행한다.


## 2026-10-18 macOS 저장 비밀번호 자동 인증

- 사용자 후속 결정에 따라 서버 비밀번호를 OS 키체인에 한 번 저장하고 이후 SSH에 자동 전달하는 경로를 추가했다. 신규 모듈 부재 실패 후 기존 키/GPU 경로와 관련 **36 passed in0.26s**.
- 실제 macOS Security.framework로 임시 테스트 자격증명 생성/조회/갱신, 생성된 askpass 실행 파일의 실제 pipe 전달과 host 확인 prompt 거부를 확인했다. 테스트용 키체인 항목을 삭제했다. 사용자 비밀번호/기존 키체인 항목은 읽거나 변경하지 않았다.
- 사용자가 자기 터미널에서 최초 저장한 뒤, Codex가 비대화형으로 Qwen-only smoke를 실행했다. 추가 비밀번호 입력 없이 실제 localhost8001/health HTTP200/status=ok/model=persona-qwen, Slurm 작업19347의 squeue 소멸·released=true·복구 파일 삭제를 확인했다. 앞선 수동 비밀번호 smoke와 구분하며 embedding·생성 추론은 호출하지 않았다. 증거/실제 설정은 runs/private에만 둔다.

- 확인 입력 불일치 회귀 보강 후 관련 **37 passed in0.38s**, repo0 problems·compileall·diff 검사·CLI help 통과. 최종 wheel의 gpu_passwords.py/gpu_session.py/cli.py byte 비교를 통과했다.

- 로컬 전체 **502 passed in209.58s**. 이후 확인 값 불일치·키 방식 명시 전환 회귀를 보강했다. 비밀번호 저장 상태에서 gpu-key-setup을 완료해도 이전 저장 방식이 남는 실패를 재현해 성공 시 선택 모드를 해제했다. 최종 head 전체는 원격 CI에서 확인한다. 임시 agent 검사는 기본 sandbox에서 소켓 생성이 차단되므로 허용 환경 결과와 구분한다.

- 최종 관련 **38 passed in0.46s**. 자동 승인 검토 시간 초과로 한 차례 실행이 취소되어 재시도했고, 실제 코드 수정과 임시 agent 허용 환경 검사 이후 통과를 확인했다.

## 2026-10-18 #88 질문지·전체 trace 사후 설문

- `python3 -m pytest -q` **528 passed in 265.57s**. 설문·보안·setup-guide·공통 budget·review 회귀 집중 검사는 **100 passed in 15.72s**였다. 첫 sandbox 기본 실행은 local HTTP bind/Chromium 권한 제한으로 실패했고, 승인된 로컬 테스트 실행에서 통과했다.
- 회귀는 질문지+newline+전체 기억 trace payload, eviction 후 기억과 최신 importance 복원, 질문/답 순서와 객관식 검증, raw invalid JSON 보존, 민감정보 차단, 예산 초과 시 무호출, batch가 모든 브라우저 세션을 끝낸 뒤 설문하며 한 건 실패 후 계속함을 확인했다. 기존 독립 verification 결과는 유지한다.
- `python3 -m compileall -q src/uxagent`, `python3 scripts/check_repo.py` (0 problems), `git diff --check` 통과. 실제 GPU Qwen 설문 요청·Decathlon 사용자 과업·모델 응답 품질은 실행하지 않았다. Qwen의 실제 context 한도와 긴 trace 처리 결과는 미검증이다.
- 사용자 결정으로 설문에 전체 append-only trace를 사용한다. 검색 활성 메모리 64개 상한은 유지한다. 결과는 `simulated_self_report`다. 작업 계약과 실행 경로는 [#88 작업 문서](tasks/88-u-survey.md)에 있다.

## 2026-10-18 #86 U DOM parser 관찰

- `python3 -m pytest -q` 최종 전체 검사 **510 passed in 254.96s**. Chromium 실행에는 macOS sandbox에서 Mach rendezvous가 막혀 승인된 로컬 실행이 필요했다. 관련 관찰·action·runner·fake Qwen 회귀는 수정 후 **55 passed in 39.84s**였다.
- 신규 browser 회귀는 빈 input/contenteditable, current select value/option, 한글·중복 이름 ID, 페이지 아래 scrollable 대상, hidden 제거, parser 재실행, 원본 DOM locator, password value redaction, network timeout, hover listener/fetch tracking을 포함한다. Network가 끝나지 않으면 기다림을 제한하고 관찰에 `observation_wait_timeout`을 기록한다.
- `python3 -m compileall -q src`, Node `--check` 두 parser 리소스, `git diff --check` 통과. wheel 검사에서 `uxagent/parser/parser.js`, `uxagent/parser/initscript.js` 포함을 확인했다.
- 공개 Decathlon 검색 URL은 HTTP200이었다. 관찰은 검색 입력 1, clickable 52, select 0, semantic ID 275개·정리 HTML 99,328자로 구성됐으며 검색·상품·필터 후보와 처음 5개 locator가 확인됐다. 페이지의 XHR/fetch가 3초 안에 idle하지 않아 `observation_wait_timeout`이 같이 기록됐다. 상품 과업이나 구매 행동은 하지 않았다.
- 공개 페이지의 99,328자는 기존 권고 한도 12,000자를 넘는다. 관찰은 조용히 자르지 않고 초과 사실을 `CaptureInfo.limits_exceeded`와 측정 크기에 기록한다. Qwen 실제 생성 요청에서 이 크기가 처리되는지는 미검증이며 페이지/모델 한도 오류 가능성이 남는다. 실시간 관찰은 저장하지 않았다.

## 2026-10-18 #89 탐색 종료와 사후 독립 평가

- 변경 전 재현: 중간 evaluator success가 첫 행동 뒤 run을 `verified_success`로 종료했고, 종료 후 전용 final record가 없었다. 신규 mock/browser 회귀는 변경 전 2개 실패로 이를 확인했다.
- 관련 runner·Decathlon·evaluator·memory·comparison·usage·metrics/core 집중 검사는 **73 passed in 136.28s**였다. 추가 final capture/evaluator failure 및 comparison provenance 회귀는 **17 passed in 26.57s**였다.
- 전체 `python3 -m pytest -q`: **529 passed, 1 failed in 379.89s**. 실패는 예산 종료 시 verification도 `unknown`이어야 한다는 기존 테스트 기대였다. 별도 최종 evaluator가 해당 fixture 화면을 `failure`로 판정하므로 기대를 갱신한 뒤 문제 테스트는 **1 passed in 2.18s**였다. 기대 갱신 후 전체 suite는 다시 실행하지 않았다.
- `python3 -m compileall -q src/uxagent`, `python3 scripts/check_repo.py` (0 problems), `git diff --check` 통과. 실제 GPU Qwen 추론과 Decathlon 브라우저 과업은 실행하지 않았다. 라이브 상품 상태와 실제 모델 종료 행동/최종 성공률은 미검증이다.
- 확인 범위: 중간 success 뒤 탐색 지속, 종료 뒤 Slow close 및 최종 capture 다음 evaluator 1회, final capture/evaluator exception의 unknown 처리, timeout/cancel/기존 browser error 사유 유지, 종료/최종 관찰/evaluator provenance를 비교 기록에 전달한다. 공개 Decathlon 평가기는 기존 상품명·80,000원 상세 프로필만 사용한다.
- 전체 suite 뒤 shutdown 실패 회귀를 추가한 집중 runner/comparison 재검사 **10 passed in 16.06s**. 그 후 전체 suite는 재실행하지 않았다.

## 2026-10-18 #90 U 계약·로그·출력 통합

- 회귀는 호출 원문 근거가 없고 dashboard detail에서 run-local log 경계를 검증하지 않는 상태로 시작했다. 새 회귀는 method/time/request/response/retrieve_result, secret 감지 시 원문 제거, API raw-call 숨김, final evaluation detail/JSON/CSV 연결, U `feedback` trace 출력을 검사한다.
- 구현 중 새 feedback fixture로 인해 legacy 오염행 검사 기대 개수가 달라졌고 시간 필드 이름 변경 테스트도 갱신이 필요했다. 잘못된 cross-run·손상 행·symlink 경고 확인은 유지한 채 새 feedback 항목과 `recorded_at`으로 수정했다.
- 통합 집중 실행: `python3 -m pytest -q tests/test_call_evidence.py tests/test_u_fast.py tests/test_slow_loop.py tests/test_survey.py tests/test_brain_schema.py tests/test_brain_trace.py tests/test_loop_record_consumers.py tests/test_reports.py tests/test_latest_brain_integration.py tests/test_runner_flow.py tests/test_memory_integration.py` → **71 passed in 73.04s**.
- 전체 실행: 승인된 로컬 브라우저/fixture-server 환경의 `python3 -m pytest -q` → **534 passed in 381.75s**. 전체 실행 중 final-evaluation 근거가 Brain 파일 없는 단순 run에서도 출력되도록 보완했다. Markdown/HTML에도 최종 provenance section을 추가하고 legacy null 회귀를 포함한 최종 수정 뒤 `tests/test_call_evidence.py`, `test_brain_trace.py`, `test_reports.py`, `test_loop_record_consumers.py` 재검사 → **12 passed in 0.20s**.
- `python3 -m compileall -q src/uxagent`, `python3 scripts/check_repo.py` (0 problems), `git diff --check` 통과. 이 환경에는 별도 lint/typecheck 설정이 없다. 최초 sandbox 실행은 로컬 포트/Chromium 권한 때문에 실행 환경 오류가 났으며 허용 환경에서 통과했다.
- 검증한 흐름은 fake provider/Qwen fake HTTP + 기존 local fixture다. 실제 GPU Qwen 생성·공개 Decathlon 브라우저 과업 및 원격 Ubuntu/Windows CI는 이 변경에서 실행하지 않았다. 사용자에게 성공으로 표시하지 않는다. 개인 `runs/` 자료와 `.env`는 stage하지 않는다.

## 2026-10-18 실제 Qwen 큰 화면 입력 회귀

- 공개 데카트론 p001~p005의 기록은 모두 첫 Fast perception에서 `provider_http_400: Prompt too long`이었다. 첫 실행의 HTML 125,629자, 원본 첫 요청 131,683자, semantic ID 속성 약 96,000자를 측정했다. 모델용 텍스트·대상 표현은 5,493자이며 원본 observation 파일은 수정하지 않았다.
- 실제 로컬 SSH 터널의 `persona-qwen`에 같은 첫 화면을 재요청해 perception 응답 1개, 후속 plan, action 제안 1개를 확인했다. 사용한 모델은 바꾸지 않았다. 서버가 긴 U perception 응답을 512 출력토큰에서 끊는 것도 실제 응답 `finish_reason=length`와 usage로 확인했다.
- 합성 회귀는 큰 화면에서 짧은 ID를 실제 action ID로 복원하고 원본 HTML을 유지하는지 확인한다. 실제 사이트에서 클릭·검색·최종 과업 성공까지는 이 재요청에서 확인하지 않았다.
- 이후 같은 첫 화면과 p001 설정으로 `max_steps=1` 실제 브라우저 실행을 추가했다. `runs/private/gpu-prompt-fix-smoke/20261018T150241-12167c41`에서 Fast perception·plan·decision 오류 0건, 행동 시도 1건/성공 1건을 확인했다. `termination_reason=max_steps`, 독립 판정 `unknown`이며 전체 상품 과업의 성공은 확인하지 않았다. 비공개 재현 설정·원본 run은 `runs/private/`와 `runs/`에만 두었다.
- 같은 화면을 2단계로 실행한 결과, 인위적인 모델 호출 제한 20회는 Slow 중요도 채점 11회에 소진돼 두 번째 계획 전에 `budget_exceeded`로 끝났다. 운영 설정처럼 이 제한을 제거한 재실행 `20261018T150806-3b20fac4`에서는 Fast의 후속 feedback·perception·plan·decision까지 완료되고 행동 시도·성공이 각각 2건이었다. 첫 perception의 JSON 형식 오류는 1회 복구됐고 `Prompt too long`은 없었다. Slow 30회를 포함한 모델 요청은 41회였으며 종료 사유는 `max_steps`, 독립 판정은 `unknown`이다. 전체 과업 완료·상품 조건 충족 여부는 검증하지 않았다.
- 승인된 로컬 브라우저/소켓 환경의 전체 `python3 -m pytest -q`: **535 passed in 381.73s**. 마지막 Qwen 큰 화면 분기 기준을 8,000자로 조정한 뒤 비브라우저 Fast 집중 검사 **13 passed, 2 deselected**. `python3 -m compileall -q src/uxagent`, `python3 scripts/check_repo.py` (0 problems), `git diff --check` 통과. 2개 제외 테스트는 기준 변경 뒤 재실행하지 않았지만 전체 검사에서 통과했다.

## 2026-10-19 Qwen 큰 화면 단계별 관찰

- 단일 180자 큰 화면 관찰 대신 원본 HTML에서 내부 parser 속성만 뺀 입력을 1,400자 이하로 나눠 순차 관찰하고, 결과를 다시 합쳐 한 결과가 될 때까지 반복한다. 첫 단계의 모든 조각과 합치기 단계가 호출 로그로 재구성 가능하다. 원본 observation과 행동의 semantic ID 복원은 유지한다.
- 저장된 실제 데카트론 첫 관찰 `obs-9b39bbe88e`의 HTML 120,094자는 내부 parser 속성을 빼면 8,549자이며 1차에서 7개 조각으로 나뉜다. 이는 로컬 입력 계산이며 실제 Qwen 호출 결과는 아니다.
- 회귀 테스트는 수정 전 실패를 확인한 뒤, 다중 조각·모든 원본 표식 포함·2차 합치기·원래 행동 ID 복원을 확인했다. 처음 sandbox 내 비브라우저 Fast 검사는 **14 passed, 2 deselected**였고 macOS 브라우저/소켓 접근을 허용한 Fast 전체 검사는 최종 코드에서 **16 passed**였다.
- 현재 로컬 8001 GPU 포트는 연결되지 않아 실제 Qwen 다단계 응답, 누락 정도, 공개 데카트론 전체 과업 성공은 확인하지 않았다. 반복 요약은 정보의 완전 보존을 보장하지 않는다.
- 최종 코드의 전체 `python3 -m pytest -q`: **536 passed in 390.11s** (승인된 로컬 브라우저/소켓 환경). `python3 -m compileall -q src/uxagent`, `python3 scripts/check_repo.py` (0 problems), `git diff --check`도 통과했다. 실행 중인 GPU 서버에 대한 라이브 생성 호출은 포함하지 않았다.

## 2026-10-19 Qwen 다중 관찰·대기 제거 후속

- 공개 데카트론 p001~p005 실패 로그를 확인했다. 다섯 건 모두 1차 첫 조각의 `observations`가 비어 있지 않은 5개였고, 기존 정확히 1개 검사에서 중단됐다. 첫 모델 호출은 약 5.4초, 첫 화면 준비는 약 4~5초였다. 두 단계의 과거 실행에서는 행동 후 저장 화면과 다음 관찰 사이에 약 0.4초가 들었다.
- 여러 관찰을 순서대로 결합하고, 조각 결과가 입력 한도 안에 모이면 마지막 합치기 모델 요청을 생략한다. 행동 직후 관찰을 다음 단계에서 재사용하고 최종 독립 평가용 화면은 새로 찍는다. 실제 Qwen 조각 응답에서 완전한 JSON 뒤에 백틱 하나가 붙는 사례를 확인해, 해당 경우만 로컬에서 읽는다. 원본 응답 근거는 유지한다.
- 새 회귀 테스트는 수정 전 다중 관찰·중복 관찰 ID·후행 백틱에서 실패했고 수정 후 통과했다. Fast·runner·관찰·행동 집중 검사 **67 passed in 43.45s**, 백틱 변경 뒤 Fast·runner·호출 근거 검사 **30 passed in 19.72s**. 백틱 변경 전 전체 `python3 -m pytest -q`는 **537 passed in 364.71s**였다. 최종 변경 뒤 `compileall`, 저장소 검사(문제 0개), `git diff --check`도 통과했다.
- 만료된 GPU 작업19369가 실제 Slurm에서 사라진 것을 ID/이름으로 확인하고 복구 상태를 정리한 뒤 새 대시보드 작업19370을 시작했다. 대시보드/채팅/임베딩 health는 모두 HTTP200, 모델은 `persona-qwen`, 임베딩은 CUDA였다.
- 원본 실패 화면을 수정된 Qwen 인식에 다시 전달해 단일 최종 관찰 생성에 성공했다. 1,400자 조각은 실제 완료됐지만 형식 복구가 1~2회 필요한 실행이 있어 총 8~9회, 약 43~44초였다. 2,800자 조각은 실제 JSON 복구 후에도 실패했고, 2,000자 조각은 7회/약44초로 빨라지지 않아 1,400자 기준을 유지했다.
- 비공개 한 단계 실사이트 run `runs/private/gpu-chunk-fix-smoke/20261019T050611-86578b80`은 Fast perception 9회(형식 복구2회), plan 1회, decision 1회, Slow 2회였다. 행동 시도/성공은 1/1, 종료는 `max_steps`, 독립 판정은 `unknown`이다. CLI 종료 코드1은 이 미확인 판정 때문이다. 전체 데카트론 과업 성공·응답의 세부 문구 완전성은 확인하지 않았다. 이 run은 후행 백틱 로컬 처리 전이며 그 변경 뒤에는 원본 실패 화면의 perception만 다시 검증했다.

## 2026-10-19 Qwen 인식 입력의 규칙 기반 압축

- 새 동작은 큰 Qwen 화면에서 기존 U 관찰 원본을 저장하고, 모델 입력에만 텍스트·이미지 alt/title·조작 대상 이름/값·짧은 ID를 사용한다. `article`/`li`/`section`/`tr` 단위를 줄바꿈으로 구분한다. 작은 화면·다른 제공자·feedback/decision 입력은 바꾸지 않는다.
- 최근 실사이트 run `20261019T051634-9150e253`은 `model_output_error` 두 건이 각각 JSON 구문 오류였고 복구 호출로 통과했다. 첫 행동 1/1 성공 후 두 번째 행동은 없었다. Slow importance 25건과 Fast 인식이 같은 GPU에서 겹쳤으며 호출 시간이 계단식으로 길어져 경합이 강하게 의심된다. 원격 대기열은 직접 계측하지 않았다. 최종 `run_timeout`은 300.7초/독립 판정 `unknown`이다. 대시보드의 1.5초 상태 폴링은 실제 브라우저 행동이 아니다.
- 저장된 이 run의 첫 화면에서 이전 parser 속성 제거 입력 8,876자·첫 단계 7조각과 새 규칙 입력 5,901자·5조각을 오프라인 계산으로 비교했다. 저장 화면 3개의 원본 HTML 텍스트 노드 139~149개 중 새 입력에서 누락된 문구는 0개였다. 이는 입력 보존 검사이며 모델 요약의 무손실 보장은 아니다. 인식·runner·호출 근거·관찰 집중 검사 **37 passed in 24.00s**, 최종 전체 `python3 -m pytest -q`는 **539 passed in 355.99s**. `compileall`, 저장소 검사(문제 0개), `git diff --check`도 통과했다. 조각 수는 호출 전 계산값이고 실제 모델 호출 수·벽시계 시간의 실측 결과는 아니다. 새 GPU 호출은 하지 않았으며 Slow GPU 경합·JSON 오류 감소는 미검증이다.

## 2026-10-19 Qwen 조각 JSON 닫는 괄호 교정

- 공개 데카트론 실행 `20261019T060505-f45a5550`은 첫 perception 조각에서 종료됐다. 원본 두 응답 모두 마지막을 `"}]`로 뒤집었고, 두 번째는 모델의 복구 요청에 대한 응답이었다. 각 응답의 output_tokens는 180이었다. 브라우저 행동 시도는 없었다.
- 정확한 오류를 재현하는 회귀 테스트를 먼저 작성해 수정 전 실패를 확인했다. GPU 조각 응답에 한해서만 후행 백틱을 제거하고, `observations` 배열의 마지막 `"}]`를 `"]}`로 바꾼 JSON을 다시 파싱·UPerception 검증한다. 원본 호출 응답은 그대로 저장한다. 다른 문법 오류를 교정으로 오인하지 않는 테스트도 추가했다.
- 저장된 실제 실패 응답 2개는 모두 수정된 파서와 UPerception 검증을 통과했다. 관련 `tests/test_u_fast.py`는 승인된 브라우저/소켓 환경에서 **21 passed**였다. 최초 제한 환경의 2개 실패는 Playwright/HTTP 서버 소켓 권한 거부였고, 허용 환경에서 통과했다.
- 실행 중인 실제 GPU Qwen에 저장된 실패 조각 하나를 새 프롬프트로 요청했다. 원본 응답은 다시 JSON 닫는 괄호 역순이었지만, 모델 재호출 없이 **한 호출로 유효한 관찰**을 얻었다. 이는 첫 조각의 형식 검증이며 전체 페이지 인식·행동·과업 성공을 뜻하지 않는다.
- 최종 전체 `python3 -m pytest -q`는 승인된 로컬 브라우저/소켓 환경에서 **541 passed in 363.05s**였다. `python3 -m compileall -q src/uxagent`, `python3 scripts/check_repo.py` (0 problems), `git diff --check`도 통과했다.

## 2026-10-19 대시보드 시간 초과와 취소 호출 분석

- 최근 실행 `20261019T061831-7c48b172`는 300.454초에 `run_timeout`으로 끝났다. 행동 2건은 모두 실행 성공했고, 3단계는 모델 판단 중 시간 초과였다. 1단계 판단 50.931초, 2단계 판단 215.843초였다. 중요도 요청 34건 중 27건 완료·7건 취소, Fast feedback/perception 각 1건도 종료 시 취소됐다. perception JSON 오류 1건은 복구됐고 실행 종료 원인이 아니었다. 취소된 호출의 토큰·비용은 서버 응답이 없어 미확인이다.
- GPU 중요도 요청을 한 번에 하나로 제한하는 테스트와, 시간 초과 취소를 대시보드에서 구분해 표시하는 테스트는 변경 전 실패·변경 후 통과했다. 관련 Slow/대시보드 집중 검사 **13 passed**였다. 최종 전체 `python3 -m pytest -q`는 허용된 브라우저/소켓 환경에서 **543 passed in 403.64s**. `compileall`, `node --check`, 저장소 검사(0 problems), `git diff --check`도 통과했다.
- 원격 Qwen 서버 내부 대기열은 계측하지 않았고 변경 후 전체 데카트론 실행 시간·과업 성공은 다시 측정하지 않았다. 기존 대시보드와 GPU는 계속 실행 중이다.

## 2026-10-19 Qwen 관찰 배열 닫는 괄호 누락

- 공개 데카트론 실행 `20261019T142709-2db00a5b`은 첫 화면의 perception 4회 중 세 번째 조각과 복구 요청에서 모두 배열 `]`를 빠뜨린 응답을 받았다. 두 응답은 각각 122·121 출력 토큰이며, 실행은 1단계 `model_error`로 끝나 행동 시도는 없었다.
- 새 접미부 회귀 테스트는 수정 전 실패, 후 통과했다. 기존 역순·후행 백틱 사례와 내부 문법 오류 거부를 함께 확인했다. 저장된 해당 실행의 원본 응답 4개를 새 파서로 재검증한 결과 모두 JSON 및 UPerception 계약을 통과했다. 전체 사이트 과업의 실제 재실행 결과는 아직 없다.
- 변경 후 `python3 -m pytest -q tests/test_u_fast.py tests/test_runner_flow.py`는 허용된 브라우저/소켓 환경에서 **31 passed in 21.48s**. `compileall`, 저장소 검사(0 problems), `git diff --check`도 통과했다. 이번 접미부 변경 뒤 전체 테스트 묶음은 다시 실행하지 않았다.

## 2026-10-20 데카트론 사이트 검색 경로

- 최근 실행 `20261019T151741-cd0f0954`에서는 첫 계획이 `러닝` 메뉴 클릭이었고 이후 메뉴를 반복 클릭해 300초 시간 초과로 끝났다. 저장된 첫 관찰의 유일한 입력은 검색창이지만 이름이 판촉 placeholder로 기록됐다.
- U 원본은 검색을 별도 행동으로 정의하지 않고 입력 `type`과 선택적 Enter를 사용한다. 우리 코드에는 U의 `valid_targets.inputs/selects`가 clickable을 재사용하는 결함도 남아 있었다. 실제 데카트론 DOM의 검색 입력은 `data-cy="search-bar-desktop"` 컨테이너 안에 있음을 확인했다.
- 수정 전 회귀 2건이 실패했고 수정 후 관련 Fast/DOM **29 passed in 16.34s**였다. 실제 DOM 관찰은 첫 화면의 “상품 검색” 입력과 검색어 입력 뒤의 “다음에 대한 모든 결과 보기” 링크를 모두 찾았다.
- 공개 데카트론에서 실제 `ActionExecutor`로 검색창 클릭 → `러닝화` 입력(`enter=False`) → “모든 결과 보기” 클릭을 실행했다. 세 행동 모두 `ok=True`였고 최종 URL이 `/search?query=러닝화`로 이동했다. 입력에 Enter를 붙이거나 검색창을 먼저 클릭하지 않으면 이 링크가 다음 관찰에 나타나지 않는 것도 확인했다. 이는 UI 경로 검증이며 Qwen이 같은 세 행동을 자율 선택했다는 증거는 아니다.
- 최종 전체 `python3 -m pytest -q`: **545 passed in 379.63s**. `python3 -m compileall -q src/uxagent`, `node --check src/uxagent/parser/parser.js`, `python3 scripts/check_repo.py`(0 problems), `git diff --check` 통과. GPU Qwen health는 로컬 8001번에 연결되지 않아 자율 과업 재실행은 수행하지 않았다. 메뉴의 앞뒤 계층 문맥 제공은 이번 검색 수정 범위 밖에 있다.

## 2026-10-20 검색 선택 자율화와 메뉴 계층 문맥 후속

- 사용자 결정에 따라 계획의 검색 우선 지시와 `available_search_inputs` 필드를 제거했다. 데카트론 검색 입력의 “상품 검색” 표시, 실제 input/select 대상 목록, 검색을 선택한 경우의 3단계 행동 안내는 유지했다. 페르소나 JSON은 기존처럼 계획·행동 요청에 전달되며 검색 또는 메뉴를 고르는 규칙은 강제하지 않는다.
- 저장된 데카트론 관찰에서 큰 GPU 화면의 평문/컨트롤 나열에는 두 “러닝화”의 소속이 드러나지 않았다. 수정 후 `<navigation>`에 `러닝 > 러닝화`와 `러닝 > 남성 > 러닝화`를 서로 다른 짧은 ID로 표시한다. 실제 3열 화면에서는 `러닝 > 남성 > 러닝화 > 로드러닝/조깅`과 이웃 `트레일러닝`을 포함한 모델 입력을 확인했다. 원본 observation JSON·semantic ID는 보존한다.
- 메뉴 회귀 테스트는 첫 구현에서 세 번째 열의 `남성`이 누락돼 실패했고, 보이는 열의 순서를 사용한 수정 후 통과했다. 관련 `tests/test_u_fast.py tests/test_u_observation.py tests/test_runner_flow.py`는 최종 header 범위 parser 최적화까지 반영해 **39 passed in 25.33s**였다. 전체 `python3 -m pytest -q`는 **546 passed in 423.40s**였다. 전체 검사는 parser 최적화 직전에 시작됐으므로 최종 코드의 직접 검증은 뒤이은 관련 39건이다.
- 실제 공개 데카트론에서 앱 `ActionExecutor`로 `러닝 → 남성 → 러닝화 → 로드러닝/조깅`을 순서대로 클릭했고 네 행동 모두 `ok=True`, 최종 카테고리 URL은 `/c/러닝/남성/러닝화/로드러닝-조깅.html`이었다. 이 검사는 고정 행동 경로이며 Qwen이 페르소나에 따라 이 경로를 자율 선택했다는 증거는 아니다. 로컬 GPU health 포트 8000/8001이 연결되지 않아 실제 Qwen 요청은 수행하지 않았다.
- `python3 -m compileall -q src/uxagent`, `node --check src/uxagent/parser/parser.js`, `python3 scripts/check_repo.py`(0 problems), `git diff --check` 통과. 이번 후속 작업에서는 커밋·PR을 만들지 않았다.

## 2026-10-21 상호작용 흐름 후속 검증

- 검색 후속 판단/입력/제출, 텍스트·이미지 팝업 요청 범위와 modal 처리, 페이지/내부 영역 스크롤, Brain 이벤트, 기존 프롬프트/runner 회귀에 대해 집중 검사를 수행했다. 수정 중 발견한 브라우저 테스트의 페이지 스크롤 후 사라진 패널 기대, completed 이벤트의 reason_code 계약 위반을 고친 뒤 `tests/test_interaction_flows.py`, `test_u_observation.py`, `test_target_selection.py`, `test_u_fast.py`, `test_runner_flow.py`, `test_prompt_guard.py`를 포함한 집중 실행은 최종 일부 테스트 기대 수정 전 **101 passed, 1 failed**였고, 마지막 Jev 텍스트 입력 경로 테스트를 수정 뒤 따로 재실행해 **1 passed**했다. 앞선 최종 핵심 묶음은 **69 passed**였다.
- 전체 `python3 -m pytest -q`는 **602 passed, 7 failed in 344.48s**였다. 실패는 대부분 변경된 계약과 어긋난 기존 테스트 fixture/기대였다(immutable FastLoop 더블, 상호작용 삽입으로 비연속이 된 timestamp, 방향키 스크롤 기대, 타깃 스크롤 거부, 빈 텍스트 입력에서 Jev 후보 선택 기대, 검색 흐름을 고려하지 않은 반복 provider). 기존 검증을 약화하지 않고 현재 동작에 맞게 해당 fixture/기대를 갱신했다. 전체 suite는 갱신 뒤 다시 실행하지 않았다. 갱신된 영향 테스트 묶음은 101개 통과 및 남은 Jev 검사 단독 통과로 확인했다.
- `python3 -m compileall -q src/uxagent` 통과. 전체 suite의 브라우저 검사는 승인된 로컬 Chromium/fixture 환경에서 실행했다. 실제 GPU Qwen, Decathlon 사용자 과업, 이미지 모델 API는 호출하지 않았고 사진 전용 API도 구성되어 있지 않다.
- 후속 검증 항목과 사진 경로의 제한은 [상호작용 흐름 작업 문서](tasks/interaction-flows.md)를 따른다.

## 2026-10-21 UActions 수정 요청 템플릿

- 최근 실제 run `20261021T101841-9331cd9b`를 확인했다. Qwen 첫 decision 응답의 `enter=false`는 JSON 문법 오류였고 수정 응답에서는 `enter:false`로 고쳤지만 필수 `description`은 빠져 있었다. `action_attempts=0`이며 action/result가 null이어서 실패는 Playwright 실행 전에 발생했다.
- 재요청 메시지에 기대 JSON 템플릿을 넣도록 바꿨다. `response_model` JSON Schema의 필수 구조를 빈 템플릿으로 만들고, 기존 JSON을 읽을 수 있으면 유효한 action 선택·대상·텍스트·옵션을 유지한 채 빠진 필수 필드만 빈칸으로 남긴다. 수정 후에도 검증되지 않으면 기존처럼 한 번 뒤 중단한다. 원본·수정 응답과 usage 호출 로그는 기존처럼 각각 보존한다.
- 최소 회귀는 누락 description 응답과 원 실행의 잘못된 `enter=false` JSON을 재현한다. 파싱 가능할 때 기존 action/type/target/text/enter를 유지한 빈 description을 만들고, 파싱 불가일 때 required schema 템플릿을 제시하며 원본 응답이 대화에 남는지 확인한다. `python3 -m pytest -q tests/test_u_fast.py tests/test_prompt_guard.py tests/test_target_selection.py`: **46 passed in 4.64s** (Chromium/fake HTTP 실행 포함). 실제 Qwen 요청, 실제 검색어 입력, 전체 pytest는 실행하지 않았다.
- `python3 -m compileall -q src/uxagent`, `python3 scripts/check_repo.py` (**0 problems**) 및 `git diff --check` 통과.

## 2026-10-21 검색 제출 포커스와 결과 판정

- 실제 run `20261021T112804-6b33bb9d`에서 `type(러닝화, enter=false)` 뒤 다음 모델 판단에 약64초가 걸렸다. 다음 `key_press(Enter)`는 target_id가 없었고 실행 결과는 `ok=true`였으나 URL은 그대로였다. 이어 모델은 검색 결과가 아니라 `모든 스포츠` 링크를 눌렀고 세 번째 행동 뒤 JSON 제어 문자 오류로 종료됐다. 포커스는 Enter 전 관찰에서는 true였지만 키 전달 시점 값은 기록되지 않아 정확한 키 도달 위치는 확정할 수 없다.
- 검색 상호작용에서 선택된 query를 `type+Enter` 하나로 같은 input locator에 보낸다. 일반 모델이 먼저 type만 제안한 경로도 다음 Enter를 동일 input에 포커스해 보낸다. 관찰 스크립트는 main 결과 영역·검색 제안 영역 fingerprint와 로딩 표시를 기록한다. URL/영역 변화는 결과 확인 근거이며, 로딩은 pending으로 기록하고 Enter를 재전송하지 않는다. 세 신호가 없으면 미확인으로 유지한다.
- URL/결과 변화, 로딩 중/종료, 신호 없음, 제출 실패를 포함한 `tests/test_interaction_flows.py` 및 연계 Fast/runner/관찰/action/dashboard 회귀 **92 passed in 83.30s**. 전체 `python3 -m pytest -q tests`: **613 passed in 352.64s**. targeted Playwright 테스트는 submit form으로 이동하는 로컬 route만 사용했다.
- `python3 -m compileall -q src/uxagent`, `python3 scripts/check_repo.py` (0 problems), `git diff --check` 통과. 실제 Qwen·Decathlon 사이트 재실행은 하지 않았다.

## 2026-10-21 Qwen `enter=false` JSON 문법 교정

- 실제 실행 `20261021T123650-e2648528`의 4번째 행동에서 Qwen은 `"enter=false"`를 JSON 키로 반환했다. 최초 응답에는 `description`도 없었고, 한 번의 수정 요청 뒤에는 설명이 생겼지만 같은 문법 오류가 남았다. 행동은 실행 전에 차단됐다.
- 이 원본 표기와 누락 설명을 재현한 테스트는 수정 전 실패했다. `model_json.py` 추가 후 UActions 응답에서 해당 키 오타만 교정하고 기존 스키마 검증을 통과시키는 회귀를 확인했다. 정상 JSON의 설명 문자열과 다른 문법 오류는 교정하지 않는다. 호출 로그는 원본 응답과 교정 표시를 별도로 보존한다.
- `python3 -m pytest -q tests/test_model_json.py tests/test_u_fast.py tests/test_prompt_guard.py tests/test_target_selection.py`: **51 passed in 4.73s**. 첫 sandbox 실행의 Chromium/로컬 HTTP 2건은 권한 때문에 실패했고, 허용 환경에서 동일 명령으로 재검사했다. `compileall`, 저장소 검사(0 problems), diff 공백 검사도 통과했다. 실제 Qwen·데카트론 전체 과업 재실행은 하지 않았다.

## 2026-10-21 모델 JSON 문법 공통 검사 확장

- `model_json.py`에 모델용 제한 교정과 엄격한 전송 JSON 검사를 분리했다. 코드블록/BOM, 후행 쉼표, True/False/None, 확인 가능한 키/구분자 오류, 문자열 제어 문자를 처리하고 기존 GPU 인식 suffix 교정을 한곳으로 옮겼다. 중복 키·NaN/Infinity/overflow·잘린 응답·복수 루트는 거부하며 교정은 최대32회다. 원래 필드·값을 추가하지 않고 문법 검사 뒤 기존 response model과 의미 검증을 유지한다.
- Fast 모든 단계와 Slow/Wonder/중요도, 요약·설문·페르소나·설정 도우미·연결 확인을 연결했다. 호출 trace가 있는 경로에서는 원본 response와 `json_repairs`, usage를 함께 확인했다. API envelope가 깨진 경우는 ProviderJSONError이며 모델 수정 요청을 하지 않는다. API 전송은 엄격한 직렬화로 비표준 숫자를 차단한다.
- 최종 집중 검사: `python3 -m pytest -q tests/test_model_json.py tests/test_u_fast.py tests/test_u_slow.py tests/test_survey.py tests/test_setup_guide.py tests/test_prompt_guard.py tests/test_target_selection.py tests/test_gpu_provider.py tests/test_provider_budget.py tests/test_local_embeddings.py tests/test_gpu_session.py tests/test_qwen_tokenizer.py tests/test_setup_guide_http.py tests/test_claude.py` → **241 passed in 13.99s**. 파서/각 단계/요약/페르소나/설정 직접 회귀만으로도 **41 passed**였다.
- 전체 검사는 중간 코드에서 **654 passed / 1 failed in 368.10s**였다. 실패는 연결 확인에 불필요하게 추가했던 `ok=true` 필수 조건 때문에 기존 `{}` fixture가 거부된 것이었다. 이 조건을 제거하고 문법 검사만 유지했다. 해당 회귀 단독·`--lf` 재검사와 위 최종 집중241건은 통과했다. 최종 전체 suite를 다시 실행하지 않았으며 중간 전체 결과를 최종 전체 통과로 표시하지 않는다.
- 기존 실행 `20261021T123650-e2648528`의 모델 응답43개를 원문 수정 없이 로컬 재생했다. 기존 json.loads에서 문법 오류였던9개 모두 공통 파서를 통과했다. 이는 문법 복구만의 결과다. 계획 배열/누락 description 등의 스키마 문제 해결이나 실제 행동 성공을 의미하지 않는다.
- 대시보드의 이전 소유 GPU 세션 정리를 확인하고 수정 코드로 재시작했다. 실제 사이트/Qwen 자율 과업은 재실행하지 않았다. HTTP/GPU 준비 확인은 이 과업의 성공 판정과 구분한다.

## 2026-10-22 행동별 양식과 인자 오류 재요청

- 실제 `20261021T142323-1302c49e`에서 두 번 반환된 raw_type+target=s23+text=80000을 확인했다. 원인은 기존 공통 스키마 템플릿이 raw_type의 금지 인자 target도 보존한 것이었다. 재현 테스트2건은 수정 전 실패했다.
- 행동 프롬프트는17개 지원 행동의 JSON 예시, 선택 필드와 raw_type/type 차이를 제공한다. 최종2375자로 기존2400자 미만 제한을 만족한다. 예시 전체를 UAction 스키마로 검증하고 지원 행동 목록과 일치하는지 확인한다.
- UAction.argument_contract의 필수/허용 인자를 validator와 재요청에서 공유한다. 금지 인자를 제외한 행동별 초안, 인자 진단, raw_type의 대상/Enter 의도에 맞는 type 대안을 제공한다. 원래 대상·텍스트·설명과 가능한 Enter를 보존하며 실제 선택은 재응답한 모델이 결정한다. 좌표/탭 등 누락한 숫자를0으로 만들지 않고 null로 둔다.
- `python3 -m pytest -q tests/test_u_fast.py tests/test_target_selection.py tests/test_u_actions.py tests/test_model_json.py tests/test_prompt_guard.py tests/test_interaction_flows.py tests/test_runner_flow.py`: **120 passed in 32.03s**. 최초 집중 실행은 프롬프트가2405자여서 길이 회귀1건이 실패했고, 최종 축약 후 통과했다. 마지막 예시/문구 조정 뒤 `tests/test_target_selection.py`도 **4 passed in 0.19s**로 재확인했다.
- 모델이 type 또는 raw_type을 선택한 두 경로, 반복 invalid 응답 차단, 한 번의 재요청/원문/usage/예약 예산, 필수 설명과 좌표 누락, 실제 실행기 연계 및 prompt guard를 검사했다. `compileall`, 저장소 검사와 diff 공백 검사도 통과했다. 실제 Qwen 재요청/데카트론 전체 과업은 이번 변경 후 실행하지 않았고 전체 suite도 재실행하지 않았다.
- 마지막으로 대안 선택 안내와 충돌하던 “템플릿을 그대로 완성” 문구를 “참고하여 완성”으로 정리한 뒤 재요청 관련7건도 통과했다.

## 2026-10-22 Min/Max 입력 관찰과 마지막 객체 괄호 누락

- `20261021T152740-3bda475a`의7번째 행동은 text=80000을 Min 대상에 입력했다. 직전 관찰의 두 숫자 입력은 이름이 input, 값은20900/269000이었다. 원본 HTML에는 각각 앞의 span에 Min/Max가 있었지만 입력 이름에 연결되지 않았다. 모델은 s22를 최대 가격 입력으로 설명했고, 이후 전역 Enter와 잘못된 범위 해석이 이어졌다.
- 원인 회귀2건을 수정 전에 실패시켰다. 수정 후 Min/Max 이름·원래 locator ID 대응·interaction_state.inputs·강제 GPU 압축 입력 모두에 역할이 보존됨을 실제 로컬 Chromium에서 확인했다. 명시적 aria 이름과 이메일 placeholder도 유지했다. 계획/행동 지침은 이하=최대/상한, 이상=최소/하한으로 설명하며 예산을 임의 변경하지 않게 했다. 행동 지침2353자/계획1474자로 기존 제한 미만이다.
- 실패한 plan 원본449자와388자를 다시 읽었다. 둘 다 문자열과 내부 구조는 완결됐고 마지막 바깥 `}` 하나만 없었다. 수정 후 `root_object_close` 규칙으로 JSON 및 UPlan 검증을 모두 통과했다. 기존 로그/실패 판정은 바꾸지 않았다. 이 재생은 모델의 잘못된 예산 해석을 정답으로 바꾸거나 실제 행동 성공을 증명하지 않는다.
- `python3 -m pytest -q tests/test_model_json.py tests/test_u_fast.py tests/test_u_observation.py tests/test_target_selection.py tests/test_prompt_guard.py tests/test_survey.py tests/test_runner_flow.py`: **140 passed in 29.35s**. 완결 값의 마지막 객체 괄호 복구, 문자열 내 괄호/escape 보존, 잘린 숫자/문자열/중첩 거부, 추가 호출 없는 원문·usage·교정 로그를 함께 검사했다.
- `compileall`, `node --check src/uxagent/parser/parser.js`, 저장소 검사(0 problems), diff 공백 검사 통과. 실제 Qwen/Decathlon 과업·전체 pytest는 이번 수정 후 재실행하지 않았다.


## 2026-10-22 공통 DOM 요소 문맥 검증

- 가격 전용 보완을 이름 출처·소속 그룹·제약·상태·관계의 공통 추출로 확장했다. 원본 semantic ID/실행 registry는 유지한다.
- 구현 전 새 소속 그룹 테스트2건의 실패를 확인한 뒤 구현했다. 추가로 긴 한국어 그룹 이름의 구역 선택 입력 초과를 재현하고, 미리보기와 최종 전체 문맥을 분리해 해결했다.
- 전체 `python3 -m pytest -q tests`: **672 passed, 2 failed, 376.54s**. usage partial 사례는 Chromium launch180초 timeout, wonder seed 사례는 UI 클릭30초 timeout이었다. 두 파일을 분리 재실행한 `tests/test_usage_coverage.py tests/test_wonder_seed_precision.py`: **15 passed, 22.72s**. 전체 검사가 처음부터 모두 통과했다고 표기하지 않는다.
- 최종 관련 회귀 `tests/test_dom_context.py tests/test_u_observation.py tests/test_target_selection.py tests/test_interaction_flows.py tests/test_prompt_guard.py`: **38 passed, 15.55s**. 카드/폼/표 소속, 옵션 상태, 비활성 대상, 팝업 격리, 요약과 계층 선택 후 그룹 참조를 검사했다.
- `compileall`(src 및 수집 스크립트), 새 JS의 `node --check`, `scripts/check_repo.py`, `git diff --check` 통과. 프로젝트에 별도 lint/type-check 도구 설정은 없다.
- 실제 Chromium으로 공개15개 사이트를 읽어 **서로 다른13곳**의 DOM·스크린샷·모델 입력을 수집했다. 컨트롤2,525개, 공유 그룹1,428개, 명시적 라벨 대조150건, unknown 라벨206건이다. 통과 사이트의 관찰 오류는0건이다. W3C403 challenge와 GNU 네트워크 중단은 제외했다. 사이트별 결과와 한계는 [공통 DOM 문맥](tasks/dom-context.md)에 기록했다.
- 실제 수집 명령: `python3 scripts/verify_dom_context_sites.py --output runs/private/dom-context-live-2026-10-22-verified`. 해당 폴더에 source.html/관찰/PNG/model-context/model-input/pipeline/result 및 report.md/json을 보관하며 Git 제외를 확인했다.
- 실제 네트워크 검증은 페이지 읽기뿐이다. 실제 모델 요청·로그인·폼 제출·구매0회. Fast 입력 검사/대상 선택의 모델 응답은 모의했고 원격 tokenizer 없이 보수적 크기 검사를 사용했다. 실제 Qwen 의미 해석·과업 성공·속도 개선량을 입증하는 결과는 아니다.
- 무료 Mock CLI 통합: `python3 -m uxagent run --study configs/study.json --provider mock --headless --output runs/private/dom-context-mock-2026-10-22` 종료 코드0. run `20261022T000021-b859892d`에서 최종 독립 판정 success(검색/필터/상세3항목 pass), 행동30/30 성공, 기록30/30, 오류0건을 확인했다. 모델 terminate가 아닌 max_steps30 종료이며 Brain incomplete를 유지한다. 모의 Slow는 즉시 응답 반복으로1,858회 순환·총 모의 모델 요청3,973회를 기록했으며 실제 GPU 지연/비용의 근거로 사용하지 않는다.


## 2026-10-22 Qwen system-only 토큰 검사 수정

- 최근 두 실제 실행은 검색어 입력·Enter 후3단계의 토큰 검사에서 중단했다. 원격 `/tokenize`는 user만200, system만500/tokenization_failed, feedback system만500, system+빈 user200/160토큰을 반환해 결정적 요청 구성 문제를 확인했다.
- 수정 전 추가 회귀8건 실패·기존14건 통과를 확인했다. 수정 후 지침 단독 검사에만 빈 user를 추가하고 HTTP 오류의 상태/허용 코드만 보존한다. 원본/생성 메시지 불변, fixed 초과 차단, 민감 본문 비노출, 오류 캐시 금지와 추정값 우회 금지를 확인했다.
- 관련 `tests/test_prompt_guard.py tests/test_qwen_tokenizer.py tests/test_u_fast.py tests/test_target_selection.py tests/test_model_json.py`: **111 passed, 6.82s**. 최초 제한 환경 실행은109 passed/2 failed였으며 Chromium 시작·fixture bind 권한 때문에 실패해 허용된 환경에서 재실행했다.
- 실제 원격 토큰 계산 재생: 긴 기억 입력은 요약 응답을 모의하고216토큰으로 최종 검사 통과. 실제 생성 요청0회. 최근 실패 화면의 feedback 입력은10,438토큰이며 내부 지침 검사160토큰을 통과했다. 그러나 보호 조작 문맥이 요약 후에도9,849토큰으로 남아8,192한도 초과를 정확히 차단했다. 이는 이번 HTTP500 수정과 별개인 남은 한계이며 실제 전체 과업 성공으로 표시하지 않는다.
- `compileall`, `scripts/check_repo.py`(0 problems), `git diff --check` 통과. 별도 lint/type-check 도구 설정 없음.
- 수정 후 전체 `python3 -m pytest -q tests`: **682 passed, 407.27s**. Chromium·로컬 포트 사용이 가능한 허용 환경에서 직렬 수행했다.
- 무료 Mock CLI 통합 (`runs/private/tokenizer-fixed-probe-mock`): run `20261022T010123-4cb328ec`, 종료 코드0, 독립 판정 success, 행동 30/30, 오류 {}. 종료 사유는 max_steps이며 실제 Qwen 자율 성공과 구분한다.


## 2026-10-22 feedback 보호 문맥 초과 수정

- 최신 run 20261022T014757-f41be58a는 Enter 이후3단계 전 feedback 보호 문맥10,371토큰으로 중단했다. stage별 역할 구분 없이 전체 controls/element_context를 보호한 문제를 새 회귀의 실패로 재현했다(1 failed/15 passed).
- Fast feedback만 observation의 전체 조각 요약·병합을 허용한다. feedback_state·페르소나·직전 행동·실행 사실은 보호하고 decision/기본 단계에는 적용하지 않는다. 최종 관찰과 원본 run은 바꾸지 않는다.
- 관련 tests/test_prompt_guard.py, test_qwen_tokenizer.py, test_u_fast.py, test_dom_context.py, test_target_selection.py: **72 passed, 11.68s**.
- 실제 실패 관찰·페르소나·직전 행동/실행 결과·계획을 재생했다. 실제 원격 계수를 사용하고 요약/최종 피드백은 모의했다. 관찰 전체가9개 조각에 포함됐고 모든 발송 입력이 한도 안에 들며 최종1,141토큰을 확인했다. 실제 모델 생성/브라우저 행동0회. 로컬 결과: runs/private/feedback-preflight-replay-2026-10-22.json.
- 이전 항목의 feedback 문맥 조정 미완료 표현은 당시 이력이다. 이번 입력 재생 통과와 실제 Qwen 요약 품질/자율 과업 성공은 구분한다.
- 전체 `python3 -m pytest -q tests`: **686 passed, 486.18s**. `compileall`, `scripts/check_repo.py`, `git diff --check` 통과. 별도 lint/type-check 도구 설정 없음.
- 무료 Mock CLI 통합: 임시 study의 max_steps=6, 원본 persona 경로를 지정했다. run `20261022T020316-80e8ecb3`, 독립 판정 failure, 행동 6/6, 오류 {}, 종료 사유 max_steps. 출력 `/private/tmp/uxagent-feedback-check-4g49i16b/runs/20261022T020316-80e8ecb3`. 실제 모델 생성 검증과 구분한다.
- 같은 Mock을 기본30단계로 재검증: run `20261022T020349-32b2a86b`, CLI 종료 코드0, 독립 판정 success, 행동 30/30, 오류 {}, 종료 max_steps.


## 2026-10-22 누적 수정 PR 준비·prototype 통합

- 새 브랜치 fix/90-qwen-dom-json-preflight-20261022에 기존 미병합 오류 수정과 후속 JSON·공통 DOM·토큰/feedback 수정을 보존했다. 최신 prototype9095b3c를 merge해 D/U 검토 수정을 함께 유지한다.
- 충돌 해결 시 GPU hover/select 옵션 값·href, 비밀번호/Slow 출력 보호, 취소 최종 기록, 설문 재시도 무효화, 최종 평가/설문 화면·다운로드와 취소 표시를 함께 확인했다. 관련8개 테스트 파일 **138 passed, 74.36s**.
- 병합 후 전체 `python3 -m pytest -q tests`: **724 passed, 423.02s**. 병합 전686건과 구분한다.
- compileall, JS 구문 검사, repo/staged 검사와 diff 공백 검사 통과. doctor는 제한 환경에서 Chromium 권한으로 실패했고 허용 환경에서 Chromium available/study_errors=[]로 통과했다.
- prototype 대비77개 파일의 경로와 로컬 비밀 값 포함 여부를 검사했다. .env.example의 추가 값은 모두 빈 값이다. .env/인증정보/runs/비공개 비교 원자료는 포함하지 않는다. 실제 Qwen 요약 품질·전체 과업 성공, 대시보드 상태 조회 성능은 별도 후속이다.
- 최종 무료 Mock CLI: run `20261022T040921-b13b644a`, 독립 판정 success, 행동 30/30, 오류0, 종료 max_steps. 임시 경로에 보관하며 실제 Qwen 과업 성공과 구분한다.
- 최초 push의 원격 CI는 Ubuntu 성공/Windows 진행 중으로 확인했으며 최종 문서 커밋의 CI와 별도로 본다.

## 2026-10-22 PR #103 Windows GPU 포트 검사 수정

- PR #103 Windows 3.13의 push와 pull_request 필수 검사가 모두 같은 회귀에서 실패했다: 이미 listen 중인 포트에 `_check_ports()`가 `RuntimeError`를 내지 않았다. 두 로그 모두 **718 passed, 1 failed, 5 skipped**였다. Ubuntu 3.11 push/PR은 성공했다.
- 원인은 Windows에서 `SO_REUSEADDR`를 설정한 bind가 점유된 listener 포트에도 성공할 수 있는 플랫폼 차이다. Windows probe에 `SO_EXCLUSIVEADDRUSE`를 설정했다.
- 수정 후 타깃 테스트를 로컬에서 실행했으나 sandbox가 테스트 listener의 `127.0.0.1` bind를 `PermissionError`로 막아 테스트 본문에 도달하지 못했다. 따라서 로컬 재검증은 미완료이며, 수정 후 Windows CI 재실행 결과를 별도로 확인한다.
