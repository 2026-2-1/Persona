import pytest

from uxagent.browser import BrowserSession
from uxagent.observation import observe
from uxagent.browser import wait_for_settle


async def open_markup(browser, markup):
    await browser.set_allowed_origins(["https://shop.test"])
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
