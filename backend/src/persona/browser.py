from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from persona.config import Settings
from persona.planner import ActionProvider, MockActionProvider


class CancellationRequested(Exception):
    pass


def origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only HTTP(S) fixture traffic is allowed")
    if parsed.username or parsed.password:
        raise ValueError("Credential URLs are not allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.scheme, parsed.hostname.lower(), port


def allowed_url(url: str, fixture_url: str) -> bool:
    try:
        return origin(url) == origin(fixture_url)
    except ValueError:
        return False


class BrowserRunner:
    def __init__(self, provider: ActionProvider | None = None):
        self.provider = provider or MockActionProvider()

    def run(
        self,
        settings: Settings,
        session_id: str,
        persona_name: str,
        task_id: str,
        is_cancelled: Callable[[], bool],
        on_step: Callable[[dict[str, Any]], None],
    ) -> None:
        def checkpoint() -> None:
            if is_cancelled():
                raise CancellationRequested

        directory = settings.artifact_dir / session_id
        directory.mkdir(parents=True, exist_ok=True)

        def screenshot(page: Any, step_no: int, phase: str) -> str:
            filename = f"{step_no}-{phase}.png"
            page.screenshot(path=str(directory / filename), full_page=True, timeout=15_000)
            return f"/artifacts/{session_id}/{filename}"

        checkpoint()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    locale="ko-KR",
                    accept_downloads=False,
                    service_workers="block",
                )

                def restrict_request(route: Any) -> None:
                    if allowed_url(route.request.url, settings.fixture_base_url):
                        route.continue_()
                    else:
                        route.abort("blockedbyclient")

                context.route("**/*", restrict_request)
                # WebSockets are a separate channel from HTTP request routing.
                context.route_web_socket("**/*", lambda websocket: websocket.close())
                page = context.new_page()
                page.set_default_timeout(10_000)
                checkpoint()
                page.goto(settings.fixture_base_url, wait_until="domcontentloaded", timeout=20_000)
                on_step(
                    {
                        "step_no": 1,
                        "action": "navigate",
                        "url": page.url,
                        "description": "로컬 시험 상품 페이지 열기",
                        "status": "succeeded",
                        "screenshot_before": None,
                        "screenshot_after": screenshot(page, 1, "after"),
                    }
                )
                for step_no, action in enumerate(
                    self.provider.actions(persona_name, task_id), start=2
                ):
                    checkpoint()
                    before = screenshot(page, step_no, "before")
                    checkpoint()
                    try:
                        if action.kind != "click" or action.selector != "#show-info":
                            raise ValueError("The starter permits only the fixture info button")
                        page.locator(action.selector).click()
                        page.locator("#product-info").wait_for(state="visible")
                        on_step(
                            {
                                "step_no": step_no,
                                "action": action.kind,
                                "url": page.url,
                                "description": action.description,
                                "status": "succeeded",
                                "screenshot_before": before,
                                "screenshot_after": screenshot(page, step_no, "after"),
                            }
                        )
                    except Exception:
                        on_step(
                            {
                                "step_no": step_no,
                                "action": action.kind,
                                "url": page.url,
                                "description": "상품 정보 확인 동작 실패",
                                "status": "technical_error",
                                "screenshot_before": before,
                                "screenshot_after": None,
                            }
                        )
                        raise
                checkpoint()
            finally:
                browser.close()
