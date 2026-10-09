# 현재 구현 상태

기준: prototype 원본 e4dfa98, 2026-10-09 저장소 설정 작업.

## 구현됨

- Python 3.11+ / Playwright Chromium / Pydantic.
- 화면 내 DOM 관찰, 최신 관찰에 묶인 요소 ID, 클릭·입력·hover·select·탐색·탭 조작.
- Mock, OpenAI Chat Completions, Claude Messages (Sonnet 4.6), Gemini, Jev 후보 선택과 Gemini fallback.
- 요청·토큰 예산, 반복/시간/단계 제한, 허용 origin 검사.
- 메모리 검색, 선택적인 embedding·Slow Loop·Wonder (기본 비활성).
- 로컬 템플릿 persona 생성, 순차 격리 batch, 로그/PNG, 로컬 대시보드.
- 로컬 가방 fixture의 독립 성공 판정, 규칙 기반 문제 후보·HTML review·기록 조합 설문/인터뷰.

## 1차 MVP 추가 구현

- strict 외부 DOM/URL 확인 조건, fixture 검색·필터·상세의 최종 상태 근거.
- 일반/페르소나 프롬프트 분리, 대응 비교 세션 사전 등록·고정 분모·중지·순서 seed.
- 전후 화면/URL/시각/결과 기록 확보율, 도구 실행 수준의 오류 복구 보조 지표.
- 디자인 기준의 테스트·비교·개선·기록 화면, API 키 연결 확인, 실행 중지.
- 미검토 문제 카드와 JSON/CSV/Markdown/HTML 내보내기.
- 옵션 후보 ID 충돌, null 결과 보고서 처리, 실제 검색어 생성/교체 경로 수정.

## 미구현 또는 미검증

- 실제 대상 4개 과업의 독립 평가기, 기능별 검색·필터 검증.
- 자유로운 AI 대화형 설정/근거 Q&A, ChatGPT 구독 OAuth/Responses 연동. 현재 설정은 목표 → 사용자 → 모델 → 실행의 안내형 4단계이며 생성과 실행은 자동으로 이어진다.
- 2인 사람 판정·합의와 개선 전후 자동 재검증. 현재 카드는 미검토 후보다.
- 환경별 비교, 복구 사건 분석, 전체 서비스 큐/DB/스토리지.
- 실제 API·외부 사이트·사람 행동 재현은 이번 저장소 설정의 검증 범위가 아님.

## 수정 전 확인할 제한

- 관찰은 viewport만 지원한다. 독립 scroll, iframe/canvas/복잡한 shadow DOM/custom controls/password는 미지원.
- Jev는 실제 입력값을 Gemini로 생성한다. 옵션 ID 충돌은 회귀 수정됐다. 후보 종료 선택 확장은 후속 범위다.
- 외부 사이트는 명시적 확인 조건이 없으면 unknown이다. 모델 완료 선언을 성공으로 볼 수 없다.
- 설문·인터뷰는 현재 자유로운 대화 모델이 아닌 기록 기반 템플릿이다.
- 평가 오류는 failure/unknown/종료 사유를 함께 읽어야 한다. 과업 실패와 시스템 기능 실패를 분리한다.
