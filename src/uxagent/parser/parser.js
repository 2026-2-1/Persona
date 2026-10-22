/* =========================================================================
 *  DOM "stripper" — keeps empty controls **and** guarantees unique
 *  parser-semantic-id values by appending numeric suffixes
 * ========================================================================= */

const parse = () => {
  /* ---------- globals --------------------------------------------------- */
  const BLACKLISTED_TAGS = new Set([
    'script', 'style', 'link', 'meta', 'noscript', 'template',
    'iframe', 'svg', 'canvas', 'picture', 'video', 'audio',
    'object', 'embed'
  ]);

  const ALLOWED_ATTR = new Set([
    'id', 'type', 'name', 'value', 'placeholder',
    'checked', 'disabled', 'readonly', 'required', 'maxlength',
    'min', 'max', 'step', 'role', 'tabindex', 'alt', 'title',
    'for', 'action', 'method', 'contenteditable', 'selected',
    'multiple', 'autocomplete'
  ]);

  const PRESERVE_EMPTY_TAGS = new Set([
    'input', 'select', 'textarea', 'button', 'img', 'head', 'title', 'form'
  ]);

  const USED_SEMANTIC_IDS = new Set();

  /* ---------- helpers -------------------------------------------------- */
  const copyAllowed = (src, dst) => {
    for (const a of src.attributes) {
      if (src.tagName === 'INPUT' && src.type === 'password' && a.name === 'value') continue;
      if (
        ALLOWED_ATTR.has(a.name) ||
        a.name.startsWith('aria-') ||
        a.name.startsWith('parser-')
      ) {
        dst.setAttribute(a.name, a.value);
      }
    }
  };

  const slug = (t) =>
    t.toLowerCase().replace(/\s+/g, ' ').trim()
      .replace(/[^\w]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 20);

  const uniqueName = (base) => {
    let name = base || 'item';
    if (!USED_SEMANTIC_IDS.has(name)) {
      USED_SEMANTIC_IDS.add(name);
      return name;
    }
    let i = 1;
    while (USED_SEMANTIC_IDS.has(name + i)) i++;
    USED_SEMANTIC_IDS.add(name + i);
    return name + i;
  };

  const isEmpty = (el) => {
    // Stripping SVG must not strip an otherwise empty, named icon control.
    if (el.hasAttribute('parser-clickable') ||
        ['dialog', 'alertdialog'].includes(el.getAttribute('role'))) return false;
    if (el.hasAttribute('contenteditable')) return false;
    if (PRESERVE_EMPTY_TAGS.has(el.tagName.toLowerCase())) return false;
    for (const n of el.childNodes) {
      if (n.nodeType === 3 && n.textContent.trim()) return false;
      if (n.nodeType === 1 && !isEmpty(n)) return false;
    }
    return true;
  };

  const isVisible = (el) => {
    const style = window.getComputedStyle(el);
    const hidden =
      style.display === 'none' ||
      style.visibility === 'hidden' ||
      parseFloat(style.opacity) === 0;

    const zeroSize = el.offsetWidth === 0 && el.offsetHeight === 0;

    const rect = el.getBoundingClientRect();
    const scrollLeft = window.scrollX || document.documentElement.scrollLeft;
    const right = rect.right;
    const top = rect.top;
    const outOfPort = (right + scrollLeft < 0);

    let belowPortNotScrollable = false;
    if (top > window.innerHeight && !(document.documentElement.scrollHeight > window.innerHeight)) {
      let hasScrollableAncestor = false;
      for (let p = el?.parentElement; p; p = p.parentElement) {
        const cs = getComputedStyle(p);
        const canScrollY = /(auto|scroll)/.test(cs.overflowY) && p.scrollHeight > p.clientHeight;
        if (canScrollY) { hasScrollableAncestor = true; break; }
      }
      belowPortNotScrollable = !hasScrollableAncestor;
    }
    if (hidden || zeroSize || outOfPort || belowPortNotScrollable) return false;
    return true;
  };

  const replaceElement = (el, newTag, child) => {
    const r = document.createElement(newTag);
    for (const a of el.attributes) r.setAttribute(a.name, a.value);
    copyAllowed(child, r);
    r.innerHTML = child.innerHTML;
    return r;
  };

  const pullUpChild = (parent, child) => {
    copyAllowed(child, parent);
    parent.innerHTML = child.innerHTML;
  };

  const flatten = (el) => {
    while (el.children.length === 1) {
      const child = el.children[0];
      if ([el, child].some(node => node.hasAttribute('parser-clickable') ||
          ['dialog', 'alertdialog'].includes(node.getAttribute('role')) ||
          node.hasAttribute('aria-modal'))) break;
      const p = el.tagName.toLowerCase();
      const c = child.tagName.toLowerCase();
      if (p !== 'div' && c !== 'div') break;
      el = (p === 'div' && c !== 'div')
        ? replaceElement(el, child.tagName, child)
        : (pullUpChild(el, child), el);
    }
    return el;
  };

  /* ---------- clear parser-* attrs before run -------------------------- */
  (() => {
    const clearParserAttrs = (el) => {
      if (!el || !el.attributes) return;
      for (const a of Array.from(el.attributes)) {
        if (a.name.startsWith('parser-')) el.removeAttribute(a.name);
      }
    };

    // Clear on <html> itself first
    clearParserAttrs(document.documentElement);

    // Walk every element efficiently and clear any parser-* attrs
    const walker = document.createTreeWalker(document, NodeFilter.SHOW_ELEMENT);
    let node = walker.currentNode;
    while (node) {
      clearParserAttrs(node);
      node = walker.nextNode();
    }
  })();


  const nearbyInputLabel = el => {
    if (!['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) return '';
    const parent = el.parentElement;
    const onlyField = parent && parent.querySelectorAll('input,textarea,select').length === 1;
    const candidates = [el.previousElementSibling, ...(onlyField ? [el.nextElementSibling] : [])];
    for (const candidate of candidates) {
      if (!candidate || !isVisible(candidate) || candidate.matches('input,textarea,select,button,a') ||
          candidate.querySelector('input,textarea,select,button,a')) continue;
      const text = (candidate.textContent || '').trim().replace(/\s+/g, ' ');
      if (!text || text.length > 60) continue;
      if (/^min\.?$/i.test(text)) return text + ' (최소값)';
      if (/^max\.?$/i.test(text)) return text + ' (최대값)';
      return text;
    }
    return '';
  };

  /* ==================================================================== */
  function automaticStripElement(original, parentName = '', parentIsClickable = false) {
    if (!original || original.nodeType !== 1) return null;
    const tag = original.tagName.toLowerCase();
    if (BLACKLISTED_TAGS.has(tag)) return null;
    if (!isVisible(original)) return null;

    let clone = document.createElement(original.tagName);
    copyAllowed(original, clone);
    const accessibleName = original.getAttribute('aria-label') ||
      (original.labels ? Array.from(original.labels).map(label => label.textContent.trim()).filter(Boolean).join(' ') : '') ||
      (tag === 'input' && original.closest('[data-cy="search-bar-desktop"]') ? '상품 검색' : '') ||
      (!original.getAttribute('placeholder') && !original.getAttribute('title') ? nearbyInputLabel(original) : '');
    if (accessibleName) clone.setAttribute('parser-accessible-name', accessibleName);
    if (tag === 'input' && ['checkbox', 'radio'].includes((original.type || '').toLowerCase())) {
      clone.checked = original.checked;
      if (original.checked) clone.setAttribute('checked', '');
      else clone.removeAttribute('checked');
    }

    const computedStyle = window.getComputedStyle(original);
    if (computedStyle.pointerEvents !== 'auto') {
      clone.setAttribute('parser-pointer-events', computedStyle.pointerEvents);
    }
    if (document.activeElement === original) {
      clone.setAttribute('parser-is-focused', 'true');
    }

    const isDisabled = original.disabled ||
      original.hasAttribute('disabled') ||
      computedStyle.pointerEvents === 'none';

    const probablyClickable = (() => {
      if (['button', 'select', 'summary', 'area', 'input'].includes(tag)) return true;
      if (tag === 'a' && original.hasAttribute('href')) return true;
      if (original.hasAttribute('onclick')) return true;
      const r = original.getAttribute('role');
      if (['button', 'link', 'checkbox', 'radio', 'option'].includes(r)) return true;
      return computedStyle.cursor === 'pointer';
    })();

    const isClickable = !parentIsClickable && probablyClickable && !isDisabled;

    let thisName = '';
    if (isClickable) {
      const base = slug((original.innerText || '').trim() ||
        original.getAttribute('title') ||
        original.getAttribute('placeholder') ||
        tag);
      thisName = uniqueName(parentName ? `${parentName}.${base}` : base);
      for (const e of [clone, original]) {
        e.setAttribute('parser-semantic-id', thisName);
        e.setAttribute('parser-clickable', 'true');
      }
    }

    if (original.closest('[data-maybe-hoverable="true"]')) {
      if (!thisName) {
        const base = slug((original.innerText || '').trim() || original.getAttribute('title') || tag);
        thisName = uniqueName(parentName ? `${parentName}.${base}` : base);
      }
      clone.setAttribute('parser-semantic-id', thisName);
      original.setAttribute('parser-semantic-id', thisName);
      clone.setAttribute('parser-maybe-hoverable', 'true');
      clone.setAttribute('parser-hoverable', 'true');
    }

    if (tag === 'input' || tag === 'textarea' || original.hasAttribute('contenteditable')) {
      const t = (original.getAttribute('type') || 'text').toLowerCase();
      const inputIsDisabled = original.disabled || original.readOnly || t === 'password';
      if (!inputIsDisabled && !thisName) {
        const base = slug((original.getAttribute('placeholder') ||
          original.getAttribute('name') ||
          original.value || '').trim() || tag);
        thisName = uniqueName(parentName ? `${parentName}.${base}` : base);
      }
      if (!inputIsDisabled && thisName) {
        clone.setAttribute('parser-semantic-id', thisName);
        clone.setAttribute('value', original.value || '');
        clone.setAttribute('parser-input-disabled', 'false');
        clone.setAttribute('parser-can-edit', !original.readOnly ? 'true' : 'false');
        original.setAttribute('parser-semantic-id', thisName);
      }
      if (!inputIsDisabled && thisName && t === 'number') {
        clone.setAttribute('parser-numeric-value', original.valueAsNumber || '');
      }
      if (!inputIsDisabled && thisName && original.selectionStart !== undefined) {
        clone.setAttribute('parser-selection-start', original.selectionStart);
        clone.setAttribute('parser-selection-end', original.selectionEnd);
      }
    }

    if (tag === 'select') {
      const selectIsDisabled = original.disabled || original.hasAttribute('disabled');
      if (!selectIsDisabled) {
        if (!thisName) {
          const base = slug((original.getAttribute('name') || tag));
          thisName = uniqueName(parentName ? `${parentName}.${base}` : base);
        }
        clone.setAttribute('parser-semantic-id', thisName);
        clone.setAttribute('parser-value', original.value);
        clone.setAttribute('parser-selected-index', original.selectedIndex);
        clone.setAttribute('parser-has-multiple', original.multiple ? 'true' : 'false');
        const selectedOptions = Array.from(original.selectedOptions).map(opt => opt.value).join(',');
        clone.setAttribute('parser-selected-values', selectedOptions);
        original.setAttribute('parser-semantic-id', thisName);
        for (const opt of original.querySelectorAll('option')) {
          const o = document.createElement('option');
          o.textContent = opt.textContent.trim();
          o.setAttribute('value', opt.value);
          o.setAttribute('parser-selected', opt.selected ? 'true' : 'false');
          const optName = uniqueName(`${thisName}.${slug(opt.textContent)}`);
          o.setAttribute('parser-semantic-id', optName);
          opt.setAttribute('parser-semantic-id', optName);
          clone.appendChild(o);
        }
      }
    }

    for (const child of (tag === 'select' ? [] : original.children)) {
      const cleaned = automaticStripElement(
        child,
        thisName || parentName,
        parentIsClickable || isClickable
      );
      if (cleaned && (!isEmpty(cleaned))) {
        clone.appendChild(cleaned);
      }
    }

    for (const n of original.childNodes) {
      if (n.nodeType === 3 && n.textContent.trim()) {
        clone.appendChild(document.createTextNode(n.textContent.trim()));
      }
    }

    clone = flatten(clone);
    for (let i = clone.children.length - 1; i >= 0; i--) {
      const c = clone.children[i];
      if (!PRESERVE_EMPTY_TAGS.has(c.tagName.toLowerCase()) && isEmpty(c)) {
        clone.removeChild(c);
      }
    }

    return clone;
  }

  const result = automaticStripElement(document.documentElement);
  const semanticInfo = (el) => {
    const tag = el.tagName.toLowerCase();
    const labels = el.labels ? Array.from(el.labels).map(label => label.textContent.trim()).filter(Boolean).join(' ') : '';
    const name = (el.getAttribute('parser-accessible-name') || el.getAttribute('aria-label') || labels || el.getAttribute('placeholder') ||
      el.getAttribute('title') || el.getAttribute('name') || el.textContent || tag).trim().replace(/\s+/g, ' ').slice(0, 200);
    const value = tag === 'input' && (el.getAttribute('type') || '').toLowerCase() === 'password'
      ? '[redacted]' : (tag === 'input' || tag === 'textarea' ? (el.getAttribute('value') || '') : null);
    const inputType = (el.getAttribute('type') || '').toLowerCase();
    return {id:el.getAttribute('parser-semantic-id'), tag, role:el.getAttribute('role') ||
      (tag === 'input' && ['checkbox','radio'].includes(inputType) ? inputType :
      ({button:'button',a:'link',input:'textbox',textarea:'textbox',select:'combobox'}[tag] || tag)),
      name, enabled:!el.hasAttribute('disabled') && el.getAttribute('aria-disabled') !== 'true',
      value, checked:el.hasAttribute('aria-checked') ? el.getAttribute('aria-checked') === 'true' :
        (('checked' in el) ? Boolean(el.checked) : el.hasAttribute('checked')), focused:el.getAttribute('parser-is-focused') === 'true',
      href:el.getAttribute('href'), options:tag === 'select' ? Array.from(el.querySelectorAll('option')).map(o=>({value:o.getAttribute('value') || '',label:o.textContent.trim()})) : []};
  };
  if (!result) throw new Error('U DOM parser returned no document root');
  return {
    title: document.title,
    url: location.href,
    html: result.outerHTML,
    clickable_elements: Array.from(result.querySelectorAll('[parser-clickable="true"]')).map(semanticInfo),
    hoverable_elements: Array.from(result.querySelectorAll('[parser-maybe-hoverable="true"]'))
      .map(semanticInfo),
    input_elements: Array.from(result.querySelectorAll('input[parser-semantic-id], textarea[parser-semantic-id], [contenteditable][parser-semantic-id]'))
      .map(el => ({
        ...semanticInfo(el),
        id: el.getAttribute('parser-semantic-id'),
        enabled: el.getAttribute('parser-input-disabled') === 'false' && !el.hasAttribute('disabled'),
        type: el.getAttribute('type') || (el.tagName.toLowerCase() === 'textarea' ? 'textarea' : 'contenteditable'),
        value: (el.getAttribute('type') || '').toLowerCase() === 'password' ? '[redacted]' : (el.getAttribute('value') || el.textContent),
        canEdit: el.getAttribute('parser-can-edit') === 'true',
        isFocused: el.getAttribute('parser-is-focused') === 'true'
      })),
    select_elements: Array.from(result.querySelectorAll('select[parser-semantic-id]'))
      .map(el => ({...semanticInfo(el), value:el.getAttribute('parser-value'),
        selectedIndex:Number(el.getAttribute('parser-selected-index')),
        multiple:el.getAttribute('parser-has-multiple') === 'true',
        selectedValues:(el.getAttribute('parser-selected-values') || '').split(',').filter(Boolean)})),
    observed_urls: Array.from(document.querySelectorAll('a[href]')).filter(isVisible).map(a=>a.href),
    semantic_element_count: result.querySelectorAll('[parser-semantic-id]').length,
    unsupported: Array.from(document.querySelectorAll('iframe,canvas')).map(el=>el.tagName.toLowerCase()).filter((x,i,a)=>a.indexOf(x)===i),
  };
}

parse();
