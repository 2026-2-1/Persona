from __future__ import annotations

import asyncio
from importlib.resources import files
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


class BrowserSession:
    def __init__(self, headed: bool = True, width: int = 1440, height: int = 900):
        self.headed, self.width, self.height = headed, width, height
        self.playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.pages: list[Page] = []
        self.active: Page | None = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=not self.headed)
        self.context = await self.browser.new_context(viewport={"width": self.width, "height": self.height})
        init_script = files("uxagent").joinpath("parser/initscript.js").read_text(encoding="utf-8")
        await self.context.add_init_script(init_script)
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

    async def __aexit__(self, exc_type, exc, tb):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


async def wait_for_settle(page: Page, timeout_ms: int) -> bool:
    """Wait for network activity and DOM changes to settle within one bounded deadline."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0, timeout_ms) / 1000
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=min(timeout_ms, 1000))
    except Exception:
        pass
    try:
        remaining = deadline - loop.time()
        if remaining <= 0:
            return False
        network_idle = await asyncio.wait_for(page.evaluate("""async ({idleMs, limitMs}) => {
          const activity = window.__uxagentNetworkActivity;
          return activity ? activity.waitForIdle(idleMs, limitMs) : true;
        }""", {"idleMs": 180, "limitMs": max(1, int(remaining * 1000))}), timeout=remaining)
        if not network_idle:
            return False
        remaining = deadline - loop.time()
        if remaining <= 0:
            return False
        return await asyncio.wait_for(page.evaluate("""async (limit) => await new Promise(resolve => {
          let timer, hard, done=false; const finish=v=>{if(!done){done=true;clearTimeout(timer);clearTimeout(hard);observer.disconnect();resolve(v)}};
          const observer=new MutationObserver(()=>{clearTimeout(timer);timer=setTimeout(()=>finish(true),180)});
          observer.observe(document,{subtree:true,childList:true,attributes:true,characterData:true});
          timer=setTimeout(()=>finish(true),180); hard=setTimeout(()=>finish(false),limit);
        })""", max(1, int(remaining * 1000))), timeout=remaining)
    except (Exception, asyncio.TimeoutError):
        return False
