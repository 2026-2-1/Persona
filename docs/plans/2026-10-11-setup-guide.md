# 모델 선택·설정 도우미 Implementation Plan

사용자 요청: 모델별 API키 발급 안내, 모델 선택, AI토큰으로 페르소나 추천, 먼저 고를 수 있는 상황, 주변 AI도우미.

목표: 기존4단계/로컬Python실행기를 유지하며 시작 상황·사용자예시를 무료로 제공하고 연결한 모델로 요청 시에만 추천/짧은 상담을 실행한다. 제안은 적용 버튼으로 검토 후 반영한다.

## 작업과 파일 소유
- 모델 연결: model_catalog.py(공식안내/허용모델/default), schemas.py/provider_model, runner.py/fast_loop.py/llm.py의 실행모델·비용 기록, monitor.py의 model 연결/작업 인자. 기본CLI호환 유지, 잘못된모델 차단, 선택모델 snapshot/log 일치 테스트.
- 도우미 서비스: setup_guide.py와 test_setup_guide.py. static_options는 시나리오/사용자예시를 제공, SetupGuide.recommend(provider,model,message,context,history) JSON추천을 검증한다. 가정페르소나이며 연령/성별고정관념·평가정답·키·페이지지시를 쓰지 않는다. 키는 기존 서버환경만, 입력/출력 민감정보 차단, 5요청/12000토큰·출력1000 상한, 요청실패도분모 유지. 대화 저장 없음, 토큰메타만메모리.
- 프런트/통합: index.html/app.js와 monitor GET /api/setup-guide/options, POST /api/setup-guide. 오른쪽도우미, 시작상황 버튼, model-select, 발급 안내. 추천카드 title/background/count/reason을 클릭해야 사용자설정에 적용. 최근기록을 접어서 유지, 모바일한열, 기존 검증/비교·키비노출 회귀.
- docs/README와 현재상태·계약·트러블슈팅·검증, 실패테스트→최소구현→전체검사→리뷰→PR/prototype.

## 계약
model_catalog.catalog_payload(): providers 매핑. provider마다 models[{id,label,note}], default_model, key_url, docs_url, steps[], note. resolve_model(provider,model=None) 허용목록/기본값검증. 기존기본모델을 보존하며 제공자가 지원하는지 연결 요청으로 확인한다. 모델선택은 최신/가장좋음/인기 통계 주장과 구분한다.
setup_guide.static_options(): scenarios[{id,title,task,hint}], personas[{id,title,background,count,reason}].
SetupGuide.recommend 응답: answer, personas[{title,background,count,reason}], task_suggestion(nullable), source(template/ai), provider(실제생성제공자), model, usage{requests,max_requests,max_total_tokens,input_tokens,output_tokens,estimated_cost_usd}. 실패는 민감값없는 오류.
context: target_url/task/persona_background만, evaluator정답/관찰/키 제외. history는 최근6개 user/assistant text만.
Jev는 행동분류모델, 상담은 선택된Gemini fallback으로 생성.

## 공식 근거 (2026-10-11 확인)
OpenAI 키: https://platform.openai.com/api-keys / https://developers.openai.com/api/docs/quickstart
OpenAI GPT4.1mini ChatCompletions: https://developers.openai.com/api/docs/models/gpt-4.1-mini
Claude: https://platform.claude.com/docs/en/api/overview / https://console.anthropic.com/settings/keys
Gemini: https://ai.google.dev/gemini-api/docs/api-key / https://aistudio.google.com/apikey / https://ai.google.dev/gemini-api/docs/models
Jev: https://console.typesafe.ai/login (상세발급경로 미확인, 임의메뉴단정금지)
기존 모델들은 계정/지원상태가 다를 수 있다. Gemini2.5는 신규계정 접근제한 안내가 있어 미리 공지한다. 실제 키/유료API를 개발 검증에서 사용하지 않는다. 계정구독토큰을API크레딧으로 설명하지 않는다.
