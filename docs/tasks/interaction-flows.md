# 검색·스크롤·메뉴·팝업 흐름 (2026-10-21, 검증 대기)

사용자 요청에 따라 후속 채팅에서 로컬 테스트를 수행했다. 실제 GPU·Decathlon 과업은 실행하지 않았다. 전체 테스트 최초 실행과 수정 후 집중 재검증의 상세는 [검증 기록](../verification.md)을 따른다.

## 확인한 문제

실행 `20261021T062621-1dfb433b`에서 검색 입력을 연 뒤 같은 입력을 반복 클릭했다. 저장된 입력은 focused=true였지만 모델용 간략 컨트롤은 focused를 누락했다. 계획은 검색어 입력을 지시했지만 실제 행동은 클릭이었다. 클릭 ok=true는 도구 실행 사실이므로 논리적 검색 진행을 증명하지 않는다. 별도로 기존 scroll 프롬프트는 픽셀 단위였지만 실행기는 amount×3 방향키 입력이었다.

## 구현 연결

- `interaction.py`: Brain 실행마다 별도 InteractionFlow를 둔다. 검색이 선택된 뒤의 입력·제출과 현재 팝업 처리를 다음 관찰에 연결한다. 검색 사용 여부는 계속 모델/페르소나가 결정한다.
- `parser/interaction_state.js`, `observation.py`: 현재 입력값·포커스·viewport 포함 여부·문서/내부 스크롤 위치·팝업을 기록한다. popup PNG는 해당 영역만 저장한다. 기존 원본 DOM과 전체 viewport PNG도 보존한다.
- `fast_loop.py`: 컨트롤의 focused/enabled/checked/in_viewport/options를 모델에 보존한다. 계획에도 입력/스크롤/팝업 상태를 제공한다. 대상 별칭과 직전 행동 대상도 맞춘다.
- `actions.py`: 방향키 반복을 픽셀 이동으로 교체한다. direction/amount/선택적 target으로 페이지 또는 내부 영역을 움직인다. 한 번 이동은 화면에 보이는 영역의 80% 이내다. before/after/moved/끝 위치를 ActionResult.interaction에 기록한다. 기존 scripted scroll_y는 유지한다.
- `schemas.py`: Observation.interaction_state, ElementInfo.in_viewport, ActionResult.interaction을 기본값과 함께 추가한다. scroll에 target을 허용하고 amount는 양수로 제한한다.

## 검색 순서

1. 일반 모델이 검색창 클릭을 선택한다. 검색 우선 정책은 없다.
2. 실행 후 관찰에서 동일 입력 또는 유일하게 일치하는 입력을 다시 찾는다.
3. `search_query` 호출에 페르소나·과업·현재 입력·실행 결과를 제공한다. 모델은 검색어 또는 검색 취소를 반환한다.
4. 결정한 검색어를 type/enter=false로 입력한다. 이 단계는 전체 perception/plan/decision을 다시 호출하지 않는다.
5. 다음 관찰의 실제 입력값과 검색어를 비교한다. 일치한 경우 관찰된 모든 결과 링크/검색 버튼을 선택하거나 일반 폼에 Enter를 보낸다.
6. 데카트론 헤더는 Enter가 패널을 닫는 것으로 관찰됐으므로 관찰된 결과 링크를 우선한다. 링크가 없으면 자동 Enter 대신 현재 로딩/빈 결과/제출 수단을 재판단한다.
7. 제출 뒤에는 일반 판단으로 돌아가 실제 검색 결과를 확인한다. URL/탭 변화, 입력 소실, 입력값 불일치, 도구 실패도 재계획으로 돌린다.

각 동작은 기존 runner의 한 행동→실제 관찰을 유지한다. 검색어 생성 호출은 llm_calls에, 연결된 행동은 steps/brain_stages에 남는다. 연결 행동 기록의 `Interaction continuation` 표기는 호스트가 이어 붙인 행동이며 추가 LLM 호출이 있었다는 뜻이 아니다.

## 메뉴·스크롤·반복

메뉴는 기존 경로/expanded/visible_children를 이용해 열린 부모에서 하위 항목 또는 모두 보기로 이동하도록 지침을 연결했다. 현재 화면 밖 요소는 in_viewport=false로 구분한다. U DOM 전체 추출 정책을 완전한 viewport 전용 추출로 바꾼 것은 아니다.

스크롤은 문서 또는 관찰된 내부 영역을 지정한다. 세로는 높이, 가로는 너비를 기준으로 겹치는 구간을 남긴다. 이동이 없으면 경계/영역/방향을 재판단한다. 정해진 비율만으로 지연 로딩·가상 목록의 모든 정보를 보았다고 보장하지 않는다.

같은 행동 후 입력값·컨트롤·스크롤·팝업 상태가 반복해서 같으면 interaction_progress로 재계획 근거를 전달한다. 일반 행동을 일괄 차단하거나 반복만으로 강제 종료하지 않는다. 메뉴 반복 방지는 현재 상태와 모델의 재계획에 의존하며 실제 검증은 남아 있다.

## 팝업 우선 처리

전경 dialog/aria-modal 및 닫기 컨트롤이 있는 큰 overlay 후보를 관찰한다. 검색 패널은 검색 흐름으로 분리한다. 일반 페이지 인식 전에 페르소나·과업·팝업 본문/컨트롤만 `popup_decision`에 보낸다. 배경 페이지 목록이나 과거 기억을 이 요청에 섞지 않는다.

모델은 interact/ignore/stop을 고른다. interact는 관찰된 팝업 컨트롤 또는 사진상의 좌표를 사용한다. modal을 ignore하거나 배경 대상을 제안하면 한 번 교정을 요청한다. ignore한 비모달은 동일한 팝업 내용에 한해 다시 묻지 않는다. 닫힘 여부는 다음 실제 관찰로 확인한다. stop은 사용자 과업 성공이 아닌 agent_gave_up으로 연결한다.

본문을 읽을 수 없으면 팝업 영역 PNG를 이미지 입력으로 보낸다. 이미지 좌표는 팝업 내부 기준이며 실행 전에 화면 좌표로 변환한다. 이미지 자체를 JSON 로그에 base64로 남기지 않고 파일명을 기록한다.

### 사진 경로의 현재 제한

기존 persona-qwen 텍스트 서버가 이미지까지 처리한다고 가정하지 않는다. 이미지 경로를 사용하려면 다음 두 환경변수에 **이미지를 지원하는 로컬 SSH 터널 API**와 모델을 설정해야 한다. 이번 변경은 원격 서버를 설치/변경하지 않았다.

- `PERSONA_QWEN_VISION_API_URL`: 로컬 HTTP `/v1/chat/completions` 주소.
- `PERSONA_QWEN_VISION_MODEL`: 해당 이미지 서버가 제공하는 모델명.

이미지 요청 형식은 [Chat Completions image_url 명세](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)를 사용한다. API 요청은 기존 GPU 대기열을 공유한다. 텍스트 입력은 기존 검사로 확인하지만 별도 이미지 모델의 이미지 토큰을 정확히 계산하지는 않으며 image_preflight로 이 차이를 기록한다. 원격 이미지 서버 지원·모델·컨텍스트 한도·사진 판단은 미검증이다.

설정이 없으면 `popup_vision_unavailable`과 model_capability_error로 중단한다. 사진을 본 것처럼 추정하거나 팝업을 임의로 닫지 않는다. 이미지 캡처 실패도 popup_image_unavailable로 구분한다. iframe/shadow DOM 등 아직 추출하지 못하는 팝업과 overlay 휴리스틱 오탐은 검증·보완 대상으로 남는다.

## 추가 검증 항목

1. 스키마/연결: 이전 observation 기본값, scroll target/양수, 중간 판단 후 일반 계획 복귀, Brain 작업 완료 기록.
2. 검색: 클릭 반복 재현, 페르소나 검색어 선택/취소, 입력값 확인, Enter와 명시적 제출, DOM ID 변경, 입력 소실/실패, 새 URL/탭, 제출 뒤 성공·빈 결과 구분.
3. 스크롤: 페이지/내부 영역, 상하좌우, 포커스된 입력이 있을 때 스크롤, 일부만 보이는 영역, 끝/변화 없음, scroll snap·지연 로딩.
4. 메뉴: 열린 부모/동명이인 경로/하위 항목/화면 밖 항목, 변경 없는 반복의 재계획.
5. 팝업: 배경 입력 누출 없음, 광고와 검색 패널 구분, 텍스트 팝업/사진만 있는 팝업, 닫힘/무시/중지, 유효하지 않은 대상, 사진 좌표, 모델 미지원과 캡처 실패.
6. 실제 GPU 검색·팝업 흐름. 이미지 전용 서버 준비 여부를 먼저 확인한다. Mock 결과를 실제 GPU 성공으로 표시하지 않는다.

Mock 통합과 전체 pytest는 포트 충돌을 피하도록 동시에 실행하지 않는다. 이미지 전용 서버와 실제 GPU/Decathlon 동작은 별도 환경 검증으로 남아 있다.
