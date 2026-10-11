import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path

from uxagent.monitor import Dashboard, make_handler

ROOT=Path(__file__).resolve().parents[1]


def test_template_guide_options_origin_and_no_job_side_effect(tmp_path):
    dashboard=Dashboard(tmp_path/'runs',tmp_path/'personas',ROOT/'configs/study.json')
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(dashboard))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with urllib.request.urlopen(base+'/api/setup-guide/options') as response:
            options=json.load(response)
        assert len(options['scenarios'])==4
        assert options['providers']['live']['key_url']=='https://platform.openai.com/api-keys'
        request=urllib.request.Request(base+'/api/setup-guide',data=json.dumps({'provider':'mock','message':'사용자 추천','context':{'task':'가방 찾기'}}).encode(),headers={'Content-Type':'application/json','Origin':base})
        with urllib.request.urlopen(request) as response: advice=json.load(response)
        assert advice['source']=='template' and len(advice['personas'])==3
        assert advice['usage']['requests']==0
        assert dashboard.job is None and not dashboard.guide_busy
        request=urllib.request.Request(base+'/api/setup-guide',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://evil.test'})
        try: urllib.request.urlopen(request)
        except urllib.error.HTTPError as error: assert error.code==403
        else: raise AssertionError('cross-origin guide request accepted')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
