# 대시보드가 소유하는 GPU 세션

2026-10-17 사용자 후속 요청으로 #85 구현에 추가했다. 기존 수동 SSH·Slurm 사용법을 유지하며, 비공개 GPU 설정을 둔 대시보드만 자동 할당한다. 2026-10-18 대시보드 자동 시작에서 Qwen HTTP200, 임베딩 CUDA·벡터 응답 및 작업 반환을 실제 확인했다. 생성형 Qwen 과업 추론은 별도 검증 대상이다.

## 시작과 종료

```text
대시보드 CLI
 → 비공개 설정 읽기 / HTTP 포트 확보 / 로컬 모델 포트 충돌 확인
 → OpenSSH 로그인 master 인증
 → 고유 세션 이름·복구 상태 저장
 → sbatch --parsable로 단일 노드·작업 할당
 → squeue에서 지정 노드 RUNNING 확인
 → compute SSH master + 채팅/임베딩 loopback 포트 전달
 → 채팅 health / 임베딩 health·GPU·실제 1건 벡터 probe
 → 짧은 Qwen 채팅 요청 / 대시보드 제공
Ctrl+C 또는 SIGTERM
 → 실행 중인 로컬 과업 중지·기록 대기
 → 이 세션의 Slurm 이름·ID 확인 / scancel / squeue에서 반환 확인
 → SSH master 종료 / 로컬 환경 복원 / HTTP 종료
```

브라우저 탭 닫기는 서버 종료가 아니다. SIGKILL·전원 종료·네트워크 단절에서는 즉시 반환을 보장하지 못한다. 유한 Slurm walltime과 로컬 복구 기록을 유지한다. 반환 확인 실패를 성공으로 숨기거나 기록을 삭제하지 않는다.

## 설정

[예시 JSON](../../configs/gpu-session.example.json)을 `runs/private/gpu-session.json`으로 복사해 실제 주소·계정·파티션·노드·자원을 설정한다. 실제 주소와 비밀번호를 공개 설정에 넣지 않는다. 비밀번호 필드는 허용하지 않는다. 예시는 p02/DIS01/A6000 1개·CPU4·48G·4시간이고 실제 클러스터의 허용 옵션을 확인해야 한다. 원격 node와 compute_host가 같은 계산 노드를 가리켜야 한다.

```sh
python3 -m uxagent dashboard
python3 -m uxagent dashboard --gpu-config runs/private/gpu-session.json
python3 -m uxagent dashboard --no-gpu
```

기본 비공개 파일이 없으면 종전 수동 연결 방식이다. 자동 모드는 localhost8001→원격8000 채팅, localhost8002→원격8002 임베딩을 기본으로 사용한다. 따라서 합성 fixture8000과 충돌하지 않는다. 실제 데카트론 설정은 fixture 서버를 사용하지 않는다. 시작/종료 구현은 `gpu_session.py`, 연결은 `cli.py`·`monitor.py`다. SSH ControlMaster/ControlPath를 지원하는 로컬 OpenSSH가 필요하다. Windows의 실제 SSH/Slurm 동작은 미검증이며 CI는 가짜 transport로 수명주기를 검증한다.

## 인증

비밀번호는 OpenSSH의 사용자 터미널 프롬프트에서 입력한다. 앱·환경 변수·JSON·요청·로그에 보관하지 않는다. 실행 중에는 인증한 login master를 ProxyCommand로 재사용하고 agent forwarding을 켜지 않는다. 무인 시작은 아래 SSH 키 인증 또는 macOS 키체인 비밀번호 저장 방식을 선택한다. 초기 BatchMode 점검은 Permission denied였다. 이후 사용자 터미널의 비밀번호 인증으로 실제 Qwen health200과 소유 Slurm 작업 반환을 확인했다. 키 전용 인증은 최초 등록 후 별도로 검증한다. 기본 런타임은 키 등록을 수행하지 않는다. 아래 최초 설정 명령만 사용자가 명시 실행할 때 공개 키를 등록한다.

## 임베딩 최초 준비

기존 Qwen `.venv-dis01`과 분리해 **원격 `~/persona-llm`에서 최초 한 번** 준비한다. 로그인/계산 노드 HOME 공유와 인터넷 접근을 확인한다. 로컬 대시보드 환경에는 sentence-transformers/torch를 추가하지 않는다.

```sh
cd ~/persona-llm
python3 -m venv .venv-persona-embedding
.venv-persona-embedding/bin/python -m pip install sentence-transformers
HF_HUB_OFFLINE=0 .venv-persona-embedding/bin/python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", device="cpu", trust_remote_code=False)'
.venv-persona-embedding/bin/python -m pip freeze > .persona-embedding-packages.txt
```

이 명령은 이번 작업에서 원격 실행하지 않았다. 설치 버전·모델 캐시·실제 CUDA 메모리 여유를 원격에서 확인해야 한다. 예시 모델은 [공식 모델 카드](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)의 다국어384차원 모델이며 최대 길이128 token이다. 긴 기억은 모델 창에서 잘리므로 Qwen 문맥 길이와 혼동하지 않는다. 실제 한국어 검색 품질·U 원본 embedding 모델과의 동등 성능은 검증하지 않았다.

자동 시작은 `embedding_server.py`를 원격 `$HOME/.persona-gpu/`에 고유 이름으로 전달한다. 서버는 CUDA·local_files_only로 모델을 읽고 127.0.0.1에만 bind한다. 모델 다운로드·유료 API·CPU fallback은 시작 경로에 없다. 별도 Python 프로세스로 Qwen과 같은 Slurm 할당 안에서 실행하고 한쪽이 종료되면 다른 쪽도 정리한다. 로그/helper는 원격 `.persona-gpu/`에 남으며 기존 api_server.py를 수정하지 않는다.

`GET /health`는 모델·차원·최대 길이·장치를 반환한다. `POST /v1/embeddings`는 model/input 문자열 배열을 받아 index/embedding과 tokenize attention-mask의 실제 입력 token 수를 반환한다. 정규화·query prefix를 추가하지 않는다. [SentenceTransformer API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html)를 사용한다. 실패 응답은 입력 본문을 포함하지 않는다.

## 소유권과 복구

- 대시보드는 5초마다 채팅·임베딩 health를 확인하고 batch/compare 직전에도 검사한다. 소유 작업 ID·고유 이름·RUNNING·지정 노드를 확인한 뒤 없어진 SSH master/터널을 복구한다. 이 검사는 모델 생성을 하지 않으며 새 Slurm 작업을 만들지 않는다. 할당 만료·서버 종료·복구 실패는 `gpu_connection`과 `providers.gpu=false`로 드러내고 새 실행을 막는다. 종료 때 로그인 master가 끊겼으면 재인증해 소유 작업을 반환한다. [오류 대응·검증 매뉴얼](../model-json-operations.md)을 따른다.

- 이름은 실행별 UUID다. 사용자 전체 작업이나 기존 수동 작업을 취소하지 않는다.
- sbatch 응답을 잃으면 해당 사용자+고유 이름으로만 ID를 복구한다.
- 로컬 `runs/private/gpu-session-state.json`은 배타적으로 생성한다. job ID·고유 이름과 임베딩 probe 메타데이터를 저장하고 실제 반환이 확인된 뒤 삭제한다.
- 이전 미반환 기록이 있으면 새 할당을 막는다. 운영자가 같은 사용자/이름의 작업을 확인·반환한 뒤 상태를 정리한다. 단순히 파일만 지워 할당을 숨기지 않는다.
- 자원 할당은 srun --pty 대화형 셸 대신 동일 자원 옵션의 sbatch를 사용한다. 서버 실행/종료를 작업 ID로 관리하기 위해서다. 이 클러스터의 sbatch 정책은 실제 인증 후 확인해야 한다.

근거: [sbatch](https://slurm.schedmd.com/sbatch.html), [squeue](https://slurm.schedmd.com/squeue.html), [scancel](https://slurm.schedmd.com/scancel.html), [OpenSSH](https://man.openbsd.org/ssh).

## SSH 키 최초 설정과 이후 자동 인증

사용자 터미널에서 최초 한 번 실행한다. 실제 접속 설정은 runs/private/gpu-session.json에 둔다.

```sh
python3 -m uxagent gpu-key-setup
```

- 전용 키 ~/.ssh/uxagent_gpu_ed25519를 만들거나 기존 완전한 쌍을 재사용한다. 암호는 OpenSSH 터미널에서 입력한다. 저장소 안 키·불완전한 쌍·공개 키 symlink·열린 POSIX 개인 키 권한은 거부한다. 기존 키·전역 SSH config를 덮어쓰지 않는다.
- macOS는 시스템 ssh-add --apple-use-keychain으로 agent와 OS Keychain을 사용한다. 다른 POSIX 환경은 기존 agent 또는 전용 agent를 쓴다. 앱은 개인 키 본문·암호를 읽지 않는다. 공개 키만 읽고 해당 키의 agent 서명도 확인한다.
- 로그인 서버에 공개 키를 추가한다. authorized_keys는 잠금 후 추가하고 기존 행을 보존한다. 같은 키가 제한 옵션과 함께 있어도 무제한 사본을 추가하지 않는다. symlink 대상이나 관리자 SSH 정책을 변경하지 않는다.
- 계산 노드 접속에 필요한 임시 Slurm 할당을 만든다. 모델·임베딩·포트 전달 없이 최대600초 대기 프로세스만 실행한다. 계산 노드에도 공개 키를 등록하며 HOME 공유 시 중복 추가하지 않는다.
- 양쪽에 ControlPath=none 새 연결로 publickey 전용·BatchMode 인증을 확인한다. 자기 임시 할당을 반환한 뒤에만 private config의 identity_file·identity_agent·ssh_batch_mode=true를 저장한다. 실패 시 활성화하지 않는다. 이미 추가한 공개 키는 자동 삭제하지 않으며 재실행은 중복 등록하지 않는다.

최초 설정에는 키 암호와 서버 비밀번호 입력이 필요하다. 이후 대시보드는 전용 키와 agent를 사용하고 비밀번호를 앱에 받아 fallback하지 않는다. 운영자가 공개 키 인증을 허용하고 agent/Keychain이 사용 가능해야 한다. 비대화형 새 키 생성과 암호 등록은 거부한다.

POSIX 로그인 세션 종료·agent 재시작 후 필요하면 키만 다시 등록한다. 이 명령은 원격 공개 키 재등록이나 GPU 할당을 하지 않는다.

```sh
python3 -m uxagent gpu-key-unlock
```

macOS의 해제된 Keychain에서는 저장한 키 암호를 사용할 수 있다. 사용자 지정 키는 gpu-key-setup --identity-file로 지정하며 저장소 밖이어야 한다. Windows는 기존 agent 서비스가 필요하고 실제 SSH/Slurm은 미검증이다. 소켓/PID 설정은 비공개 파일에만 둔다. 런타임은 공개 키 등록을 수행하지 않는다.

근거: [ssh-add](https://man.openbsd.org/ssh-add), [IdentityFile/IdentityAgent/BatchMode](https://man.openbsd.org/ssh_config), [macOS 시스템 ssh-add·Keychain](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent).


## macOS 서버 비밀번호 저장과 자동 접속

사용자 추가 결정: 매 실행마다 입력하지 않고 저장한 서버 비밀번호를 사용한다. macOS에서는 평문 파일 대신 로그인 키체인에 두 서버의 비밀번호를 저장한다. 키 등록과 별개의 선택 경로이며 원격 authorized_keys를 수정하지 않는다.

```sh
python3 -m uxagent gpu-password-setup
python3 -m uxagent dashboard
```

1. 최초 명령은 사용자 터미널에서 로그인 서버·계산 서버 비밀번호와 각각의 확인 값을 숨김 입력으로 받는다. 앞서 SSH에 입력한 비밀번호는 회수/재사용할 수 없어 최초 저장 입력은 필요하다.
2. Security.framework를 직접 호출해 service=uxagent.gpu.ssh, account=user@host:port의 키체인 항목에 저장/갱신한다. 비밀번호를 명령 인자·파일·JSON·환경 변수·앱 로그에 넣지 않는다. private config에는 ssh_password_store=macos-keychain만 저장한다.
3. dashboard의 각 SSH master가 임시 askpass 실행 파일과 비밀이 없는 account 식별자를 사용한다. helper가 키체인에서 값을 읽어 OpenSSH 전용 pipe에만 전달한다. login master는 jump에 재사용하며 agent forwarding은 켜지 않는다.
4. 이 모드는 BatchMode=no, password/keyboard-interactive, 인증 프롬프트1회로 동작한다. 비밀번호와 다른 prompt·빈 항목·키체인 오류는 자동 응답하지 않는다. host key 검증은 StrictHostKeyChecking=yes로 강제한다. 이미 신뢰한 호스트가 필요하며 알 수 없는/변경된 host key를 자동 승인하지 않는다.
5. macOS 로그인 키체인이 잠겼거나 접근 허가가 필요하면 OS가 해제/허가를 요구할 수 있다. OTP/MFA·비표준 prompt·비밀번호 만료 변경은 자동화 범위가 아니다. 다른 OS에서는 이 설정을 명시 오류로 거부한다.
6. 서버 비밀번호 변경 후 같은 setup 명령으로 갱신한다. 저장/조회는 인증 성공을 의미하지 않는다. 실제 health와 소유 Slurm 반환은 별도로 검증한다. 비밀번호를 채팅·이슈·공유 문서에 보내지 않는다.

근거: [Apple Keychain 저장 API](https://developer.apple.com/documentation/security/seckeychainaddgenericpassword(_:_:_:_:_:_:_:_:)), [Keychain 조회 API](https://developer.apple.com/documentation/security/seckeychainfindgenericpassword(_:_:_:_:_:_:_:_:)), [OpenSSH SSH_ASKPASS_REQUIRE](https://man.openbsd.org/ssh).

2026-10-18 실제 검증: macOS 키체인 자격증명과 비공개 설정으로 대시보드를 시작했다. Qwen `/health` HTTP200/status=ok/model=persona-qwen, sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2의 `cuda:0`·384차원 및 벡터 probe를 통과했고 Slurm 작업19357을 반환했다. 검증용 번들과 wrapper는 원격 사용자 홈·노드 임시 디스크에 두며 비밀번호·키체인 값은 출력하거나 저장소에 넣지 않았다. 생성형 Qwen 과업 성공은 검증하지 않았다.

2026-10-20 실제 과업 예산: 공개 데카트론 등록 study는 실제394.70초 측정 후600초를 허용한다. 기본 대시보드에서 등록 과업을 GPU로 실행할 때만 데모의300초 대신 이 제한을 쓴다. 사용자 지정 study의 명시 시간 한도는 유지한다. 이는 실행 시간 설정이며 GPU 처리속도 향상으로 보고하지 않는다.

## 2026-10-21 동일 채팅 토크나이저 서비스

기본 tokenizer_enabled=true, tokenizer_local_port/remote_port=8003으로 CPU 보조 서비스를 추가한다. 기존 server_script의 모델 경로/이름을 AST로 읽고 같은 chat venv에서 실행하며 chat/embedding/토큰 계산의 어느 자식이 끝나도 소유 Slurm 작업을 정리한다. 추가 GPU는 요청하지 않는다. 준비 시 모델명/한도/fingerprint와 CPU 계산 probe를 확인하고 PERSONA_QWEN_TOKENIZER_URL을 실행기에 전달한다. health 감시·터널 복구·포트 충돌 검사와 종료 환경 복원에 포함한다. 토큰 계산 서비스가 필요한 수동 모드는 별도로 URL을 설정해야 하며 managed 기본과 구분한다.
