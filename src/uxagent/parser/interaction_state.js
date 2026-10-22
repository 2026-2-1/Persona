() => {
  const shown = el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity) !== 0 &&
      r.width > 0 && r.height > 0 && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth;
  };
  const identify = (el, prefix, i) => {
    if (!el.getAttribute('parser-semantic-id')) el.setAttribute('parser-semantic-id', `${prefix}-${i}`);
    return el.getAttribute('parser-semantic-id');
  };
  const label = el => (el.getAttribute('parser-accessible-name') || el.getAttribute('aria-label') ||
    el.getAttribute('title') || el.getAttribute('placeholder') || el.innerText || '').trim();
  const root = document.scrollingElement;
  const scrollInfo = (el, id) => ({id, name:label(el).slice(0,120),
    x:el.scrollLeft, y:el.scrollTop, width:el.clientWidth, height:el.clientHeight,
    max_x:Math.max(0,el.scrollWidth-el.clientWidth), max_y:Math.max(0,el.scrollHeight-el.clientHeight)});
  const scrolls = [...document.querySelectorAll('body *')].filter(el => {
    if (!shown(el)) return false;
    const s=getComputedStyle(el);
    return (/(auto|scroll)/.test(s.overflowX) && el.scrollWidth>el.clientWidth+1) ||
      (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight>el.clientHeight+1);
  });
  const scroll_regions = [scrollInfo(root, 'page'), ...scrolls.map((el,i)=>scrollInfo(el,identify(el,'ux-scroll',i)))];
  const inputNodes = [...document.querySelectorAll('input,textarea,[contenteditable=true]')].filter(shown);
  const inputs = inputNodes.filter(el=>el.type !== 'password').map((el,i)=>({
    id:identify(el,'ux-input',i), name:label(el), value:el.value ?? el.innerText,
    focused:el===document.activeElement, enabled:!el.disabled && !el.readOnly,
    search:el.type==='search' || Boolean(el.closest('[role=search],[data-cy=search-bar-desktop]')) ||
      /검색|search/i.test([label(el),el.name,el.id,el.getAttribute('data-cy')].join(' '))
  }));
  const hashText = value => {
    let hash = 2166136261;
    for (let i=0; i<value.length; i++) hash = Math.imul(hash ^ value.charCodeAt(i), 16777619);
    return (hash >>> 0).toString(16).padStart(8, '0');
  };
  const searchInput = inputNodes.find(el => inputs.some(info =>
    info.id === el.getAttribute('parser-semantic-id') && info.search));
  const main = document.querySelector('main,[role=main]') || document.body;
  const resultText = (main.innerText || '').replace(/\s+/g, ' ').trim();
  const searchRoot = searchInput && (searchInput.closest('[role=search],[data-cy="search-bar-desktop"]') ||
    searchInput.parentElement?.parentElement);
  const suggestionNodes = [...document.querySelectorAll('[role=listbox],[role=option],[role=status],[role=alert],[aria-live]')]
    .filter(el => shown(el) && !main.contains(el));
  if (searchRoot?.parentElement) suggestionNodes.push(...[...searchRoot.parentElement.children]
    .filter(el => el !== searchRoot && shown(el) && !main.contains(el)));
  const suggestionText = [...new Set(suggestionNodes)].map(el => (el.innerText || '').replace(/\s+/g, ' ').trim())
    .filter(Boolean).join('\n').slice(0, 12000);
  const loadingNodes = [...document.querySelectorAll(
    '[aria-busy="true"],[role=progressbar],[data-cy*="loading"],[class*="loading"],[class*="spinner"]')]
    .filter(shown);
  const search_state = {results_signature:hashText(resultText),
    suggestions_signature:hashText(suggestionText), loading:loadingNodes.length > 0,
    loading_count:loadingNodes.length};
  const explicit = [...document.querySelectorAll('[role=dialog],[role=alertdialog],[aria-modal=true],dialog[open]')].filter(shown);
  const closePattern = /^(close|닫기|팝업 닫기|창 닫기|×|✕|✖)$/i;
  const inferred = [...document.querySelectorAll('div,section,aside')].filter(el=> {
    if (!shown(el)) return false;
    const r=el.getBoundingClientRect(), s=getComputedStyle(el);
    return ['fixed','absolute'].includes(s.position) && Number(s.zIndex)>=100 &&
      r.width*r.height >= innerWidth*innerHeight*0.12 &&
      [...el.querySelectorAll('button,[role=button],[aria-label]')].some(c=>shown(c)&&closePattern.test(label(c)));
  });
  const candidates = [...new Set([...explicit,...inferred])].filter(el => {
    // Search panels belong to the active search flow, not promotion handling.
    if (inputNodes.some(input => el.contains(input) && inputs.some(info =>
        info.id === input.getAttribute('parser-semantic-id') && info.search))) return false;
    const r=el.getBoundingClientRect();
    const hit=document.elementFromPoint(Math.min(innerWidth-1,Math.max(0,r.left+r.width/2)),
      Math.min(innerHeight-1,Math.max(0,r.top+r.height/2)));
    return hit && (el.contains(hit) || hit.contains(el));
  }).filter(el=>!explicit.some(other=>other!==el && el.contains(other)));
  candidates.sort((a,b)=> Number(getComputedStyle(b).zIndex||0)-Number(getComputedStyle(a).zIndex||0) ||
    a.getBoundingClientRect().width*a.getBoundingClientRect().height-b.getBoundingClientRect().width*b.getBoundingClientRect().height);
  const el=candidates[0];
  let popup=null;
  if (el) {
    const r=el.getBoundingClientRect(), id=identify(el,'ux-popup',0);
    const text=[el.innerText,...[...el.querySelectorAll('img')].map(i=>i.alt)].filter(Boolean).join('\n').trim();
    const controls=[...el.querySelectorAll('[parser-semantic-id]')].filter(shown).map(c=>({id:c.getAttribute('parser-semantic-id'),name:label(c)}));
    const bodyText=[];
    const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node=walker.currentNode, parent=node.parentElement;
      if (parent && shown(parent) && !parent.closest('button,a,input,[role=button]')) bodyText.push(node.textContent.trim());
    }
    const descriptiveAlts=[...el.querySelectorAll('img')].filter(shown).map(i=>i.alt.trim())
      .filter(alt=>alt.length>=12 && !/^(popup|banner|image|팝업|배너|이미지)[\s\d_-]*$/i.test(alt));
    const meaningful=[...bodyText,...descriptiveAlts].join(' ').replace(/\bclose\b|팝업 닫기|창 닫기|닫기|[×✕✖]/gi,'').trim();
    popup={id, name:el.getAttribute('aria-label')||'popup', text,
      text_available:Boolean(meaningful), modal:el.getAttribute('aria-modal')==='true'||el.tagName==='DIALOG',
      controls, scroll_ids:scrolls.filter(c=>el.contains(c)).map(c=>c.getAttribute('parser-semantic-id')),
      clip:{x:Math.max(0,r.left),y:Math.max(0,r.top),width:Math.max(1,Math.min(innerWidth,r.right)-Math.max(0,r.left)),
            height:Math.max(1,Math.min(innerHeight,r.bottom)-Math.max(0,r.top))}};
  }
  return {viewport:{width:innerWidth,height:innerHeight}, scroll_regions, inputs, popup, search_state,
    visible_target_ids:[...document.querySelectorAll('[parser-semantic-id]')].filter(shown).map(e=>e.getAttribute('parser-semantic-id'))};
}
