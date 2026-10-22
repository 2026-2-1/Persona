"""Strict transport JSON and bounded, auditable model-response syntax repairs."""
from __future__ import annotations

import json
import math
import re


class ProviderJSONError(RuntimeError):
    """The API envelope is invalid; no model response can be extracted."""


def loads_json(raw: str | bytes | bytearray):
    """Read JSON without accepting duplicate keys or nonfinite numbers."""
    text = raw.decode('utf-8') if isinstance(raw, (bytes, bytearray)) else raw

    def reject(message):
        raise json.JSONDecodeError(message, text, 0)

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                reject('Duplicate object key')
            result[key] = value
        return result

    def number(value):
        value = float(value)
        if not math.isfinite(value):
            reject('Nonfinite JSON number')
        return value

    return json.loads(text, object_pairs_hook=pairs, parse_float=number,
                      parse_constant=lambda _: reject('Nonfinite JSON number'))


def dumps_json(value, **kwargs) -> str:
    """Serialize outbound data with standard JSON numbers only."""
    kwargs['allow_nan'] = False
    return json.dumps(value, **kwargs)


def loads_transport_json(raw):
    """Keep malformed API envelopes out of model JSON repair conversations."""
    try:
        value = loads_json(raw)
    except (ValueError, TypeError) as error:
        raise ProviderJSONError('provider_response_json_error: invalid API envelope') from error
    if not isinstance(value, dict):
        raise ProviderJSONError('provider_response_json_error: expected API object')
    return value


def _repair_at_error(text, error, *, allow_enter_key):
    pos, message = error.pos, error.msg
    before, after = text[:pos], text[pos:]
    previous = before.rstrip()
    if (message.startswith('Illegal trailing comma') and after.startswith(',')
            and after[1:].lstrip().startswith(('}', ']'))):
        return before + after[1:], 'trailing_comma'
    if message.startswith('Invalid control character') and after and ord(after[0]) < 32:
        return before + json.dumps(after[0])[1:-1] + after[1:], 'string_control_character'
    if message in ('Expecting property name enclosed in double quotes', 'Expecting value'):
        if after[:1] in ('}', ']') and previous.endswith(','):
            comma = len(previous) - 1
            return text[:comma] + text[comma + 1:], 'trailing_comma'
    if message == 'Expecting property name enclosed in double quotes':
        key = re.match(r'([A-Za-z_][A-Za-z_0-9]*)(?=\s*:)', after)
        if key:
            return before + json.dumps(key[1]) + after[key.end():], 'unquoted_key'
    if message == 'Expecting value':
        literal = re.match(r'(True|False|None)(?=\s*[,}\]]|\s*$)', after)
        if literal:
            value = {'True': 'true', 'False': 'false', 'None': 'null'}[literal[1]]
            return before + value + after[literal.end():], 'python_literal'
    if message == "Expecting ':' delimiter":
        if allow_enter_key:
            key = re.search(r'"enter=(true|false)"\s*$', before)
            if key and before[:key.start()].rstrip().endswith(('{', ',')):
                return before[:key.start()] + '"enter": ' + key[1] + after, 'enter_boolean_key'
        if after.startswith('=') and not after.startswith(('==', '=>')):
            return before + ':' + after[1:], 'equals_separator'
        if after.startswith(('"', '{', '[')):
            return before + ':' + after, 'missing_colon'
    if message == "Expecting ',' delimiter":
        if after.startswith(('{', '[')) and previous.endswith(('}', ']')):
            return before + ',' + after, 'missing_comma'
        if after.startswith('"'):
            try:
                key, end = json.JSONDecoder().raw_decode(after)
            except json.JSONDecodeError:
                pass
            else:
                if isinstance(key, str) and after[end:].lstrip().startswith(':'):
                    return before + ',' + after, 'missing_comma'
    return None


def _missing_root_close(text, error):
    """Close one outer object only after a lexically complete string/container."""
    if (error.msg != "Expecting ',' delimiter" or error.pos != len(text)
            or not text.startswith('{') or not text.endswith(('"', ']', '}'))):
        return None
    stack, quoted, escaped = [], False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '{[':
            stack.append(char)
        elif char in '}]':
            if not stack or stack.pop() != {'}': '{', ']': '['}[char]:
                return None
    if not quoted and stack == ['{']:
        return text + '}', 'root_object_close'
    return None


def loads_model_json(response: str, *, repairs: list[str] | None = None,
                     allow_enter_key=False, perception_chunk=False):
    """Repair known syntax and require a complete document; callers check schemas.

    Do not invent values or complete truncated strings/nested containers. Original
    responses remain untouched. The repair list contains rule names, not data.
    """
    if not isinstance(response, str):
        raise TypeError('Model JSON response must be text')
    repairs = repairs if repairs is not None else []
    initial_repairs = len(repairs)
    text = response.strip()
    if text.startswith('\ufeff'):
        text = text[1:].lstrip()
        repairs.append('bom')
    fence = re.fullmatch(r'```(?:json)?[ \t]*\r?\n(.*?)\r?\n```', text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence[1].strip()
        repairs.append('json_fence')
    if perception_chunk and text.endswith('`'):
        text = text.rstrip('`').rstrip()
        repairs.append('perception_trailing_backtick')
    for _ in range(33):
        try:
            return loads_json(text)
        except json.JSONDecodeError as error:
            if len(repairs) - initial_repairs >= 32:
                break
            patch = _repair_at_error(text, error, allow_enter_key=allow_enter_key)
            if patch is None:
                patch = _missing_root_close(text, error)
            if patch is None and perception_chunk and re.match(r'^\s*\{\s*"observations"\s*:\s*\[', text):
                # Existing complete GPU observation suffixes only.
                if text.endswith('"}]'):
                    patch = text[:-2] + ']}', 'perception_closing_order'
                elif text.endswith('"}'):
                    patch = text[:-1] + ']}', 'perception_array_close'
            if patch is None:
                raise
            text, rule = patch
            repairs.append(rule)
    raise json.JSONDecodeError('Model JSON repair limit exceeded', text, 0)


def loads_action_json(response: str) -> tuple[object, bool]:
    """Compatibility wrapper for UActions callers."""
    repairs = []
    result = loads_model_json(response, repairs=repairs, allow_enter_key=True)
    return result, bool(repairs)
