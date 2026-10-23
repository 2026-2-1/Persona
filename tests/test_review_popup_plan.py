"""Follow-ups from the PR #103 review: image popups without vision, and plan continuity."""
import pytest

from uxagent.interaction import InteractionFlow
from uxagent.schemas import ElementInfo, Observation, UActions, UAction, UPlan
from test_interaction_flows import FlowFast
from test_u_fast import setup


def image_popup_observation(popup):
    return Observation(observation_id='obs', tab_id='tab-1', url='https://shop.test', title='shop',
        html='<main>배경</main>', clickable_elements=[ElementInfo(id='close', role='button', name='닫기')],
        interaction_state={'popup': popup, 'scroll_regions': []})


def image_popup(**fields):
    return {'id': 'popup', 'name': 'promotion', 'text': '', 'text_available': False, 'modal': True,
            'controls': [{'id': 'close', 'name': '닫기'}], 'scroll_ids': [],
            'clip': {'x': 20, 'y': 30, 'width': 100, 'height': 80}, **fields}


class NoVisionFast(FlowFast):
    async def _generate(self, stage, prompt, payload, *, response_model=None, image_path=None):
        if image_path is not None:
            self.calls.append((stage, dict(payload['popup']), image_path))
            raise RuntimeError('popup_vision_unavailable: this provider has no image input adapter')
        return await super()._generate(stage, prompt, payload, response_model=response_model)


@pytest.mark.asyncio
async def test_image_popup_falls_back_to_observed_controls_without_vision(tmp_path):
    (tmp_path / 'popup.png').write_bytes(b'crop')
    fast = NoVisionFast(tmp_path)
    plan, proposed, _ = await InteractionFlow().propose(
        fast, object(), '과업', image_popup_observation(image_popup(screenshot_path='popup.png')), 'persona', None)
    (_, first, first_image), (_, second, second_image) = fast.calls
    assert first_image is not None and 'image_coordinates' in first
    assert second_image is None and 'image_coordinates' not in second['popup']
    assert [c['id'] for c in second['popup']['controls']] == ['close']
    assert proposed.actions[0].action == 'click' and proposed.actions[0].target == 'close'


@pytest.mark.asyncio
async def test_image_popup_without_crop_decides_from_controls():
    fast = FlowFast(None)
    _, proposed, _ = await InteractionFlow().propose(
        fast, object(), '과업', image_popup_observation(image_popup()), 'persona', None)
    assert fast.calls[0][2] is None
    assert proposed.actions[0].target == 'close'


def continuation(brain):
    detour = UPlan(plan='(next) 현재 팝업을 먼저 판단하고 처리한다.', rationale='팝업', next_step='팝업 처리')
    proposed = UActions(actions=[UAction(action='click', target='submit', description='팝업 닫기')])

    async def propose(*args):
        return detour, proposed, '팝업'
    brain.interactions.needs_handling = lambda observation: True
    brain.interactions.propose = propose
    return detour


@pytest.mark.asyncio
async def test_continuation_keeps_the_task_plan():
    brain, obs, retrieve, *_ = setup()
    task_plan = UPlan(plan='1. 러닝화 검색\n2. 상세 확인', rationale='과업', next_step='러닝화 검색')
    brain.current_plan = task_plan
    detour = continuation(brain)
    decision, _ = await brain.forward('러닝화 찾기', obs, 1, retrieve)
    assert brain.current_plan is task_plan
    assert decision.plan == detour.plan


@pytest.mark.asyncio
async def test_first_step_continuation_still_sets_a_plan_for_feedback():
    brain, obs, retrieve, *_ = setup()
    detour = continuation(brain)
    await brain.forward('러닝화 찾기', obs, 1, retrieve)
    assert brain.current_plan is detour
