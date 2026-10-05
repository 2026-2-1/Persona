# 팀 개발 안내

1. 저장소를 받은 뒤 `bash scripts/setup.sh`를 실행하고, `bash scripts/dev.sh`로 데모가 동작하는지 확인합니다.
2. 담당 작업의 브랜치를 만들어 수정합니다. 예: `feat/session-review`, `fix/worker-error`.
3. 환경 설정은 `.env`에 두고, 공유가 필요한 설정은 비밀값 없는 `.env.example`에 반영합니다.
4. 의존성을 바꾸면 해당 `uv.lock` 또는 `package-lock.json`도 함께 커밋합니다. 기존 잠금 파일은 임의로 재생성하지 않습니다.
5. DB 구조 변경은 새 Alembic 마이그레이션으로 추가합니다. 실행 상태/API 응답을 바꾸면 프런트 타입과 `docs/architecture.md`도 맞춥니다.
6. PR 전에 `bash scripts/check.sh`를 통과시키고, 실행 흐름에 영향이 있으면 데모와 `scripts/smoke.py`도 확인합니다.
7. PR 설명에 변경 이유, 확인한 동작, 남은 제한을 적고 다른 팀원 1명의 리뷰를 받습니다.

첫 개발 범위는 실행 1건의 생성 → 워커 처리 → 화면/로그 저장 → 결과 조회입니다. 새 과업이나 실제 모델 연결도 이 흐름을 유지하면서 추가합니다.
