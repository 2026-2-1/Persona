(targetIds) => {
  const wanted = new Set(targetIds);
  const byId = new Map([...document.querySelectorAll('[parser-semantic-id]')]
    .map(el => [el.getAttribute('parser-semantic-id'), el]));
  const clean = (text, max=200) => (text || '').replace(/\s+/g, ' ').trim().slice(0,max);
  const visible = el => {
    const style = getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0' && el.getClientRects().length > 0;
  };
  const refs = (el, attr) => (el.getAttribute(attr) || '').split(/\s+/).filter(Boolean).map(id=>document.getElementById(id)).filter(Boolean);
  const textRefs = (el, attr) => refs(el,attr).map(node=>clean(node.textContent)).filter(Boolean);
  const explicit = el => {
    const labelled = textRefs(el,'aria-labelledby').join(' ');
    if(labelled) return [clean(labelled),'aria-labelledby'];
    if(el.getAttribute('aria-label')) return [clean(el.getAttribute('aria-label')),'aria-label'];
    if(el.labels && el.labels.length) return [clean([...el.labels].map(n=>n.textContent).join(' ')),'label'];
    return ['', 'unknown'];
  };
  const siblings = el => {
    const single = el.parentElement && el.parentElement.querySelectorAll('input,textarea,select').length===1;
    return [el.previousElementSibling, ...(single ? [el.nextElementSibling] : [])].filter(n=>n && visible(n) &&
      !n.matches('input,textarea,select,button,a') && !n.querySelector('input,textarea,select,button,a'))
      .map(n=>clean(n.textContent,61)).filter(s=>s && s.length<=60);
  };
  const nameOf = el => {
    const found = explicit(el);
    if(found[0]) return [...found,'explicit'];
    if(el.matches('input') && el.closest('[data-cy="search-bar-desktop"]')) return ['상품 검색','search_container','explicit'];
    if(el.matches('input[type=submit],input[type=button],input[type=reset]') && el.value) return [clean(el.value),'value','explicit'];
    if(!el.matches('input,textarea,select,[contenteditable]')) {
      const text = clean(el.innerText);
      if(text) return [text,'text','explicit'];
      const image = el.matches('img') ? el : el.querySelector('img[alt]');
      if(image?.getAttribute('alt')) return [clean(image.getAttribute('alt')),'alt','explicit'];
      const svgTitle = el.querySelector('svg title');
      if(svgTitle?.textContent) return [clean(svgTitle.textContent),'svg_title','explicit'];
    }
    for(const attr of ['placeholder','title']) if(el.getAttribute(attr)) return [clean(el.getAttribute(attr)),attr,'explicit'];
    if(el.matches('input,textarea,select,[contenteditable]')) {
      const near = siblings(el)[0];
      if(near) return [/^min\.?$/i.test(near) ? near+' (최소값)' : /^max\.?$/i.test(near) ? near+' (최대값)' : near,'nearby_text','nearby'];
    }
    if(el.getAttribute('name')) return [clean(el.getAttribute('name')),'name_attribute','nearby'];
    return ['', 'unknown','unknown'];
  };
  const types = new Map([['DIALOG','dialog'],['FIELDSET','fieldset'],['FORM','form'],['ARTICLE','article'],
    ['LI','list_item'],['TR','row'],['TABLE','table'],['NAV','navigation'],['MAIN','main'],['HEADER','header'],
    ['ASIDE','aside'],['SECTION','section'],['UL','list'],['OL','list']]);
  const roleTypes = new Map([['dialog','dialog'],['alertdialog','dialog'],['group','group'],['radiogroup','radio_group'],
    ['tablist','tab_list'],['tabpanel','tab_panel'],['menu','menu'],['menubar','menu'],['navigation','navigation'],
    ['list','list'],['listitem','list_item'],['row','row'],['region','region'],['form','form'],['search','search']]);
  const kinds = new WeakMap(), siblingCounts = new WeakMap();
  const signature = el => el.tagName+'|'+(el.getAttribute('role')||'')+'|'+[...el.classList].sort().slice(0,4).join('.');
  const kindOf = el => {
    if(kinds.has(el)) return kinds.get(el);
    let kind = roleTypes.get(el.getAttribute('role')) || types.get(el.tagName) || '';
    if(el.getAttribute('aria-modal')==='true') kind='dialog';
    if(!kind && el.parentElement && !el.matches('a,button,input,select,textarea,span,label')) {
      let counts = siblingCounts.get(el.parentElement);
      if(!counts) { counts=new Map(); for(const child of el.parentElement.children) counts.set(signature(child),(counts.get(signature(child))||0)+1); siblingCounts.set(el.parentElement,counts); }
      if((counts.get(signature(el))||0)>1 && el.querySelector('h1,h2,h3,h4,a[href],img') && el.querySelector('button,a[href],input,select')) kind='repeated_item';
    }
    kinds.set(el,kind);
    return kind;
  };
  const groupNodes = new WeakMap(), groups=[];
  const groupName = (el,kind) => {
    const exp=explicit(el); if(exp[0]) return exp;
    const direct=el.querySelector(':scope > legend,:scope > caption,:scope > h1,:scope > h2,:scope > h3,:scope > h4,:scope > header > h2,:scope > header > h3');
    if(direct) return [clean(direct.textContent),direct.tagName.toLowerCase()];
    if(['article','repeated_item','list_item'].includes(kind)) {
      const headings=el.querySelectorAll('h1,h2,h3,h4');
      if(headings.length && (kind!=='repeated_item' || headings.length===1)) return [clean(headings[0].textContent),'heading'];
      if(kind==='repeated_item' && headings.length>1) return ['', 'unknown'];
      const links=[...el.querySelectorAll('a[href]')];
      if(kind==='repeated_item' && new Set(links.map(link=>nameOf(link)[0]).filter(Boolean)).size>1) return ['', 'unknown'];
      const link=links[0];
      if(link) { const n=nameOf(link); if(n[0]) return [n[0],'item_link']; }
    }
    if(kind==='row') { const cell=el.querySelector('th,td,[role=rowheader],[role=cell]'); if(cell) return [clean(cell.textContent),'row_header']; }
    return ['', 'unknown'];
  };
  const ensureGroup = el => {
    if(groupNodes.has(el)) return groupNodes.get(el);
    const kind=kindOf(el); if(!kind) return null;
    let parent=el.parentElement, parentGroup=null;
    while(parent) { if(kindOf(parent)) { parentGroup=ensureGroup(parent); break; } parent=parent.parentElement; }
    const [name,source]=groupName(el,kind);
    const group={id:'context:g'+(groups.length+1),kind,name,name_source:source,parent_id:parentGroup?.id||null};
    groups.push(group);groupNodes.set(el,group);return group;
  };
  const elements={},contextOnly=[];
  const targets=[...wanted].filter(id=>byId.has(id)).map(id=>({id,el:byId.get(id),passive:false}));
  const unavailable=[...document.querySelectorAll('button:disabled,input:disabled,input[readonly],select:disabled,textarea:disabled,textarea[readonly],[aria-disabled=true]')]
    .filter(el=>visible(el) && !wanted.has(el.getAttribute('parser-semantic-id')));
  unavailable.forEach((el,index)=>targets.push({id:'context:unavailable'+index,el,passive:true}));
  for(const {id,el,passive} of targets) {
    const [name,source,status]=nameOf(el);
    const chain=[];
    for(let parent=el.parentElement;parent;parent=parent.parentElement) if(kindOf(parent)) chain.push(ensureGroup(parent).id);
    const attributes={};
    for(const key of ['type','name','min','max','step','minlength','maxlength','autocomplete','role','aria-expanded','aria-selected',
      'aria-pressed','aria-current','aria-invalid','aria-disabled','aria-busy','aria-haspopup']) {
      if(el.hasAttribute(key)) attributes[key]=el.getAttribute(key);
    }
    for(const key of ['required','readonly','disabled','multiple']) if(el.hasAttribute(key)) attributes[key]='true';
    if(el.matches('input[type=checkbox],input[type=radio]')) attributes.checked=String(el.checked);
    const cell=el.closest('td,th');const table=cell?.closest('table');
    if(cell && table?.tHead) { const header=table.tHead.rows[table.tHead.rows.length-1]?.cells[cell.cellIndex]; if(header) attributes.column_header=clean(header.textContent); }
    const relations={},unresolved=[];
    for(const [attr,key] of [['aria-controls','controls'],['aria-owns','owns']]) {
      const nodes=refs(el,attr);const linked=[];
      for(const node of nodes) {
        const target=node.getAttribute('parser-semantic-id');
        if(wanted.has(target)) linked.push(target);
        else if(visible(node)) { const group=ensureGroup(node); if(group) linked.push(group.id); else unresolved.push(key); }
        else unresolved.push(key);
      }
      if(linked.length) relations[key]=linked;
      if(el.hasAttribute(attr) && !nodes.length) unresolved.push(key);
    }
    const context={name_source:source,label_status:status,group_ids:chain.reverse(),attributes,
      descriptions:textRefs(el,'aria-describedby'),errors:textRefs(el,'aria-errormessage'),
      nearby_text:el.matches('input,textarea,select,[contenteditable]')?siblings(el):[],
      relations,unresolved_relations:[...new Set(unresolved)],
      option_states:el.matches('select')?[...el.options].filter(option=>option.disabled||option.parentElement.disabled)
        .map(option=>({value:option.value,label:clean(option.textContent),disabled:'true'})):[]};
    if(passive) {
      contextOnly.push({id,name:name||el.tagName.toLowerCase(),role:el.getAttribute('role')||el.tagName.toLowerCase(),enabled:false,
        value:el.type==='password'?'[redacted]':el.matches('input,textarea,select')?el.value:null,context});
    } else elements[id]={name,...context};
  }
  return {groups,elements,context_only_elements:contextOnly};
}
