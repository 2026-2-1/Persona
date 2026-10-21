from __future__ import annotations

import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from playwright.async_api import Locator, Page

from .browser import wait_for_settle
from .schemas import CaptureInfo, ElementInfo, Observation, TabInfo


@dataclass
class TargetBinding:
    locator: Locator
    tag: str
    capabilities: set[str]
    option_values: set[str]
    href: str | None = None


@dataclass
class TargetRegistry:
    observation_id: str
    tab_id: str
    targets: dict[str, TargetBinding]
    urls: set[str]


def _element_info(item: dict) -> ElementInfo:
    return ElementInfo(
        id=item["id"], role=item.get("role") or "element", name=item.get("name") or item.get("id") or "element",
        enabled=bool(item.get("enabled", True)), value=item.get("value"),
        checked=item.get("checked"), focused=bool(item.get("focused", item.get("isFocused", False))),
        in_viewport=bool(item.get('in_viewport', True)),
        href=item.get("href"), options=item.get("options") or [],
    )


async def observe(session, run_dir: Path | None = None, max_text: int = 12000, max_elements: int = 100,
                  previous_error: dict | None = None, _retried: bool = False) -> tuple[Observation, TargetRegistry]:
    """Capture U-style cleaned DOM and semantic targets from the current page.

    The U parser's observation is passed intact; legacy limits are recorded as
    advisory thresholds and never silently truncate model input.
    """
    page: Page = session.active
    obs_id = "obs-" + uuid.uuid4().hex[:10]
    tab_id = session.tab_id(page)
    settle_timeout_ms = 3000
    if not await wait_for_settle(page, settle_timeout_ms):
        previous_error = previous_error or {
            "code": "observation_wait_timeout",
            "message": "Page network or DOM did not settle before observation.",
        }

    parser = files("uxagent").joinpath("parser/parser.js").read_text(encoding="utf-8")
    try:
        data = await asyncio.wait_for(page.evaluate(parser), timeout=10)
    except asyncio.TimeoutError as exc:
        raise RuntimeError("U DOM parser exceeded its 10 second observation bound") from exc
    if not isinstance(data, dict) or not isinstance(data.get("html"), str):
        raise RuntimeError("U DOM parser returned an invalid observation")
    state_script = files('uxagent').joinpath('parser/interaction_state.js').read_text(encoding='utf-8')
    interaction_state = await asyncio.wait_for(page.evaluate(state_script), timeout=10)

    if page.url != data.get("url"):
        if not _retried:
            return await observe(session, run_dir, previous_error=previous_error, _retried=True)
        previous_error = {"code": "capture_error", "message": "URL changed during observation capture"}
        interaction_state = {}
        data.update({"url": page.url, "title": await page.title(), "html": "", "clickable_elements": [],
                     "input_elements": [], "hoverable_elements": [], "select_elements": [], "observed_urls": []})

    groups = {"clickable_elements": [], "input_elements": [], "hoverable_elements": [], "select_elements": []}
    visible_ids = set(interaction_state.pop('visible_target_ids', []))
    targets: dict[str, TargetBinding] = {}

    def add_target(item: dict, capability: str, *, option_values=None):
        target_id = item["id"]
        target = targets.get(target_id)
        if target is None:
            locator = page.locator(f'[parser-semantic-id="{target_id}"]')
            target = TargetBinding(locator, item.get("tag", ""), set(), set(), item.get("href"))
            targets[target_id] = target
        target.capabilities.add(capability)
        if option_values:
            target.option_values.update(option_values)

    for group, capability in (("clickable_elements", "click"), ("input_elements", "type"),
                              ("hoverable_elements", "hover"), ("select_elements", "select")):
        for item in data.get(group, []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            item = {**item, 'in_viewport': item['id'] in visible_ids}
            if group == "input_elements" and not item.get("canEdit", True):
                continue
            if group == "select_elements":
                item = {**item, "options": item.get("options", [])}
                add_target(item, capability, option_values={option["value"] for option in item["options"]})
            else:
                add_target(item, capability)
            groups[group].append(_element_info(item))

    input_info = {entry.id: entry for entry in groups['input_elements']}
    for entry in interaction_state.get('inputs', []):
        if entry['id'] in input_info:
            info = input_info[entry['id']]
            entry.update(name=info.name, enabled=info.enabled, value=info.value, focused=info.focused)

    screenshot = None
    if run_dir is not None:
        obs_dir = run_dir / "observations"
        obs_dir.mkdir(parents=True, exist_ok=True)
        screenshot = f"observations/{obs_id}.png"
        await page.screenshot(path=str(run_dir / screenshot), full_page=False)
        popup = interaction_state.get('popup')
        if popup:
            popup_path = f'observations/{obs_id}-popup.png'
            try:
                await page.screenshot(path=str(run_dir / popup_path), clip=popup['clip'])
                popup['screenshot_path'] = popup_path
                popup['image_hash'] = hashlib.sha256((run_dir / popup_path).read_bytes()).hexdigest()
            except Exception as exc:
                popup['screenshot_error'] = type(exc).__name__

    tabs = [TabInfo(id=session.tab_id(p), title=await p.title(), url=p.url, active=p == page)
            for p in session.pages if not p.is_closed()]
    observation = Observation(
        observation_id=obs_id, tab_id=tab_id, url=data["url"], title=data.get("title", ""), html=data["html"],
        **groups, tabs=tabs, error=previous_error,
        interaction_state=interaction_state,
        capture=CaptureInfo(policy="u-dom-parser", screenshot_path=screenshot,
                            observed_text_chars=len(data["html"]),
                            observed_element_count=int(data.get("semantic_element_count", 0)),
                            configured_text_limit=max_text, configured_element_limit=max_elements,
                            limits_exceeded=len(data["html"]) > max_text or
                                            int(data.get("semantic_element_count", 0)) > max_elements,
                            unsupported=data.get("unsupported", [])),
    )
    if run_dir:
        (run_dir / f"observations/{obs_id}.json").write_text(observation.model_dump_json(indent=2), encoding="utf-8")

    observed_urls = {data["url"], *data.get("observed_urls", [])}
    registry = TargetRegistry(obs_id, tab_id, targets, observed_urls)
    return observation, registry
