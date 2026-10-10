from __future__ import annotations

import html, json, re, uuid
from dataclasses import dataclass
from pathlib import Path
from playwright.async_api import Page, Locator
from .schemas import Observation, ElementInfo, TabInfo, CaptureInfo


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


def _slug(value: str) -> str:
    value = re.sub(r"[^\w가-힣]+", ".", value.strip().lower()).strip(".")
    return value[:60] or "element"


async def observe(session, run_dir: Path | None = None, max_text: int = 12000, max_elements: int = 100,
                  previous_error: dict | None = None, _retried: bool = False) -> tuple[Observation, TargetRegistry]:
    page: Page = session.active
    obs_id = "obs-" + uuid.uuid4().hex[:10]
    tab_id = session.tab_id(page)
    data = await page.evaluate("""(capture) => {
      const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity)!==0&&r.width>0&&r.height>0&&r.bottom>0&&r.right>0&&r.top<innerHeight&&r.left<innerWidth};
      const name=e=>{const l=e.labels?.length?[...e.labels].map(x=>x.innerText).join(' '):'';return (e.getAttribute('aria-label')||l||e.innerText||e.getAttribute('placeholder')||e.getAttribute('title')||e.getAttribute('name')||e.tagName.toLowerCase()).trim().replace(/\\s+/g,' ').slice(0,200)};
      const clickRoles=['button','link','checkbox','radio','combobox','option','menuitem'];
      const nodes=[...document.querySelectorAll('button,a,input,textarea,select,[role=button],[role=link],[role=checkbox],[role=radio],[role=combobox],[role=option],[role=menuitem],[onclick],label,h1,h2,h3,p,li')].filter(visible);
      const items=nodes.map((e,i)=>{const internal='ux-'+capture+'-'+i;e.setAttribute('data-uxagent-id',internal);const role=e.getAttribute('role')||({BUTTON:'button',A:'link',INPUT:e.type==='checkbox'?'checkbox':e.type==='radio'?'radio':'textbox',TEXTAREA:'textbox',SELECT:'combobox'}[e.tagName]||e.tagName.toLowerCase());return {i,internal,tag:e.tagName.toLowerCase(),role,name:name(e),text:(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,500),value:e.type==='password'?'[redacted]':('value'in e?String(e.value):null),enabled:!e.matches(':disabled')&&!e.closest('[aria-disabled="true"]'),checked:e.hasAttribute('aria-checked')?e.getAttribute('aria-checked')==='true':!!e.checked,focus:document.activeElement===e,clickable:e.tagName!=='SELECT'&&(/^(BUTTON|A)$/.test(e.tagName)||/^(INPUT)$/.test(e.tagName)&&['button','submit','checkbox','radio'].includes(e.type)||clickRoles.includes(e.getAttribute('role'))||e.hasAttribute('onclick')||getComputedStyle(e).cursor==='pointer'),input:/^(INPUT|TEXTAREA)$/.test(e.tagName)&&!e.readOnly&&!['button','submit','checkbox','radio','password'].includes(e.type),select:e.tagName==='SELECT',hover:/menu|dropdown|tooltip/i.test((e.className||'')+' '+e.getAttribute('aria-haspopup')),href:e.tagName==='A'?e.href:null,options:e.tagName==='SELECT'?[...e.options].map(o=>({value:o.value,label:o.textContent.trim()})):[]}});
      return {title:document.title,url:location.href,html:document.body?.innerHTML||'',items,unsupported:[...document.querySelectorAll('iframe,canvas')].map(e=>e.tagName.toLowerCase()).filter((x,i,a)=>a.indexOf(x)===i)};
    }""", obs_id)
    if page.url != data["url"]:
        if not _retried:
            return await observe(session,run_dir,max_text,max_elements,previous_error,True)
        previous_error={"code":"capture_error","message":"URL changed during observation capture"}
        data.update({"url":page.url,"title":await page.title(),"items":[],"html":""})
    # stable semantic IDs are generated in reading order and attached only to this current registry.
    unique: dict[str, int] = {}
    registry: dict[str, tuple[Locator, str]] = {}
    groups = {"clickable_elements": [], "input_elements": [], "hoverable_elements": [], "select_elements": []}
    for item in data["items"][:max_elements]:
        name = item["name"]
        base = _slug(name)
        unique[base] = unique.get(base, 0) + 1
        eid = base if unique[base] == 1 else f"{base}.{unique[base]}"
        # The marker was attached to this exact visible DOM node during capture.
        locator=page.locator(f'[data-uxagent-id="{item["internal"]}"]')
        capabilities=set()
        if item["clickable"]:capabilities.add("click")
        if item["input"]:capabilities.add("type")
        if item["select"]:capabilities.add("select")
        if item["hover"]:capabilities.add("hover")
        registry[eid] = TargetBinding(locator,item["tag"],capabilities,{o["value"] for o in item["options"]},item["href"])
        info = ElementInfo(id=eid, role=item["role"], name=name, enabled=item["enabled"],
                           value=item["value"], checked=item["checked"], focused=item["focus"], href=item["href"], options=item["options"])
        if item["clickable"]: groups["clickable_elements"].append(info)
        if item["input"]: groups["input_elements"].append(info)
        if item["hover"]: groups["hoverable_elements"].append(info)
        if item["select"]: groups["select_elements"].append(info)
    # Sanitize public HTML using current visible rendered nodes and their text. Keep concise semantic markup.
    lines = [f"<{i['tag']} role=\"{i['role']}\">{html.escape(i['name'])}</{i['tag']}>" for i in data["items"][:max_elements] if i["tag"]!="label"]
    public_html = "\n".join(lines)
    truncated = len(public_html) > max_text or len(data["items"]) > max_elements
    public_html = public_html[:max_text]
    omitted = max(0, len(data["items"]) - max_elements)
    screenshot = None
    if run_dir is not None:
        obs_dir = run_dir / "observations"
        obs_dir.mkdir(parents=True, exist_ok=True)
        screenshot = f"observations/{obs_id}.png"
        await page.screenshot(path=str(run_dir / screenshot), full_page=False)
    tabs = [TabInfo(id=session.tab_id(p), title=await p.title(), url=p.url, active=p == page) for p in session.pages if not p.is_closed()]
    observation = Observation(observation_id=obs_id, tab_id=tab_id, url=data["url"], title=data["title"], html=public_html,
                              **groups, tabs=tabs, error=previous_error,
                              capture=CaptureInfo(truncated=truncated, omitted_element_count=omitted,
                                                  screenshot_path=screenshot, unsupported=data["unsupported"]))
    if run_dir:
        (run_dir / f"observations/{obs_id}.json").write_text(observation.model_dump_json(indent=2), encoding="utf-8")
    observed_urls={data["url"]}|{item["href"] for item in data["items"] if item["href"]}
    return observation, TargetRegistry(obs_id, tab_id, registry, observed_urls)
