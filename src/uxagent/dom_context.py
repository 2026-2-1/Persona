"""Shared DOM group references for model inputs, without duplicating group text."""
from __future__ import annotations

from html import escape

from .model_json import dumps_json
from .schemas import ElementInfo


def model_context(observation, aliases=None, target_ids=None, *, popup_only=False, include_names=True):
    aliases = aliases or {}
    entries = {e.id: e for collection in (observation.hoverable_elements, observation.clickable_elements,
                                         observation.input_elements, observation.select_elements) for e in collection}
    for region in observation.interaction_state.get('scroll_regions', []):
        if region.get('context'):
            entries.setdefault(region['id'], ElementInfo(id=region['id'], role='scroll_region',
                name=region.get('name', ''), context=region['context']))
    selected = set(target_ids) if target_ids is not None else set(entries)
    groups = {g.id: g for g in observation.context_groups}
    needed, elements = set(), {}
    popup_roots = set()
    for target in entries:
        if target not in selected:
            continue
        entry = entries[target]
        context = entry.context.model_dump(exclude_defaults=True)
        if not context:
            continue
        context['name_source'] = entry.context.name_source
        context['label_status'] = entry.context.label_status
        path = list(entry.context.group_ids)
        if popup_only:
            boundaries = [i for i, key in enumerate(path) if key in groups and groups[key].kind == 'dialog']
            path = path[boundaries[-1]:] if boundaries else []
            popup_roots.update(path[:1])
        context['group_ids'] = path
        needed.update(path)
        relations = {}
        unresolved = list(context.get('unresolved_relations', []))
        for kind, references in entry.context.relations.items():
            values = []
            for reference in references:
                if reference in groups:
                    lineage, cursor = set(), reference
                    while cursor in groups and cursor not in lineage:
                        lineage.add(cursor)
                        cursor = groups[cursor].parent_id
                    if not popup_only or bool(lineage & popup_roots):
                        values.append(reference)
                        needed.add(reference)
                    else:
                        unresolved.append(kind + '_outside_popup')
                elif reference in selected:
                    values.append(aliases.get(reference, reference))
                else:
                    unresolved.append(kind + '_outside_section')
            if values:
                relations[kind] = values
        if relations:
            context['relations'] = relations
        else:
            context.pop('relations', None)
        if unresolved:
            context['unresolved_relations'] = sorted(set(unresolved))
        if include_names:
            context['name'] = entry.name
        elements[aliases.get(target, target)] = context
    unavailable = []
    for entry in observation.context_only_elements:
        path = list(entry.context.group_ids)
        if target_ids is not None and not popup_only and (not path or path[-1] not in needed):
            continue
        if popup_only:
            if not set(path) & popup_roots:
                continue
            boundaries = [i for i, key in enumerate(path) if key in groups and groups[key].kind == 'dialog']
            if not boundaries:
                continue
            path = path[boundaries[-1]:]
        row = {'name': entry.name, 'role': entry.role, 'enabled': False,
               'context': entry.context.model_dump(exclude_defaults=True)}
        row['context']['group_ids'] = path
        if entry.value is not None:
            row['value'] = entry.value
        # These are observation-only facts, never executable target IDs.
        row['context'].pop('relations', None)
        unavailable.append(row)
        needed.update(path)
    if not elements and not unavailable:
        return {}
    pending = list(needed)
    while pending:
        group = groups.get(pending.pop())
        if popup_only and group and group.kind == 'dialog':
            continue
        if group and group.parent_id and group.parent_id not in needed:
            needed.add(group.parent_id)
            pending.append(group.parent_id)
    definitions = []
    for group in observation.context_groups:
        if group.id not in needed:
            continue
        row = group.model_dump(exclude_defaults=True)
        if group.parent_id not in needed:
            row.pop('parent_id', None)
        definitions.append(row)
    result = {'groups': definitions, 'elements': elements}
    if unavailable:
        result['unavailable_controls'] = unavailable
    return result


def context_markup(observation, aliases=None, target_ids=None, *, include_names=True):
    if target_ids is not None:
        target_ids = set(target_ids) | {r['id'] for r in observation.interaction_state.get('scroll_regions', []) if r.get('context')}
    context = model_context(observation, aliases, target_ids, include_names=include_names)
    return '<element_context>' + escape(dumps_json(context, ensure_ascii=False, separators=(',', ':'))) + '</element_context>' if context else ''
