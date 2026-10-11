"""Bounded model choices compatible with the existing request adapters.

Availability is checked for the user's account at connection time; these are
not popularity rankings or claims of live verification.
"""
from copy import deepcopy

_GEMINI = [
    {'id':'gemini-2.5-flash-lite','label':'Gemini 2.5 Flash Lite','note':'기존 기본 모델. 신규 계정은 접근이 제한될 수 있습니다.'},
    {'id':'gemini-2.5-flash','label':'Gemini 2.5 Flash','note':'계정별 지원 여부를 연결 확인으로 점검합니다.'},
    {'id':'gemini-3.5-flash-lite','label':'Gemini 3.5 Flash Lite','note':'공식 문서의 새 프로젝트 권장 모델. 이 프로젝트의 실제 API 검증은 아직 없습니다.'},
]
_CATALOG = {
    'live': {'models':[{'id':'gpt-4o-mini','label':'GPT-4o mini','note':'기존 기본 모델.'},{'id':'gpt-4.1-mini','label':'GPT-4.1 mini','note':'Chat Completions 호환 선택지. 계정 권한 확인 필요.'}], 'default_model':'gpt-4o-mini','key_url':'https://platform.openai.com/api-keys','docs_url':'https://developers.openai.com/api/docs/quickstart','steps':['OpenAI Platform에 로그인합니다.','API keys에서 키를 만들고 API 사용 권한과 결제를 확인합니다.','이 화면에 키를 입력하고 선택한 모델로 연결을 확인합니다.'],'note':'ChatGPT 구독과 API 사용량·결제는 별도입니다.'},
    'claude': {'models':[{'id':'claude-sonnet-4-6','label':'Claude Sonnet 4.6','note':'기존 기본 모델.'},{'id':'claude-haiku-4-5','label':'Claude Haiku 4.5','note':'Messages API 선택지. 계정별 지원 여부 확인 필요.'}], 'default_model':'claude-sonnet-4-6','key_url':'https://console.anthropic.com/settings/keys','docs_url':'https://platform.claude.com/docs/en/api/overview','steps':['Claude Console에 로그인합니다.','API keys에서 키를 만들고 API 결제·권한을 확인합니다.','이 화면에 키를 입력하고 연결을 확인합니다.'],'note':'Claude 구독과 API 사용량·결제는 별도입니다.'},
    'gemini': {'models':_GEMINI,'default_model':'gemini-2.5-flash-lite','key_url':'https://aistudio.google.com/apikey','docs_url':'https://ai.google.dev/gemini-api/docs/api-key','steps':['Google AI Studio에 로그인합니다.','API keys에서 프로젝트의 키를 만듭니다.','프로젝트의 모델 접근·한도·결제를 확인하고 연결합니다.'],'note':'Gemini 2.5는 신규 계정에서 제한될 수 있습니다. 선택지의 실제 계정 지원은 연결 요청으로 확인합니다.'},
    'jev': {'models':_GEMINI,'default_model':'gemini-2.5-flash-lite','key_url':'https://console.typesafe.ai/login','docs_url':'https://console.typesafe.ai/login','steps':['TypeSafe Console에 로그인합니다.','콘솔의 API 키 안내를 확인합니다. 상세 발급 메뉴 경로는 확인되지 않았습니다.','TypeSafe 키와 Google AI Studio에서 발급한 Gemini 키를 입력합니다.'],'note':'Jev 행동 분류는 jev-latest이며 선택한 Gemini 모델은 입력값 생성·fallback·설정 상담에 사용됩니다.'},
    'mock': {'models':[{'id':'mock-v1','label':'무료 데모','note':'API 요청 없음.'}],'default_model':'mock-v1','key_url':None,'docs_url':None,'steps':[],'note':'로컬 데모 사이트 전용입니다.'},
}

def catalog_payload():
    return {'providers':deepcopy(_CATALOG)}

def resolve_model(provider, requested=None):
    if provider not in _CATALOG:
        raise ValueError('지원하지 않는 모델 제공자입니다')
    model = _CATALOG[provider]['default_model'] if requested is None else requested
    if not isinstance(model,str) or model not in {item['id'] for item in _CATALOG[provider]['models']}:
        raise ValueError('선택한 제공자에서 지원하는 모델을 선택하세요')
    return model
