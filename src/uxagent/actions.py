from __future__ import annotations

import time, uuid
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from .schemas import Action, ActionResult
from .security import origin_allowed
from .browser import wait_for_settle


class ActionExecutor:
    def __init__(self, session, allowed_origins: list[str], timeout_ms=5000, settle_ms=3000, *, allow_scroll=False):
        self.session, self.allowed_origins = session, allowed_origins
        self.timeout_ms, self.settle_ms = timeout_ms, settle_ms
        self.allow_scroll = allow_scroll
        self.registries = {}

    def publish(self, registry):
        # Keep only the newest registry, so old observations cannot authorize actions.
        self.registries = {registry.observation_id: registry}

    async def execute(self, action: Action) -> ActionResult:
        started = time.monotonic()
        action_id = "a-" + uuid.uuid4().hex[:10]
        page = self.session.active
        before = page.url if page else ""
        error = None
        events = []
        self.session.blocked_navigations.clear()
        try:
            registry = self.registries.get(action.observation_id)
            if not registry:
                raise ActionFailure("stale_observation", "Observation is no longer current")
            if registry.tab_id != action.tab_id or self.session.tab_id(page) != action.tab_id:
                raise ActionFailure("stale_observation", "The action tab does not match the active observation")
            if action.type in ("scroll", "keypress") and not origin_allowed(page.url, self.allowed_origins):
                raise ActionFailure("navigation_blocked", "Current page origin is not allowed")
            if action.type in ("switch_tab", "close_tab"):
                target = next((p for p in self.session.pages if not p.is_closed() and self.session.tab_id(p) == action.target_tab_id), None)
                if not target:
                    raise ActionFailure("target_not_found", "Tab was not present in the observation")
                open_tabs = [p for p in self.session.pages if not p.is_closed()]
                if action.type == "close_tab":
                    if len(open_tabs) <= 1: raise ActionFailure("not_interactable", "Cannot close the last tab")
                    await target.close()
                    events.append({"type":"closed", "tab_id":action.target_tab_id})
                    self.session.active = next(p for p in open_tabs if p != target)
                else:
                    await self.session.activate(target)
                    events.append({"type":"activated", "tab_id":action.target_tab_id})
            elif action.type == "navigate":
                if not origin_allowed(action.url or "", self.allowed_origins):
                    raise ActionFailure("navigation_blocked", "URL origin is not allowed")
                if action.url not in registry.urls:
                    raise ActionFailure("target_not_found", "URL was not present in the current observation")
                await page.goto(action.url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            elif action.type == "back":
                response = await page.go_back(wait_until="domcontentloaded", timeout=self.timeout_ms)
                if not response and not origin_allowed(page.url, self.allowed_origins):
                    raise ActionFailure("navigation_blocked", "Previous page is outside allowed origins")
                if not origin_allowed(page.url, self.allowed_origins):
                    raise ActionFailure("navigation_blocked", "Previous page is outside allowed origins")
            elif action.type == "scroll":
                if not self.allow_scroll:
                    raise ActionFailure("unsupported_control", "Explicit scrolling is disabled for this study")
                # A bounded page scroll reveals new viewport targets only after recapture.
                await page.evaluate("distance => window.scrollBy({top: distance, behavior: 'instant'})", action.scroll_y)
            else:
                target_data = registry.targets.get(action.target_id or "")
                if not target_data: raise ActionFailure("target_not_found", "Target was not in the current observation")
                locator, tag = target_data.locator, target_data.tag
                if await locator.count() == 0: raise ActionFailure("target_detached", "Target is no longer attached")
                if not await locator.is_enabled() or await locator.get_attribute("aria-disabled") == "true":
                    raise ActionFailure("not_interactable", "Target is disabled")
                if action.type == "click":
                    if "click" not in target_data.capabilities:
                        raise ActionFailure("unsupported_control", "Target is not a click candidate")
                    if not await locator.is_enabled():raise ActionFailure("not_interactable","Target is disabled")
                    await locator.scroll_into_view_if_needed(timeout=self.timeout_ms)
                    await locator.click(timeout=self.timeout_ms)
                elif action.type == "type":
                    if "type" not in target_data.capabilities: raise ActionFailure("unsupported_control", "Target is not a text input")
                    if not await locator.is_enabled(): raise ActionFailure("not_interactable", "Input is disabled")
                    if await locator.get_attribute("type") == "password": raise ActionFailure("unsupported_control", "Password input is not supported")
                    if await locator.get_attribute("readonly") is not None: raise ActionFailure("unsupported_control", "Readonly input is not supported")
                    await locator.scroll_into_view_if_needed(timeout=self.timeout_ms)
                    if action.input_mode == "sequential":
                        await locator.fill("", timeout=self.timeout_ms)
                        await locator.press_sequentially(action.text or "", timeout=self.timeout_ms)
                    else:
                        await locator.fill(action.text or "", timeout=self.timeout_ms)
                elif action.type == "keypress":
                    if not target_data.capabilities.intersection({"click", "type"}):
                        raise ActionFailure("unsupported_control", "Target is not a safe keyboard control")
                    if (await locator.get_attribute("type") or "").lower() == "password":
                        raise ActionFailure("unsupported_control", "Password input is not supported")
                    await locator.scroll_into_view_if_needed(timeout=self.timeout_ms)
                    await locator.press(" " if action.key == "Space" else action.key, timeout=self.timeout_ms)
                elif action.type == "hover":
                    if "hover" not in target_data.capabilities:raise ActionFailure("unsupported_control","Target is not an observed hover candidate")
                    await locator.scroll_into_view_if_needed(timeout=self.timeout_ms)
                    await locator.hover(timeout=self.timeout_ms)
                elif action.type == "select":
                    if "select" not in target_data.capabilities: raise ActionFailure("unsupported_control", "Target is not a native select")
                    if action.option_value not in target_data.option_values: raise ActionFailure("invalid_option", "Option was not present in observation")
                    await locator.select_option(action.option_value, timeout=self.timeout_ms)
            settled = await wait_for_settle(self.session.active, self.settle_ms)
            if self.session.blocked_navigations:
                events.extend({"type":"navigation_blocked", "url":url} for url in self.session.blocked_navigations)
                raise ActionFailure("navigation_blocked", "A navigation outside allowed origins was blocked")
        except ActionFailure as exc:
            error = {"code": exc.code, "message": str(exc)}
            settled = True
        except PlaywrightTimeoutError as exc:
            error = {"code":"action_timeout", "message":str(exc)[:300]}
            settled = False
        except Exception as exc:
            if self.session.blocked_navigations:
                events.extend({"type":"navigation_blocked", "url":url} for url in self.session.blocked_navigations)
                error = {"code":"navigation_blocked", "message":"A navigation outside allowed origins was blocked"}
            else:
                error = {"code":"not_interactable", "message":str(exc)[:300]}
            settled = False
        after = self.session.active.url if self.session.active else before
        return ActionResult(action_id=action_id, observation_id=action.observation_id, ok=error is None,
                            error=error, url_before=before, url_after=after,
                            elapsed_ms=int((time.monotonic()-started)*1000), settled=settled, tab_events=events)


class ActionFailure(Exception):
    def __init__(self, code, message): self.code, self.message = code, message; super().__init__(message)
