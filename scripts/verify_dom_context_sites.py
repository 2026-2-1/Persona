"""Read-only live DOM context verification; artifacts stay under ignored runs/."""
from __future__ import annotations

import argparse
import asyncio
import json
import hashlib
from importlib.resources import files
import time
from datetime import datetime, timezone
from pathlib import Path
from html import unescape
import re
from urllib.parse import urlsplit

from uxagent.browser import BrowserSession
from uxagent.dom_context import model_context
from uxagent.fast_loop import FastLoop
from uxagent.llm import BudgetManager, LocalQwenProvider
from uxagent.observation import observe
from uxagent.schemas import Persona, UPlan


SITES = [
    'https://www.decathlon.co.kr/',
    'https://www.ikea.com/kr/ko/',
    'https://www.wikipedia.org/',
    'https://www.python.org/',
    'https://pypi.org/',
    'https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input',
    'https://github.com/python/cpython',
    'https://www.gov.uk/',
    'https://www.nhs.uk/',
    'https://www.mozilla.org/en-US/',
    'https://www.openstreetmap.org/',
    'https://www.w3.org/WAI/tutorials/forms/',
    'https://www.apple.com/kr/',
    'https://www.gnu.org/',
    'https://www.kernel.org/',
]


def validate(observation, registry):
    entries = {e.id: e for collection in (observation.hoverable_elements, observation.clickable_elements,
        observation.input_elements, observation.select_elements) for e in collection}
    groups = {g.id: g for g in observation.context_groups}
    scroll_ids = {r['id'] for r in observation.interaction_state.get('scroll_regions', [])}
    assert len(groups) == len(observation.context_groups), 'duplicate group IDs'
    assert all(not g.parent_id or g.parent_id in groups for g in groups.values()), 'missing parent group'
    for entry in entries.values():
        assert set(entry.context.group_ids) <= groups.keys(), 'missing owner group'
        for values in entry.context.relations.values():
            assert set(values) <= (entries.keys() | groups.keys() | scroll_ids), 'missing relationship reference'
    assert all(e.id not in registry.targets for e in observation.context_only_elements), 'unavailable control became executable'
    context = model_context(observation)
    assert set(context.get('elements', {})) <= entries.keys() | scroll_ids, 'invented target'
    fast = FastLoop(LocalQwenProvider(), BudgetManager(None, None), 'persona-qwen', 0, 512)
    html, aliases, originals = fast._model_html(observation, force=True)
    assert all(originals[alias] == target for target, alias in aliases.items()), 'alias mapping mismatch'
    assert '<element_context>' in html, 'context lost in model input'
    assert len(registry.targets) > 0 and len(entries) > 0, 'no observed controls'
    return entries, context, html


async def validate_model_pipeline(observation):
    """Simulate model responses to test preflight/selection without calling a model."""
    provider, calls, decisions = LocalQwenProvider(), [], []
    provider.prompt_guard.counter = None

    async def simulate(messages, model, temperature, max_tokens):
        assert provider.prompt_guard.fits(messages, max_tokens), 'oversized model dispatch'
        system = messages[0]['content']
        stage = system.split('FAST_STAGE:',1)[1].splitlines()[0] if 'FAST_STAGE:' in system else 'prompt_summary'
        payload = json.loads(messages[-1]['content'])
        calls.append(stage)
        if stage == 'target_selection':
            value = {'group_id':payload['groups'][0]['group_id'],'reason':'Read-only DOM contract check'}
        elif stage == 'prompt_summary':
            value = {'summary':'Public page content; inspect the observed controls and context.'}
        else:
            decisions.append(payload)
            value = {'actions':[{'action':'click','target':payload['valid_targets']['clickable'][0],
                                 'description':'Contract test only; never execute this proposal'}]}
        return json.dumps(value), {'provider':'gpu','model':model,'input_tokens':0,'output_tokens':0}

    provider._enqueue = simulate
    fast = FastLoop(provider, BudgetManager(None,None), 'persona-qwen', 0, 512)
    persona = Persona(persona_id='dom-check',background='Public DOM verification',digital_familiarity='high',
                      preferences=['Inspect observed context'],intent='Inspect an observed control')
    await fast.act(persona,persona.intent,observation,[],UPlan(plan='Inspect context',rationale='DOM test',next_step='Inspect a control'))
    final = decisions[-1]
    match = re.search(r'<element_context>(.*?)</element_context>',final['environment'],re.S)
    assert match, 'context lost during preflight'
    context = json.loads(unescape(match[1]))
    groups = {g['id'] for g in context['groups']}
    for data in context['elements'].values():
        assert set(data['group_ids']) <= groups, 'owner lost during preflight'
    return {'simulated_requests':len(calls),'simulated_summary_requests':calls.count('prompt_summary'),
            'simulated_target_selections':calls.count('target_selection'),'actual_model_requests':0,
            'count_mode':'conservative_without_remote_tokenizer','final_context':context}


async def collect(url, index, output, semaphore):
    async with semaphore:
        folder = output / f'{index:02d}-{urlsplit(url).hostname}'
        folder.mkdir(parents=True, exist_ok=True)
        record = {'requested_url': url, 'captured_at': datetime.now(timezone.utc).isoformat(), 'status': 'failed'}
        started = time.monotonic()
        try:
            async with BrowserSession(False) as browser:
                response = await browser.active.goto(url, wait_until='domcontentloaded', timeout=30000)
                record.update(url=urlsplit(browser.active.url)._replace(query='',fragment='').geturl(), http_status=response.status if response else None,
                              title=await browser.active.title())
                if not response or response.status >= 400:
                    record['status'] = 'http_blocked'
                    return record
                if any(term in record['title'].lower() for term in ('just a moment', 'access denied', 'robot check', 'security check')):
                    record['status'] = 'challenge'
                    return record
                await browser.active.wait_for_function('''() => [...document.querySelectorAll('a,button,input,select')]
                  .some(el=>el.getClientRects().length && getComputedStyle(el).visibility!=='hidden')''', timeout=5000)
                body_text = (await browser.active.inner_text('body')).lower()
                if len(body_text)<2500 and any(term in body_text for term in ('verify you are human', 'enable javascript and cookies', 'automated access', 'access denied')):
                    record['status']='challenge'
                    return record
                raw = await browser.active.content()
                (folder / 'source.html').write_text(raw, encoding='utf-8')
                observed_at = time.monotonic()
                observation, registry = await observe(browser, folder)
                record['observation_ms'] = round((time.monotonic() - observed_at) * 1000)
                entries, context, html = validate(observation, registry)
                pipeline = await validate_model_pipeline(observation)
                (folder / 'pipeline.json').write_text(json.dumps(pipeline,ensure_ascii=False,indent=2),encoding='utf-8')
                # Compare explicit labels with original DOM facts independently of the context extractor.
                audit = await browser.active.evaluate('''() => [...document.querySelectorAll('[parser-semantic-id]')].map(el => {
                  const norm=s=>(s||'').replace(/\\s+/g,' ').trim().slice(0,200);
                  const ids=(el.getAttribute('aria-labelledby')||'').split(/\\s+/).filter(Boolean);
                  const labelled=ids.map(id=>document.getElementById(id)?.textContent||'').join(' ').trim();
                  const labels=el.labels?[...el.labels].map(n=>n.textContent).join(' '):'';
                  const name=labelled||el.getAttribute('aria-label')||labels;
                  return {id:el.getAttribute('parser-semantic-id'),name:norm(name)};
                }).filter(x=>x.name)''')
                checked = 0
                for item in audit:
                    if item['id'] in entries:
                        assert entries[item['id']].name == item['name'], 'explicit label mismatch'
                        checked += 1
                samples = [{'id': e.id, 'name': e.name, 'source': e.context.name_source,
                    'groups': [g.name or f'unknown {g.kind}' for g in observation.context_groups if g.id in e.context.group_ids]}
                    for e in entries.values() if e.context.group_ids][:12]
                (folder / 'model-context.json').write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding='utf-8')
                (folder / 'model-input.html').write_text(html, encoding='utf-8')
                record.update(status='passed', controls=len(entries), groups=len(observation.context_groups),
                    named_groups=sum(bool(g.name) for g in observation.context_groups),
                    unavailable_controls=len(observation.context_only_elements),
                    explicit_labels_audited=checked, unknown_labels=sum(e.context.label_status == 'unknown' for e in entries.values()),
                    model_input_chars=len(html), samples=samples, artifact_dir=str(folder), observation_error=observation.error)
                record['model_pipeline'] = {key:value for key,value in pipeline.items() if key!='final_context'}
        except Exception as error:
            record.update(error_type=type(error).__name__, error=str(error)[:240])
        finally:
            record['elapsed_ms'] = round((time.monotonic() - started) * 1000)
            (folder / 'result.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({k: v for k,v in record.items() if k not in {'samples'}}, ensure_ascii=False), flush=True)
        return record


async def run(args):
    output = Path(args.output)
    if output.resolve().parts[-1] in {'', '.'} or not output.resolve().is_relative_to(Path('runs').resolve()):
        raise ValueError('Live artifacts must be stored under ignored runs/')
    output.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(2)
    results = await asyncio.gather(*(collect(url, i, output, semaphore) for i,url in enumerate(args.url or SITES,1)))
    passed = [row for row in results if row['status']=='passed']
    hosts = {urlsplit(row['url']).hostname for row in passed}
    fingerprint = hashlib.sha256(files('uxagent').joinpath('parser/element_context.js').read_bytes()).hexdigest()
    report = {'minimum_sites': args.min_sites, 'passed_sites': len(hosts), 'results': results, 'extractor_sha256':fingerprint,
              'model_calls': 0, 'browser_actions': 'navigation/DOM read/screenshot only'}
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# Live DOM context verification', '', f'Passed distinct hosts: {len(hosts)} / required {args.min_sites}',
             '', 'No model requests, login, form submission or purchase actions.', '',
             '| Site | Status | Controls | Groups | Explicit labels audited | Unknown labels |', '|---|---|---:|---:|---:|---:|']
    for row in results:
        lines.append(f"| [{urlsplit(row['requested_url']).hostname}]({row['requested_url']}) | {row['status']} | {row.get('controls','—')} | {row.get('groups','—')} | {row.get('explicit_labels_audited','—')} | {row.get('unknown_labels','—')} |")
    lines += ['', 'Assertions cover referential integrity, explicit DOM label agreement and context preservation in model input. They do not establish the correctness of every inferred group or autonomous task success.']
    (output / 'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return 0 if len(hosts)>=args.min_sites else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--url', action='append')
    parser.add_argument('--min-sites', type=int, default=10)
    raise SystemExit(asyncio.run(run(parser.parse_args())))
