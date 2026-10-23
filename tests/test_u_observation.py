import pytest

from uxagent.browser import BrowserSession
from uxagent.observation import observe
from uxagent.browser import wait_for_settle


async def open_markup(browser, markup):
    await browser.context.route(
        "https://shop.test/**",
        lambda route: route.fulfill(body=markup, content_type="text/html; charset=utf-8"),
    )
    await browser.active.goto("https://shop.test/")


@pytest.mark.asyncio
async def test_u_parser_preserves_empty_controls_and_semantic_ids_on_original_dom():
    markup = """<main><label for=search>검색</label><input id=search placeholder="상품 검색">
      <input placeholder="상품 검색"><select name=size><option value="">선택</option>
      <option value=m selected>M</option></select><div contenteditable=true aria-label="메모"></div>
      <button>구매</button><button>구매</button></main>"""
    async with BrowserSession(False) as browser:
        await open_markup(browser, markup)
        obs, registry = await observe(browser, max_text=10, max_elements=1)
        assert "parser-semantic-id=" in obs.html
        assert not obs.capture.truncated and obs.capture.limits_exceeded
        assert obs.capture.observed_text_chars > obs.capture.configured_text_limit
        assert len(obs.input_elements) == 3  # two text inputs plus the empty contenteditable editor
        assert len({x.id for x in obs.input_elements}) == 3
        assert {x.name for x in obs.input_elements} >= {"검색", "상품 검색", "메모"}
        assert any(x.name == "메모" for x in obs.input_elements)
        select = obs.select_elements[0]
        assert select.value == "m"
        assert select.options[1]["value"] == "m"
        assert len([x for x in obs.clickable_elements if x.name == "구매"]) == 2
        assert len({x.id for x in obs.clickable_elements if x.name == "구매"}) == 2
        for element in obs.input_elements + obs.clickable_elements + obs.select_elements:
            assert await browser.active.locator(
                f'[parser-semantic-id="{element.id}"]'
            ).count() >= 1
        assert registry.observation_id == obs.observation_id


@pytest.mark.asyncio
async def test_decathlon_search_control_is_named_for_its_function_not_promotion():
    markup = '''<header><div data-cy="search-bar-desktop">
      <input placeholder="리뷰 작성 시 즉시 사용 가능한 2,000포인트 증정!">
      <div data-cy="search-bar-icon-desktop"></div></div></header>
      <main><input placeholder="이메일"></main>'''
    async with BrowserSession(False) as browser:
        await open_markup(browser, markup)
        obs, _ = await observe(browser)
        search = next(item for item in obs.input_elements if "포인트" in item.name or "검색" in item.name)
        assert search.name == "상품 검색"
        assert "상품 검색" in obs.html
        assert next(item for item in obs.input_elements if item.name == "이메일").name == "이메일"


@pytest.mark.asyncio
async def test_numeric_min_max_labels_survive_observation_and_gpu_control_compression():
    from uxagent.fast_loop import FastLoop
    from uxagent.llm import LocalQwenProvider, BudgetManager

    markup = '''<main><h2>가격</h2><div><span>Min</span><input id=lower type=number value=20900></div>
      <div><span>Max</span><input id=upper type=number value=269000></div>
      <input aria-label="명시된 입력 이름" placeholder="다른 이름">
      <input placeholder="이메일"></main>'''
    async with BrowserSession(False) as browser:
        await open_markup(browser, markup)
        obs, registry = await observe(browser)
        minimum = next(item for item in obs.input_elements if item.value == '20900')
        maximum = next(item for item in obs.input_elements if item.value == '269000')
        assert minimum.name == 'Min (최소값)'
        assert maximum.name == 'Max (최대값)'
        assert await registry.targets[maximum.id].locator.get_attribute('id') == 'upper'
        assert {item.name for item in obs.input_elements} >= {'명시된 입력 이름', '이메일'}
        assert {item['name'] for item in obs.interaction_state['inputs']} >= {'Min (최소값)', 'Max (최대값)'}
        fast = FastLoop(LocalQwenProvider(), BudgetManager(None, None), 'persona-qwen', .2, 512)
        html, aliases, _ = fast._model_html(obs, force=True)
        assert f'id="{aliases[minimum.id]}"' in html and 'Min (최소값)' in html
        assert f'id="{aliases[maximum.id]}"' in html and 'Max (최대값)' in html


@pytest.mark.asyncio
async def test_icon_only_dialog_dismiss_control_is_preserved_and_executes():
    from uxagent.actions import ActionExecutor
    from uxagent.schemas import Action
    markup = '''<button id=background>러닝</button>
      <div id=popup role=dialog aria-modal=true aria-label="Promotional pop-up"
        style="position:fixed;inset:0;background:#fff">
        <div><div role=button aria-label=Close tabindex=0 style="width:24px;height:24px;cursor:pointer"
          onclick="document.getElementById('popup').remove()"><svg width=24 height=24><path d="M0 0L24 24"/></svg></div></div>
        <div>다가오는 마라톤! 추천 제품 보러가기</div>
      </div>'''
    async with BrowserSession(False) as browser:
        await open_markup(browser, markup)
        obs, _ = await observe(browser)
        close = next((x for x in obs.clickable_elements if x.name == 'Close'), None)
        assert close is not None, 'Icon-only role=button must survive SVG stripping'
        assert 'role="dialog"' in obs.html and 'aria-modal="true"' in obs.html
        result = await ActionExecutor(browser, [], 1000).execute(Action(
            type='click', observation_id=obs.observation_id, tab_id=obs.tab_id, target_id=close.id))
        assert result.ok, result.error
        following, _ = await observe(browser)
        assert 'role="dialog"' not in following.html
        assert not any(x.name == 'Close' for x in following.clickable_elements)


@pytest.mark.asyncio
async def test_u_parser_includes_scrollable_below_viewport_and_excludes_hidden():
    markup = """<div style="height:1200px"></div><button id=below>필터</button>
      <button style="display:none">숨김</button>
      <button style="visibility:hidden">숨김2</button>"""
    async with BrowserSession(False, 800, 400) as browser:
        await open_markup(browser, markup)
        obs, _ = await observe(browser)
        assert any(x.name == "필터" for x in obs.clickable_elements)
        assert not any(x.name.startswith("숨김") for x in obs.clickable_elements)


@pytest.mark.asyncio
async def test_parser_rerun_clears_old_semantic_ids_and_uses_current_dom():
    async with BrowserSession(False) as browser:
        await open_markup(browser, "<button>처음</button>")
        first, _ = await observe(browser)
        await browser.active.evaluate(
            "() => { document.body.innerHTML = '<button>다음</button>' }"
        )
        second, registry = await observe(browser)
        assert all(x.name != "처음" for x in second.clickable_elements)
        assert any(x.name == "다음" for x in second.clickable_elements)
        assert first.observation_id != second.observation_id
        assert registry.observation_id == second.observation_id


@pytest.mark.asyncio
@pytest.mark.parametrize("input_type", ["password", "PASSWORD", "PassWord"])
@pytest.mark.parametrize("runtime_value", [False, True])
async def test_parser_redacts_password_values_from_html_and_element_lists(tmp_path, input_type, runtime_value):
    import json
    from importlib.resources import files

    marker = "synthetic-password-marker"
    async with BrowserSession(False) as browser:
        value = "" if runtime_value else marker
        await open_markup(browser, f'<label for=pw>Password</label><input id=pw type="{input_type}" value="{value}">')
        if runtime_value:
            await browser.active.locator("#pw").fill(marker)
        obs, _ = await observe(browser, tmp_path)
        assert marker not in obs.model_dump_json()
        assert marker not in (tmp_path / "observations" / f"{obs.observation_id}.json").read_text()
        password = next(x for x in obs.clickable_elements if x.name == "Password")
        assert password.value == "[redacted]"
        raw = await browser.active.evaluate(files("uxagent").joinpath("parser/parser.js").read_text())
        assert marker not in json.dumps(raw)
        assert raw["input_elements"][0]["value"] == "[redacted]"
        assert await browser.active.locator("#pw").input_value() == marker


@pytest.mark.asyncio
async def test_observation_timeout_is_bounded_and_reported(monkeypatch):
    async with BrowserSession(False) as browser:
        await open_markup(browser, '<button>Ready</button>')
        await browser.active.evaluate("window.__uxagentNetworkActivity.update(1, 'test')")
        assert not await wait_for_settle(browser.active, 100)
        await browser.active.evaluate("window.__uxagentNetworkActivity.update(-1, 'test')")
        monkeypatch.setattr("uxagent.observation.wait_for_settle", lambda *_args: _not_settled())
        obs, _ = await observe(browser)
        assert obs.html and obs.error["code"] == "observation_wait_timeout"


@pytest.mark.asyncio
async def test_init_script_tracks_hover_handlers_and_fetch_activity():
    async with BrowserSession(False) as browser:
        await open_markup(browser, '<button id=hover>Hover target</button>')
        await browser.active.evaluate("() => document.querySelector('#hover').addEventListener('mouseenter', () => {})")
        await browser.active.evaluate("fetch('/activity-check')")
        obs, _ = await observe(browser)
        hover = next(x for x in obs.hoverable_elements if x.name == "Hover target")
        assert await browser.active.locator(f'[parser-semantic-id="{hover.id}"]').count() == 1
        status = await browser.active.evaluate("window.__uxagentNetworkActivity.activeRequests")
        assert status == 0


async def _not_settled():
    return False
