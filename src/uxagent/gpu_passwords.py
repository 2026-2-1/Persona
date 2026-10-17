"""macOS Keychain storage and OpenSSH askpass bridge; no plaintext credential files."""
from __future__ import annotations

import ctypes
import getpass
import os
from pathlib import Path
import re
import shlex
import sys

SERVICE = 'uxagent.gpu.ssh'


def _security():
    if sys.platform != 'darwin':
        raise RuntimeError('이 비밀번호 저장 방식은 macOS 키체인 전용입니다')
    lib = ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security')
    pointer = ctypes.c_void_p
    uint = ctypes.c_uint32
    lib.SecKeychainAddGenericPassword.argtypes = [pointer,uint,ctypes.c_char_p,uint,ctypes.c_char_p,uint,pointer,ctypes.POINTER(pointer)]
    lib.SecKeychainAddGenericPassword.restype = ctypes.c_int32
    lib.SecKeychainFindGenericPassword.argtypes = [pointer,uint,ctypes.c_char_p,uint,ctypes.c_char_p,ctypes.POINTER(uint),ctypes.POINTER(pointer),ctypes.POINTER(pointer)]
    lib.SecKeychainFindGenericPassword.restype = ctypes.c_int32
    lib.SecKeychainItemModifyAttributesAndData.argtypes = [pointer,pointer,uint,pointer]
    lib.SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32
    lib.SecKeychainItemFreeContent.argtypes = [pointer,pointer]
    lib.SecKeychainItemFreeContent.restype = ctypes.c_int32
    return lib


def store_password(service, account, password):
    """Write via Security.framework, never command arguments, env or files."""
    lib = _security()
    service, account, data = service.encode(), account.encode(), password.encode()
    result = lib.SecKeychainAddGenericPassword(None,len(service),service,len(account),account,len(data),data,None)
    if result == -25299:  # errSecDuplicateItem: update the exact service/account.
        item = ctypes.c_void_p()
        result = lib.SecKeychainFindGenericPassword(None,len(service),service,len(account),account,None,None,ctypes.byref(item))
        if result == 0:
            try:
                result = lib.SecKeychainItemModifyAttributesAndData(item,None,len(data),data)
            finally:
                core = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
                core.CFRelease.argtypes = [ctypes.c_void_p]
                core.CFRelease.restype = None
                core.CFRelease(item)
    if result:
        raise RuntimeError(f'키체인 저장 실패 (OSStatus {result})')


def read_password(service, account):
    lib = _security()
    service, account = service.encode(), account.encode()
    length, data = ctypes.c_uint32(), ctypes.c_void_p()
    result = lib.SecKeychainFindGenericPassword(None,len(service),service,len(account),account,ctypes.byref(length),ctypes.byref(data),None)
    if result:
        raise RuntimeError(f'키체인 읽기 실패 (OSStatus {result})')
    try:
        return ctypes.string_at(data,length.value).decode('utf-8')
    finally:
        lib.SecKeychainItemFreeContent(None,data)


def account_for(config, host):
    return f'{config.user}@{host}:{config.ssh_port}'


def setup_passwords(config_path, *, repo_root=None):
    from .gpu_ssh_keys import _read_private_config, _write_private_json
    if sys.platform != 'darwin':
        raise RuntimeError('이 비밀번호 저장 방식은 macOS 키체인 전용입니다')
    if not sys.stdin.isatty():
        raise ValueError('비밀번호 최초 저장은 사용자 터미널에서 실행하세요')
    path, original, config = _read_private_config(config_path, Path.cwd() if repo_root is None else repo_root)
    pending = []
    for label, host in (('로그인 서버',config.login_host),('계산 서버',config.compute_host)):
        password = getpass.getpass(f'{label} 비밀번호 (화면에 표시되지 않음): ')
        repeated = getpass.getpass(f'{label} 비밀번호 확인: ')
        if not password or password != repeated or any(c in password for c in '\r\n\0'):
            raise ValueError('비밀번호가 비었거나 확인 값이 다릅니다. 줄바꿈/NUL은 지원하지 않습니다')
        pending.append((account_for(config,host),password))
    if path.read_bytes() != original:
        raise RuntimeError('설정 파일이 작업 중 바뀌었습니다')
    for account, password in pending:
        store_password(SERVICE,account,password)
    if path.read_bytes() != original:
        raise RuntimeError('키체인에는 저장했지만 설정 파일이 바뀌어 자동 인증을 활성화하지 않았습니다')
    updated = config.model_dump()
    updated.update(ssh_password_store='macos-keychain',ssh_batch_mode=False)
    _write_private_json(path,updated)
    print('두 서버 비밀번호를 macOS 키체인에 저장했습니다. 이후 SSH는 저장한 비밀번호를 사용합니다.',flush=True)


def askpass(prompt):
    """Only stdout here is the private OpenSSH askpass pipe, never app logs."""
    if not re.search(r'password:\s*$',prompt,re.I):
        return 1
    account = os.environ.get('UXAGENT_SSH_ACCOUNT')
    if not account:
        return 1
    try:
        password = read_password(SERVICE,account)
        if not password or any(c in password for c in '\r\n\0'):
            return 1
        sys.stdout.write(password+'\n')
        return 0
    except Exception:
        return 1


def askpass_environment(config, host, directory):
    if sys.platform != 'darwin':
        raise RuntimeError('macOS 키체인 인증 설정을 다른 OS에서는 사용할 수 없습니다')
    helper = Path(directory)/'keychain-askpass'
    # Explicit source path also supports editable installs launched outside repo CWD.
    program = ('import sys;sys.path.insert(0,'+repr(str(Path(__file__).resolve().parent.parent))+');'
               'from uxagent.gpu_passwords import askpass;sys.exit(askpass(sys.argv[1] if len(sys.argv)>1 else ""))')
    with helper.open('w',encoding='utf-8') as handle:
        handle.write('#!/bin/sh\nexec '+shlex.join([sys.executable,'-c',program])+' "$@"\n')
    helper.chmod(0o700)
    return {**os.environ,'SSH_ASKPASS':str(helper),'SSH_ASKPASS_REQUIRE':'force',
            'UXAGENT_SSH_ACCOUNT':account_for(config,host)}
