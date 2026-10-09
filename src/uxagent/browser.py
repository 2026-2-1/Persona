from __future__ import annotations

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from .security import origin_allowed


class BrowserSession:
    def __init__(self, headed: bool = True, width: int = 1440, height: int = 900):
        self.headed, self.width, self.height = headed, width, height
        self.playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.pages: list[Page] = []
        self.active: Page | None = None
        self.blocked_navigations: list[str] = []

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=not self.headed)
        self.context = await self.browser.new_context(viewport={"width": self.width, "height": self.height})
        page = await self.context.new_page()
        self.pages = [page]
        self.active = page
        page.on("popup", lambda p: self._register(p))
        self.context.on("page", self._register)
        return self

    def _register(self, page: Page):
        if page not in self.pages:
            self.pages.append(page)
            self.active = page
            page.on("popup", lambda p: self._register(p))

    def tab_id(self, page: Page) -> str:
        return f"tab-{self.pages.index(page) + 1}"

    async def activate(self, page: Page):
        self.active = page
        await page.bring_to_front()

    async def set_allowed_origins(self, allowed_origins: list[str]):
        async def guard(route):
            request = route.request
            main_document = request.is_navigation_request() and request.frame.parent_frame is None
            if main_document and not origin_allowed(request.url, allowed_origins):
                self.blocked_navigations.append(request.url)
                await route.abort()
            else:
                await route.continue_()
        await self.context.route("**/*", guard)

    async def __aexit__(self, exc_type, exc, tb):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


async def wait_for_settle(page: Page, timeout_ms: int) -> bool:
    """Wait for a quiet DOM window, bounded even when analytics keep networking active."""
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=min(timeout_ms, 1000))
    except Exception:
        pass
    try:
        await page.evaluate("""async (limit) => await new Promise(resolve => {
          let timer, hard, done=false; const finish=v=>{if(!done){done=true;clearTimeout(timer);clearTimeout(hard);observer.disconnect();resolve(v)}};
          const observer=new MutationObserver(()=>{clearTimeout(timer);timer=setTimeout(()=>finish(true),180)});
          observer.observe(document,{subtree:true,childList:true,attributes:true,characterData:true});
          timer=setTimeout(()=>finish(true),180); hard=setTimeout(()=>finish(false),limit);
        })""", timeout_ms)
        return True
    except Exception:
        return False
