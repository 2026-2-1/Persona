"""One-time public-key enrollment. Passwords/private-key bytes stay in OpenSSH."""
from __future__ import annotations

import base64
import inspect
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import uuid

from .gpu_session import GpuSession, GpuSessionConfig


def install_public_key(directory, public_key):
    """Append only, including when an existing copy has restrictive options."""
    import base64
    import fcntl
    import os
    from pathlib import Path
    parts = public_key.strip().split()
    if len(parts) < 2 or parts[0] != 'ssh-ed25519':
        raise ValueError('invalid public key')
    base64.b64decode(parts[1], validate=True)
    directory = Path(directory)
    target = directory / 'authorized_keys'
    if directory.is_symlink() or target.is_symlink():
        raise ValueError('refusing SSH directory/authorized_keys symlink')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(target, os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        with os.fdopen(descriptor, 'r+b', closefd=False) as handle:
            original = handle.read()
            for line in original.decode('utf-8', 'replace').splitlines():
                if line.lstrip().startswith('#'):
                    continue
                tokens = line.split()
                if any(tokens[i:i+2] == parts[:2] for i in range(len(tokens)-1)):
                    return {'added':False}
            handle.seek(0, os.SEEK_END)
            if original and not original.endswith(b'\n'):
                handle.write(b'\n')
            handle.write((' '.join(parts[:2]) + ' persona-gpu\n').encode())
            handle.flush()
            os.fsync(handle.fileno())
        return {'added':True}
    finally:
        os.close(descriptor)


def prepare_identity(key_path, *, repo_root):
    key = Path(key_path).expanduser().resolve()
    if key.is_relative_to(Path(repo_root).resolve()):
        raise ValueError('개인 키는 저장소 밖 ~/.ssh에 보관해야 합니다')
    public = key.with_name(key.name + '.pub')
    if public.is_symlink():
        raise ValueError('공개 키 파일의 symlink는 지원하지 않습니다')
    if key.exists() != public.exists():
        raise ValueError('기존 개인 키/공개 키 쌍이 불완전합니다. 기존 파일을 덮어쓰지 않습니다')
    if not key.exists():
        if not sys.stdin.isatty():
            raise ValueError('새 SSH 키 생성은 암호를 직접 입력할 사용자 터미널에서 실행하세요')
        key.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        print('전용 SSH 키를 생성합니다. 키 암호는 터미널에서 입력하세요.', flush=True)
        result = subprocess.run(['ssh-keygen','-t','ed25519','-a','64','-f',str(key),'-C','persona-gpu'], check=False)
        if result.returncode:
            raise RuntimeError('SSH 키 생성을 완료하지 못했습니다')
    if os.name != 'nt' and stat.S_IMODE(key.stat().st_mode) & 0o077:
        raise ValueError('개인 키 권한을 사용자만 읽을 수 있도록 설정하세요 (chmod 600)')
    # Ask OpenSSH to validate the public file. Never open/read the private file.
    result = subprocess.run(['ssh-keygen','-l','-f',str(public)], capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError('공개 키 형식을 확인하지 못했습니다')
    text = public.read_text(encoding='utf-8').strip()
    parts = text.split()
    if len(parts) < 2 or parts[0] != 'ssh-ed25519':
        raise ValueError('전용 ed25519 공개 키가 필요합니다')
    base64.b64decode(parts[1], validate=True)
    return ' '.join(parts[:2]) + ' persona-gpu'


def _write_private_json(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_identity(key_path, *, state_dir, identity_agent=None):
    """Use the OS agent, or remember a dedicated agent socket without eval."""
    key = Path(key_path).expanduser().resolve()
    if not sys.stdin.isatty():
        raise ValueError('키 암호 등록은 사용자 터미널에서 실행하세요')
    environment = dict(os.environ)
    if identity_agent and Path(identity_agent).is_socket():
        environment['SSH_AUTH_SOCK'] = identity_agent
    agent_state = Path(state_dir) / 'gpu-ssh-agent.json'
    add = '/usr/bin/ssh-add' if sys.platform == 'darwin' else 'ssh-add'

    def available():
        result = subprocess.run([add,'-l'], env=environment, capture_output=True, check=False)
        return result.returncode in (0, 1)

    if not available() and agent_state.exists():
        saved = json.loads(agent_state.read_text())
        socket_path = saved.get('socket')
        if isinstance(socket_path, str) and Path(socket_path).is_socket():
            environment['SSH_AUTH_SOCK'] = socket_path
    if not available():
        if os.name == 'nt':
            raise RuntimeError('Windows OpenSSH ssh-agent 서비스를 먼저 시작하세요')
        result = subprocess.run(['ssh-agent','-s'], capture_output=True, text=True, check=False)
        socket_match = re.search(r'^SSH_AUTH_SOCK=([^;\n]+);', result.stdout, re.M)
        pid_match = re.search(r'^SSH_AGENT_PID=([0-9]+);', result.stdout, re.M)
        if result.returncode or not socket_match or not pid_match:
            raise RuntimeError('ssh-agent 시작을 확인하지 못했습니다')
        environment['SSH_AUTH_SOCK'] = socket_match.group(1)
        _write_private_json(agent_state, {'socket':socket_match.group(1), 'pid':int(pid_match.group(1))})
    args = [add]
    if sys.platform == 'darwin':
        args.append('--apple-use-keychain')
    args.append(str(key))
    # Passphrase prompts belong to the terminal / macOS Keychain, not this app.
    if subprocess.run(args, env=environment, check=False).returncode:
        raise RuntimeError('SSH 키의 agent 등록을 완료하지 못했습니다')
    if subprocess.run([add,'-T',str(key)+'.pub'], env=environment,
                      capture_output=True, check=False).returncode:
        raise RuntimeError('agent에서 해당 키의 서명 사용을 확인하지 못했습니다')
    return environment.get('SSH_AUTH_SOCK')


def _install_command():
    program = inspect.getsource(install_public_key) + (
        '\nimport json, sys\nfrom pathlib import Path\n'
        "print(json.dumps(install_public_key(Path.home()/'.ssh', json.load(sys.stdin)['public_key'])))\n")
    return 'python3 -c ' + shlex.quote(program)


def verify_key_auth(config, host):
    manager = GpuSession(config.model_copy(update={'ssh_batch_mode':True}))
    # Explicitly prohibit multiplex reuse and other authentication methods.
    def base(destination):
        return ['ssh','-o','ControlMaster=no','-o','ControlPath=none',
                '-o','PreferredAuthentications=publickey','-o','PasswordAuthentication=no',
                '-o','BatchMode=yes','-o','ConnectTimeout=10',
                *manager.identity_options(), '-p',str(config.ssh_port),f'{config.user}@{destination}']
    args = base(host)
    if host == config.compute_host:
        proxy = shlex.join(base(config.login_host)[:-1] + ['-W','%h:%p',f'{config.user}@{config.login_host}'])
        args = args[:-1] + ['-o','ProxyCommand='+proxy,args[-1]]
    result = subprocess.run(args + ['true'], capture_output=True, timeout=config.ssh_timeout, check=False)
    if result.returncode:
        raise RuntimeError('새 SSH 키 전용 연결 검증에 실패했습니다. 서버 공개 키 정책을 확인하세요')


def _read_private_config(config_path, repo_root):
    path = Path(config_path).expanduser().resolve()
    root = Path(repo_root).resolve()
    if path.is_relative_to(root) and not path.is_relative_to(root/'runs/private'):
        raise ValueError('실제 SSH 설정은 저장소 밖 또는 runs/private에 보관하세요')
    original = path.read_bytes()
    config = GpuSessionConfig.model_validate_json(original)
    return path, original, config


def setup_gpu_key(config_path, *, key_path='~/.ssh/uxagent_gpu_ed25519', repo_root=None):
    root = Path.cwd() if repo_root is None else Path(repo_root)
    path, original, config = _read_private_config(config_path, root)
    key = Path(key_path).expanduser().resolve()
    public_key = prepare_identity(key, repo_root=root)
    agent = load_identity(key, state_dir=path.parent, identity_agent=config.identity_agent)
    bootstrap = config.model_copy(update={'identity_file':str(key),'identity_agent':agent,
        'ssh_batch_mode':False,'embedding_model':None,'ssh_timeout':300})
    manager = GpuSession(bootstrap, path.parent/'gpu-key-setup-state.json')
    payload = json.dumps({'public_key':public_key})
    command = _install_command()
    try:
        manager.open_login()
        manager._remote(command, input=payload)
        verify_key_auth(bootstrap, config.login_host)
        manager.start(authentication_only=True)
        manager.install_compute_key(command, payload)
        verify_key_auth(bootstrap, config.compute_host)
    finally:
        manager.close()
    if path.read_bytes() != original:
        raise RuntimeError('설정 파일이 작업 중 바뀌어 자동 인증 설정을 저장하지 않았습니다')
    updated = config.model_dump()
    updated.update(identity_file=str(key), identity_agent=agent, ssh_batch_mode=True)
    _write_private_json(path, updated)
    print('두 서버의 새 키 인증과 테스트 할당 반환을 확인했습니다. 무인 SSH 인증을 활성화했습니다.', flush=True)


def unlock_gpu_key(config_path, *, repo_root=None):
    root = Path.cwd() if repo_root is None else Path(repo_root)
    path, original, config = _read_private_config(config_path, root)
    if not config.identity_file:
        raise ValueError('먼저 gpu-key-setup을 실행하세요')
    agent = load_identity(config.identity_file, state_dir=path.parent, identity_agent=config.identity_agent)
    if path.read_bytes() != original:
        raise RuntimeError('설정 파일이 작업 중 바뀌었습니다')
    updated = config.model_dump(); updated['identity_agent'] = agent
    _write_private_json(path, updated)
    print('SSH 키 agent 등록을 확인했습니다.', flush=True)
