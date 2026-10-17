# #85 U 기억 검색·임베딩

이슈: [#85](https://github.com/2026-2-1/Persona/issues/85). 작업 브랜치 `feat/85-u-transition-03`, 선행 Slow [PR #93](https://github.com/2026-2-1/Persona/pull/93) 커밋 `f293a0ad526c78d013939efb195cf209c657a522`를 포함한다. 선행 PR은 미병합이며 prototype 반영과 구분한다.

## 작업 브랜치의 구현 범위

- 실행기의 plan query는 intent, act query는 next_step을 유지한다.
- `retrieve_u` 점수는 `(dot(memory, query) + exp(memory.timestamp-current) + importance/10) * kind_weight`다. legacy 1.0의 0~5 중요도는 5로 나눈다. 미산정 중요도는 0으로 취급하며 없는 점수 때문에 전체 수식을 다시 정규화하지 않는다.
- plan 가중치 action/plan/thought/reflection=10, 나머지1. act 가중치 observation=0, action/thought=10, 나머지1.
- ranked 기본20개 전에 plan은 observation 최근3차례, action/plan/thought 최근5차례를 종류별로 추가한다. 경계 포함이며 ranked와 중복을 제거하지 않는다. 활성64개와 최종 프롬프트 개수는 다르다.
- Fast는 Slow의 memory embedding 갱신 완료를 기다리지 않는다. 준비된 활성 ID가 없으면 query embedding을 호출하지 않고 U처럼 최근 목록만 반환한다. 일부 준비됐으면 준비된 ID만 순위를 매긴다. query embedding은 매 검색 호출하며, word overlap/cosine/시간 반감기로 fallback하지 않는다. query 호출 실패는 숨기지 않는다.
- 벡터는 비어 있지 않은 유한 숫자 목록과 같은 차원이어야 한다. 응답 검증 실패도 실제 usage를 보존하고 취소는 요청·미확인 usage를 기록하며 예약을 정산한다.
- 이전 `retrieve`/`retrieve_with_embeddings`는 명시적 구형 호출자·회귀용이며 현재 runner는 U 검색을 호출한다.

## 확정한 제거 순서와 남은 연결 정보

2026-10-17 사용자 결정으로 활성 상한 초과 시 중요도가 낮은 순서, 동점이면 오래된 seq 순서로 제거한다. 종류·현재 단계·최근10개·점수 대기·Slow snapshot에 따른 우선 보호는 적용하지 않는다. 미산정 null은 사용자 추가 결정으로 채점 전 임시 최상위에 보존하고 원본 중요도는 null로 유지한다. 모두 미산정이면 오래된 seq를 먼저 제거한다. 검색 수식에서만 미산정 중요도 기여를0으로 둔다. legacy 0~5와 새 1~10은 각 최대값으로 나눈다. 원본 로그·점수 사건은 유지하고 활성 ID의 벡터·대기 집합만 정리한다.

사용자 후속 요구에 따라 [대시보드 GPU 수명주기](gpu-dashboard-lifecycle.md)를 추가했다. 기존 DIS01 접속과 자원 명령을 비공개 설정에 반영하며 sbatch 할당·서버/터널 시작·Ctrl+C/SIGTERM 반환을 관리한다. 상세 인증·소유권·최초 준비·강제 종료 한계는 해당 문서를 따른다.

Qwen 채팅은 LocalQwenProvider/persona-qwen을 유지한다. 별도 `embedding_provider=local`과 `embedding_model`을 사용하면 `LocalEmbeddingProvider`가 SSH 터널의 `/v1/embeddings`를 호출한다. Slow의 기억 벡터 갱신과 Fast의 query 생성이 같은 실제 embedding 모델/예산을 사용한다. 응답 모델·index·차원·유한 숫자 오류는 실패로 기록하고 단어 검색이나 외부 API로 fallback하지 않는다. managed GPU 대시보드는 검증된 임베딩 설정을 batch/compare study에 전달한다. 직접 CLI에서는 study에 `embedding_provider: "local"`·`embedding_model`을 지정하고 로컬 환경에 `PERSONA_EMBEDDING_API_URL=http://127.0.0.1:8002/v1/embeddings`를 설정한다. 이 주소에는 SSH 비밀번호나 토큰을 넣지 않는다.

예시 모델은 다국어 MiniLM384차원/128 token이며 실제 CUDA·차원·입력 token usage는 시작 probe와 원격 검증에서 확인해야 한다. 원격 인증은 이번 로컬 BatchMode 읽기 전용 점검에서 Permission denied였다. 실제 설치·GPU 임베딩/채팅·할당 반환·공개 데카트론 성공은 미검증이다. 코드/가짜 transport 회귀와 실제 완료를 구분하며 이슈는 OPEN으로 유지한다.

## 검증과 U 근거

신규 점수·최근 경계·중복·임베딩 미준비·top20·차원 검증 8개가 구현 전 실패하고 구현 후 통과했다. query 호출·usage/검증 실패 2개도 구현 전 실패 후 통과했으며 취소/두 run 캐시 분리까지 신규11개가 통과했다. 신규/Slow/기존 검색·제거·점수 관련36개가 통과했다. Chromium 관련32개 첫 실행은31 passed/1 failed였다. 기존 통합 테스트는 단어 검색에서 생기던 4개 이상의 Action 입력을 요구했으나, 새 임베딩 미설정 경로는 최근 목록만 반환한다. Action 입력 존재·원본/제거/점수/출처/기록 검증은 유지하며 해당 기대값을 변경했다. 후속 재실행 결과는 verification에 기록한다.

- [U retrieve](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/memory.py#L155-L222)
- [U plan/act](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/agent.py#L248-L317)

제거 정책 신규2개도 기존 구현에서 실패했고 변경 후 통과했다. 검색·제거·점수·Slow 관련 **39 passed in 0.20s**였다.
