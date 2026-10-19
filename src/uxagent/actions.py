from __future__ import annotations

import time
import uuid

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .browser import wait_for_settle
from .schemas import Action, ActionResult


class ActionExecutor:
    """Execute U actions against the current Playwright session.

    ``allowed_origins`` and ``allow_scroll`` remain accepted for older callers,
    but U execution does not use them as access or action gates. Semantic IDs
    are resolved against the current DOM, as in the U executor.
    """

    def __init__(self, session, allowed_origins=None, timeout_ms=5000, settle_ms=3000, *, allow_scroll=None):
        self.session = session
        self.timeout_ms, self.settle_ms = timeout_ms, settle_ms

    def publish(self, _registry):
        """Compatibility no-op: registry membership does not authorize U actions."""

    async def _semantic_locator(self, page, target_id: str):
        candidates = page.locator("[parser-semantic-id]")
        index = await candidates.evaluate_all(
            "(nodes, target) => nodes.findIndex(node => node.getAttribute('parser-semantic-id') === target)",
            target_id,
        )
        if index < 0:
            raise ActionFailure("target_not_found", f"Semantic target was not present in the current DOM: {target_id}")
        return candidates.nth(index)

    def _find_tab(self, tab_id: str):
        return next((page for page in self.session.pages
                     if not page.is_closed() and self.session.tab_id(page) == tab_id), None)

    async def execute(self, action: Action) -> ActionResult:
        started = time.monotonic()
        action_id = "a-" + uuid.uuid4().hex[:10]
        page = self.session.active
        before = page.url if page and not page.is_closed() else ""
        error = None
        events = []
        settled = False

        try:
            if page is None or page.is_closed():
                raise ActionFailure("target_not_found", "There is no active browser tab")

            if action.type in {"click", "type", "hover", "select", "clear", "key_press", "keypress"} and action.target_id:
                locator = await self._semantic_locator(page, action.target_id)
                if await locator.count() == 0:
                    raise ActionFailure("target_not_found", "Semantic target is not present in the current DOM")
            else:
                locator = None

            if action.type == "click":
                await locator.click(timeout=self.timeout_ms)
            elif action.type == "mouse_click":
                await page.mouse.click(action.at_x, action.at_y)
            elif action.type == "type":
                await locator.scroll_into_view_if_needed(timeout=self.timeout_ms)
                if action.input_mode == "sequential":
                    await locator.fill("", force=True, timeout=self.timeout_ms)
                    await locator.press_sequentially(action.text or "", timeout=self.timeout_ms)
                else:
                    await locator.fill(action.text or "", force=True, timeout=self.timeout_ms)
                if action.enter:
                    await locator.press("Enter", timeout=self.timeout_ms)
            elif action.type == "raw_type":
                await page.keyboard.type(action.text or "", delay=50)
            elif action.type == "scroll":
                if action.scroll_y is not None:
                    await page.evaluate("distance => window.scrollBy({top: distance, behavior: 'instant'})", action.scroll_y)
                else:
                    key = {"up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight"}[action.scroll_direction]
                    for _ in range(action.scroll_amount * 3):
                        await page.keyboard.press(key)
            elif action.type == "hover":
                await locator.scroll_into_view_if_needed(timeout=self.timeout_ms)
                await locator.hover(force=True, timeout=self.timeout_ms)
            elif action.type == "select":
                await locator.scroll_into_view_if_needed(timeout=self.timeout_ms)
                await locator.select_option(action.option_value, force=True, timeout=self.timeout_ms)
            elif action.type == "clear":
                await locator.scroll_into_view_if_needed(timeout=self.timeout_ms)
                await locator.clear(force=True, timeout=self.timeout_ms)
            elif action.type in {"key_press", "keypress"}:
                if locator is not None:
                    await locator.scroll_into_view_if_needed(timeout=self.timeout_ms)
                    await locator.focus(timeout=self.timeout_ms)
                    await locator.press(action.key, timeout=self.timeout_ms)
                else:
                    await page.keyboard.press(action.key)
            elif action.type in {"navigate", "goto_url"}:
                await page.goto(action.url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            elif action.type == "back":
                await page.go_back(wait_until="domcontentloaded", timeout=self.timeout_ms)
            elif action.type == "forward":
                await page.go_forward(wait_until="domcontentloaded", timeout=self.timeout_ms)
            elif action.type == "refresh":
                await page.reload(wait_until="domcontentloaded", timeout=self.timeout_ms)
            elif action.type == "new_tab":
                page = await self.session.context.new_page()
                self.session._register(page)
                if action.url:
                    await page.goto(action.url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                self.session.active = page
                events.append({"type": "opened", "tab_id": self.session.tab_id(page)})
            elif action.type == "switch_tab":
                page = self._find_tab(action.target_tab_id)
                if page is None:
                    raise ActionFailure("target_not_found", "Requested tab was not open")
                await self.session.activate(page)
                events.append({"type": "activated", "tab_id": action.target_tab_id})
            elif action.type == "close_tab":
                page = self._find_tab(action.target_tab_id)
                if page is None:
                    raise ActionFailure("target_not_found", "Requested tab was not open")
                open_tabs = [candidate for candidate in self.session.pages if not candidate.is_closed()]
                if len(open_tabs) <= 1:
                    raise ActionFailure("not_interactable", "Cannot close the last browser tab")
                await page.close()
                if page == self.session.active:
                    self.session.active = next(candidate for candidate in open_tabs if candidate != page)
                    await self.session.activate(self.session.active)
                events.append({"type": "closed", "tab_id": action.target_tab_id})
            else:
                raise ActionFailure("unsupported_action", f"Unsupported action: {action.type}")

            active = self.session.active
            settled = await wait_for_settle(active, self.settle_ms) if active and not active.is_closed() else True
        except ActionFailure as exc:
            error = {"code": exc.code, "message": str(exc)}
            settled = True
        except PlaywrightTimeoutError as exc:
            error = {"code": "action_timeout", "message": str(exc)[:300]}
        except Exception as exc:
            error = {"code": "not_interactable", "message": str(exc)[:300]}

        active = self.session.active
        after = active.url if active and not active.is_closed() else before
        return ActionResult(
            action_id=action_id,
            observation_id=action.observation_id,
            ok=error is None,
            error=error,
            url_before=before,
            url_after=after,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            settled=settled,
            tab_events=events,
        )


class ActionFailure(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)
