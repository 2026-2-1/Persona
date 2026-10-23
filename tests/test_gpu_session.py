import json
import subprocess
import shlex
import socket

import pytest

from uxagent.gpu_session import GpuSession, GpuSessionConfig


def config():
    return GpuSessionConfig(login_host='login.test', compute_host='node.test', user='user',
        partition='p02', node='DIS01', gres='gpu:A6000:1', cpus=4, memory='48G', walltime='04:00:00', tokenizer_enabled=False)


class Transport:
    def __init__(self): self.calls=[]; self.fail_health=False; self.name=None; self.job_id='12345'
    def run(self, args, **kwargs):
        self.calls.append((args, kwargs))
        command=args[-1]
        if 'sbatch ' in command:
            self.name=next(arg.split('=',1)[1] for arg in shlex.split(command) if arg.startswith('--job-name='))
            output='12345\n'
        elif '--format=%i|%j' in command: output=(self.job_id+'|'+self.name) if self.name else ''
        elif 'squeue ' in command: output=''
        else: output=''
        return subprocess.CompletedProcess(args, 0, output, '')


def session(tmp_path, monkeypatch, transport):
    monkeypatch.setattr('uxagent.gpu_session.subprocess.run', transport.run)
    monkeypatch.setattr(GpuSession, '_check_ports', lambda self: None)
    monkeypatch.setattr(GpuSession, '_wait_running', lambda self: None)
    monkeypatch.setattr(GpuSession, '_wait_health', lambda self: None)
    return GpuSession(config(), tmp_path/'session.json')


def test_owned_allocation_and_tunnel_are_released_on_close(tmp_path, monkeypatch):
    transport=Transport(); manager=session(tmp_path, monkeypatch, transport)
    manager.start()
    assert manager.job_id=='12345'
    assert json.loads(manager.state_path.read_text())['job_id']=='12345'
    assert any('sbatch --parsable' in args[-1] and '--gres=gpu:A6000:1' in args[-1] for args, _ in transport.calls)
    assert any('127.0.0.1:8001:127.0.0.1:8000' in args for args, _ in transport.calls)
    manager.close(); manager.close()
    cancels=[args[-1] for args, _ in transport.calls if 'scancel ' in args[-1]]
    assert cancels==['scancel 12345']
    assert not manager.state_path.exists()
    assert all('password' not in str(kwargs).lower() for _, kwargs in transport.calls)


def test_startup_failure_rolls_back_only_its_job(tmp_path, monkeypatch):
    transport=Transport(); manager=session(tmp_path, monkeypatch, transport)
    def fail(self): raise RuntimeError('health timeout')
    monkeypatch.setattr(GpuSession, '_wait_health', fail)
    with pytest.raises(RuntimeError, match='health timeout'): manager.start()
    assert any(args[-1]=='scancel 12345' for args, _ in transport.calls)
    assert not manager.state_path.exists()


def test_failed_release_keeps_recovery_record(tmp_path, monkeypatch):
    transport=Transport(); manager=session(tmp_path, monkeypatch, transport); manager.start()
    original=transport.run
    def fail(args, **kwargs):
        if args[-1]=='scancel 12345' or '--format=%i' in args[-1]: raise RuntimeError('network unavailable')
        return original(args, **kwargs)
    monkeypatch.setattr('uxagent.gpu_session.subprocess.run', fail)
    with pytest.raises(RuntimeError, match='GPU 작업 반환'): manager.close()
    assert json.loads(manager.state_path.read_text())['job_id']=='12345'
    other=GpuSession(config(), manager.state_path)
    with pytest.raises(RuntimeError, match='미반환'): other.start()


def test_remote_script_uses_supplied_environment_and_bounded_allocation():
    manager=GpuSession(config())
    script=manager._script()
    assert 'HF_HUB_OFFLINE=1' in script and '.venv-dis01/bin/activate' in script
    assert 'exec python -u api_server.py' in script
    command=manager._submit_command()
    assert '--time=04:00:00' in command and '--nodelist=DIS01' in command
    assert '--nodes=1' in command


def test_tokenizer_child_uses_chat_environment_and_is_cleaned_up_with_owned_job(tmp_path, monkeypatch):
    transport = Transport()
    manager = session(tmp_path, monkeypatch, transport)
    manager.config = manager.config.model_copy(update={'tokenizer_enabled': True})
    monkeypatch.setattr(GpuSession, '_wait_tokenizer_health', lambda self: None)
    monkeypatch.setenv('PERSONA_QWEN_TOKENIZER_URL', 'http://127.0.0.1:9003/tokenize')
    script = manager._script()
    assert 'python -u "$HOME/.persona-gpu/' in script and '-tokenizer.py" --server-script api_server.py --port 8003' in script
    assert 'kill "$tokenizer_pid"' in script and 'wait -n "$chat_pid" "$tokenizer_pid"' in script
    manager.start()
    import os
    assert os.environ['PERSONA_QWEN_TOKENIZER_URL'] == 'http://127.0.0.1:8003/tokenize'
    assert any('127.0.0.1:8003:127.0.0.1:8003' in args for args, _ in transport.calls)
    assert any('-tokenizer.py' in args[-1] and 'input' in kwargs for args, kwargs in transport.calls)
    manager.close()
    assert os.environ['PERSONA_QWEN_TOKENIZER_URL'] == 'http://127.0.0.1:9003/tokenize'


def test_tokenizer_port_conflict_is_rejected_before_remote_changes():
    manager = GpuSession(config().model_copy(update={'tokenizer_enabled': True, 'tokenizer_local_port': 8001}))
    with pytest.raises(ValueError, match='포트'):
        manager._check_ports()


def test_config_rejects_secrets_and_unsafe_hosts():
    from pydantic import ValidationError
    with pytest.raises(ValidationError): GpuSessionConfig(**{**config().model_dump(), 'password':'not-allowed'})
    with pytest.raises(ValidationError): GpuSessionConfig(**{**config().model_dump(), 'login_host':'-oProxyCommand=bad'})


def test_lost_submission_reply_recovers_unique_job_and_cancels_it(tmp_path, monkeypatch):
    transport=Transport(); manager=session(tmp_path, monkeypatch, transport)
    original=transport.run
    def lost_reply(args, **kwargs):
        if 'sbatch ' in args[-1]:
            transport.name=manager.job_name
            transport.job_id='34567'
            raise subprocess.TimeoutExpired(args, 60)
        if 'squeue ' in args[-1] and '--format=%i' in args[-1] and manager.job_id is None:
            assert manager.job_name in args[-1]
            return subprocess.CompletedProcess(args, 0, '34567', '')
        return original(args, **kwargs)
    monkeypatch.setattr('uxagent.gpu_session.subprocess.run', lost_reply)
    with pytest.raises(subprocess.TimeoutExpired): manager.start()
    assert any(args[-1]=='scancel 34567' for args, _ in transport.calls)
    assert not manager.state_path.exists()


def test_dashboard_interrupt_returns_gpu_and_closes_http_server(tmp_path, monkeypatch):
    import uxagent.monitor as monitor
    events=[]
    class GPU:
        def __init__(self, config): pass
        def start(self): events.append('gpu_start')
        def close(self): events.append('gpu_close')
    class Server:
        def __init__(self, *args): pass
        def serve_forever(self): events.append('serve'); raise KeyboardInterrupt
        def server_close(self): events.append('http_close')
    monkeypatch.setattr('uxagent.gpu_session.GpuSession', GPU)
    monkeypatch.setattr(monitor, 'ThreadingHTTPServer', Server)
    monkeypatch.setattr(monitor.Dashboard, 'connect', lambda *a, **kw: events.append('connect'))
    path=tmp_path/'gpu.json'; path.write_text(config().model_dump_json())
    monitor.serve_dashboard(gpu_config=path)
    assert events==['gpu_start','connect','serve','http_close','gpu_close']


def test_dashboard_connection_failure_also_returns_gpu(tmp_path, monkeypatch):
    import uxagent.monitor as monitor
    events=[]
    class GPU:
        def __init__(self, config): pass
        def start(self): events.append('start')
        def close(self): events.append('close')
    class Server:
        def __init__(self,*args): pass
        def server_close(self): events.append('server_close')
    monkeypatch.setattr('uxagent.gpu_session.GpuSession', GPU)
    monkeypatch.setattr(monitor, 'ThreadingHTTPServer', Server)
    def fail(*a,**kw): raise ValueError('model connection failed')
    monkeypatch.setattr(monitor.Dashboard, 'connect', fail)
    path=tmp_path/'gpu.json';path.write_text(config().model_dump_json())
    with pytest.raises(ValueError, match='model connection failed'): monitor.serve_dashboard(gpu_config=path)
    assert events==['start','server_close','close']


def test_mismatched_owned_job_is_never_cancelled(tmp_path, monkeypatch):
    transport=Transport(); manager=session(tmp_path, monkeypatch, transport); manager.start()
    transport.name='some-other-session'
    with pytest.raises(RuntimeError, match='GPU 작업 반환'): manager.close()
    assert not any('scancel ' in args[-1] for args, _ in transport.calls)
    assert manager.state_path.exists()


def test_embedding_starts_separately_and_environment_is_restored(tmp_path, monkeypatch):
    transport=Transport(); manager=session(tmp_path, monkeypatch, transport)
    manager.config=manager.config.model_copy(update={'embedding_model':'embedding-model'})
    monkeypatch.setattr(GpuSession,'_wait_embedding_health',lambda self:None)
    monkeypatch.setenv('PERSONA_QWEN_API_URL','http://127.0.0.1:9991/v1/chat/completions')
    monkeypatch.setenv('PERSONA_EMBEDDING_API_URL','http://127.0.0.1:9992/v1/embeddings')
    manager.start()
    import os
    assert os.environ['PERSONA_EMBEDDING_API_URL']=='http://127.0.0.1:8002/v1/embeddings'
    assert any('127.0.0.1:8002:127.0.0.1:8002' in args for args, _ in transport.calls)
    script=next(kwargs['input'] for args, kwargs in transport.calls if 'sbatch ' in args[-1])
    assert '.venv-persona-embedding/bin/python' in script and 'wait -n' in script
    manager.close()
    assert os.environ['PERSONA_QWEN_API_URL'].endswith('9991/v1/chat/completions')
    assert os.environ['PERSONA_EMBEDDING_API_URL'].endswith('9992/v1/embeddings')


def test_authentication_only_allocation_does_not_start_models_or_forward_ports(tmp_path, monkeypatch):
    transport=Transport();manager=session(tmp_path,monkeypatch,transport)
    def forbidden(*args): raise AssertionError('model/port operations forbidden in enrollment')
    monkeypatch.setattr(GpuSession,'_check_ports',forbidden)
    monkeypatch.setattr(GpuSession,'_wait_health',forbidden)
    manager.config=manager.config.model_copy(update={'embedding_model':'not-needed'})
    manager.start(authentication_only=True)
    script=next(kwargs['input'] for args,kwargs in transport.calls if 'sbatch ' in args[-1])
    assert 'exec sleep 600' in script and 'python' not in script
    assert not any('-L' in args for args,_ in transport.calls)
    manager.close()
    assert any(args[-1]=='scancel 12345' for args,_ in transport.calls)


def test_lost_tunnel_is_restored_without_submitting_or_cancelling_job(tmp_path, monkeypatch):
    transport = Transport()
    manager = session(tmp_path, monkeypatch, transport)
    manager.start()
    transport.calls.clear()
    healthy = False
    def health():
        if not healthy:
            raise OSError('connection refused')
    def restore():
        nonlocal healthy
        healthy = True
    monkeypatch.setattr(manager, 'check_health', health, raising=False)
    monkeypatch.setattr(manager, '_open_compute', restore, raising=False)
    monkeypatch.setattr(manager, '_control_alive', lambda *a: False, raising=False)
    # A plain bind probe can reject TIME_WAIT after this session's listener
    # exited. OpenSSH uses its own bind flags and ExitOnForwardFailure instead.
    def stale_port_probe():
        raise RuntimeError('TIME_WAIT is not an active listener')
    monkeypatch.setattr(manager, '_check_ports', stale_port_probe)
    original = transport.run
    def run(args, **kwargs):
        if '--format=%i|%j|%T|%N' in args[-1]:
            return subprocess.CompletedProcess(args, 0, f'12345|{manager.job_name}|RUNNING|DIS01', '')
        return original(args, **kwargs)
    monkeypatch.setattr('uxagent.gpu_session.subprocess.run', run)
    manager.ensure_ready()
    assert healthy and manager.job_id == '12345'
    assert not any('sbatch ' in args[-1] or 'scancel ' in args[-1] for args, _ in transport.calls)
    manager.close()


@pytest.mark.parametrize('identity', ['', '12345|someone-else|RUNNING|DIS01'])
def test_recovery_does_not_reuse_missing_or_foreign_allocation(tmp_path, monkeypatch, identity):
    transport = Transport()
    manager = session(tmp_path, monkeypatch, transport)
    manager.start()
    monkeypatch.setattr(manager, 'check_health', lambda: (_ for _ in ()).throw(OSError()), raising=False)
    original = transport.run
    def run(args, **kwargs):
        if '--format=%i|%j|%T|%N' in args[-1]:
            return subprocess.CompletedProcess(args, 0, identity, '')
        return original(args, **kwargs)
    monkeypatch.setattr('uxagent.gpu_session.subprocess.run', run)
    with pytest.raises(RuntimeError, match='할당|소유'):
        manager.ensure_ready()
    manager.close()


def test_release_reauthenticates_if_login_master_disappeared(tmp_path, monkeypatch):
    transport = Transport()
    manager = session(tmp_path, monkeypatch, transport)
    manager.start()
    monkeypatch.setattr(manager, '_control_alive', lambda *a: False, raising=False)
    transport.calls.clear()
    manager.close()
    assert any('-M' in args and args[-1].endswith('@login.test') for args, _ in transport.calls)
    assert not manager.state_path.exists()


def test_port_probe_rejects_listener_but_accepts_its_closed_connections():
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        port = listener.getsockname()[1]
        manager = GpuSession(config().model_copy(update={'local_port': port}))
        with pytest.raises(RuntimeError, match='사용 중'):
            manager._check_ports()
        with socket.create_connection(('127.0.0.1', port)) as client:
            accepted, _ = listener.accept()
            accepted.close()
            assert client.recv(1) == b''
    manager._check_ports()
