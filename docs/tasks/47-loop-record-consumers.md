# [phase:1] 두 루프 기록의 대시보드·보고서 연결

GitHub: [#47](https://github.com/2026-2-1/Persona/issues/47)

## 구현 범위

- 실행 상세에 Fast/Slow 생성 단계와 비동기 작업 사건 전체를 읽어 관찰 ID별 행동 근거에 연결한다. 관찰 ID가 없는 Wonder는 추첨 기록의 부모 Slow 작업 ID를 따라 원래 관찰에 연결한다. 예약·시작·생성 완료·채택·폐기·생략·실패·취소 상태는 원본 사건을 유지한다.
- 사용한 기억 ID를 원본 `memory.jsonl`로 해석하고 활성 제거 여부를 `memory_changes.jsonl`에서 확인한다. 생성 내용, 실행 행동, 독립 평가를 분리한다.
- 화면 및 JSON·CSV·Markdown·HTML 출력에 같은 기록을 포함한다. 새 로그가 없는 구버전 실행과 null 행동·결과는 빈 근거/미확인으로 읽는다.
- 원본 [neuhai/UXAgent](https://github.com/neuhai/UXAgent/tree/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd)의 API trace와 memory trace 출력을 기준으로 호출·기억의 출처를 대조했다. 이 프로젝트의 독립 평가는 별도 판정으로 유지한다.

## 검증과 제한

- 로컬 mock과 가짜 기록으로 구버전/null, 비동기 취소, 활성 제거 뒤 원본 근거, 네 형식 출력의 회귀를 검사한다. 실제 사람 행동 유사성이나 유료 API·공개 사이트 성공을 이 연결만으로 검증하지 않는다.
