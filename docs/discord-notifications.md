# 디스코드 알림 연결 준비

현재는 **연결 전**이다. 이번 변경은 설정 절차와 알림 범위를 준비한 것이며 디스코드로 메시지를 보내거나 웹훅을 생성하지 않았다. 팀의 서버·채널과 웹훅이 정해지면 아래 방법으로 연결한다.

## 기본 연결 방식

Discord의 GitHub 호환 웹훅을 사용한다. 별도 봇·서버·Actions 워크플로 없이 GitHub 저장소 이벤트를 받을 수 있고, main/prototype의 코드 차이와 무관하게 저장소에서 동작한다.

1. 팀에서 알림을 받을 채널을 정한다. 예를 들어 개발 대화와 구분한 github 알림 채널을 사용할 수 있다.
2. Discord 서버 설정의 Integrations → Webhooks에서 해당 채널용 웹훅을 생성한다.
3. 복사한 URL 끝에 `/github`를 붙인다. 실제 URL은 채팅·PR·코드·스크린샷에 공개하지 않는다.
4. GitHub 저장소 Settings → Webhooks → Add webhook에서 Payload URL로 입력한다.
5. Content type은 `application/json`, SSL verification은 활성화 상태로 둔다.
6. 개별 이벤트 선택에서 우선 **Pull requests**, **Pull request reviews**, **Issues**만 선택한다.
7. 채널과 이벤트 범위를 확인한 뒤 활성화한다. Recent Deliveries의 응답과 실제 알림을 함께 확인한다. 불필요한 이벤트는 끄고 운영한다.

URL 자체에 게시 권한이 있으므로 GitHub 웹훅 설정에만 보관한다. URL이 노출되면 Discord에서 해당 웹훅을 재발급한다. Actions Secret은 이 기본 연결 방식에는 필요 없다.

## 권장 알림 범위

| 이벤트 | 목적 | 초기 설정 |
| --- | --- | --- |
| pull_request | PR 생성·변경·종료 등의 상태 확인 | 켬 |
| pull_request_review | 승인·수정 요청 확인 | 켬 |
| issues | 작업 생성·상태 변경 확인 | 켬 |
| push | 모든 커밋 알림 | 끔; 작은 커밋이 많아 중복 알림 가능 |
| issue_comment / pull_request_review_comment | 모든 대화·인라인 댓글 | 필요할 때 추가 |
| check_run / check_suite | 검사 이벤트 | 후속 검토; 실패만 필터하려면 추가 자동화 필요 |

네이티브 웹훅은 이벤트 종류를 선택한다. 특정 브랜치만 알림, PR의 특정 action만 알림, CI 실패만 알림, 특정 사용자 mention 같은 세밀한 조건은 이 설정만으로 보장하지 않는다.

## 이후 확장

알림이 너무 많아지거나 CI 실패만 받고 싶으면 별도 작업 이슈로 GitHub Actions 또는 작은 중계 서비스를 추가한다. 이때 웹훅은 GitHub Actions Secret으로 저장하고, 알림 실패를 제품 CI·병합의 필수 조건으로 만들지 않는다.

Actions로 확장할 경우 PR 제목·본문은 실행 코드가 아닌 데이터로 처리하고, 특권 이벤트에서 PR 코드를 checkout하거나 실행하지 않는다. 제목의 @everyone 등으로 의도하지 않은 전체 알림이 발생하지 않도록 mention을 제한한다. 기본 웹훅과 추가 워크플로에서 같은 이벤트를 이중 전송하지 않는다.

## 연결 후 확인할 것

- [ ] 팀에서 정한 서버·채널에만 알림이 도착한다.
- [ ] PR 생성·승인/수정 요청·종료를 구분할 수 있고 GitHub 링크가 맞다.
- [ ] 같은 이벤트가 중복으로 전송되지 않는다.
- [ ] 원하지 않는 커밋·댓글 알림은 꺼져 있다.
- [ ] 실제 URL이 저장소·PR·화면 캡처에 포함되지 않는다.

공식 자료: [Discord GitHub 웹훅 연결](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks), [지원 이벤트](https://docs.discord.com/developers/resources/webhook#execute-githubcompatible-webhook).
