#!/usr/bin/env python3
"""Check a storyboard.json against schema.json and against the links between its parts.

    python3 -I validate.py [storyboard.json] [schema.json]

Exit 0 when it passes, 1 with one line per problem. Standard library only: it covers the subset of
JSON Schema that schema.json uses, then the rules a schema cannot say (picks name real takes, take
status follows the checkpoints, ids are unique, times sit on the clock).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def check(node, schema, root, path, out):
    if '$ref' in schema:
        ref = schema['$ref'].split('/')[1:]
        target = root
        for part in ref:
            target = target[part]
        check(node, target, root, path, out)
        rest = {k: v for k, v in schema.items() if k not in ('$ref', 'description')}
        if not rest:
            return
        schema = rest
    if 'const' in schema and node != schema['const']:
        out.append(f'{path}: must be {schema["const"]!r}')
    if 'enum' in schema and node not in schema['enum']:
        out.append(f'{path}: {node!r} is not one of {schema["enum"]}')
    t = schema.get('type')
    if t:
        types = t if isinstance(t, list) else [t]
        ok = {
            'object': isinstance(node, dict), 'array': isinstance(node, list), 'string': isinstance(node, str),
            'boolean': isinstance(node, bool), 'null': node is None,
            'integer': isinstance(node, int) and not isinstance(node, bool),
            'number': isinstance(node, (int, float)) and not isinstance(node, bool),
        }
        if not any(ok[x] for x in types):
            out.append(f'{path}: expected {t}, got {type(node).__name__}')
            return
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        if 'minimum' in schema and node < schema['minimum']:
            out.append(f'{path}: {node} is below {schema["minimum"]}')
        if 'exclusiveMinimum' in schema and node <= schema['exclusiveMinimum']:
            out.append(f'{path}: {node} must be above {schema["exclusiveMinimum"]}')
    if isinstance(node, str) and 'pattern' in schema and not re.search(schema['pattern'], node):
        out.append(f'{path}: {node!r} does not match {schema["pattern"]}')
    if isinstance(node, list):
        if len(node) < schema.get('minItems', 0):
            out.append(f'{path}: needs at least {schema["minItems"]} items')
        if 'maxItems' in schema and len(node) > schema['maxItems']:
            out.append(f'{path}: allows at most {schema["maxItems"]} items')
        if 'items' in schema:
            for i, item in enumerate(node):
                check(item, schema['items'], root, f'{path}[{i}]', out)
    if isinstance(node, dict):
        for key in schema.get('required', []):
            if key not in node:
                out.append(f'{path}: missing {key}')
        props = schema.get('properties', {})
        extra = schema.get('additionalProperties', True)
        for key, value in node.items():
            if key in props:
                check(value, props[key], root, f'{path}.{key}', out)
            elif extra is False:
                out.append(f'{path}: unknown field {key}')
            elif isinstance(extra, dict):
                check(value, extra, root, f'{path}.{key}', out)
        if 'if' in schema:
            probe = []
            check(node, schema['if'], root, path, probe)
            if not probe and 'then' in schema:
                check(node, schema['then'], root, path, out)


def links(doc, out):
    slots = {s['id']: s for s in doc['slots']}
    if len(slots) != len(doc['slots']):
        out.append('slots: duplicate slot ids')
    end = doc['clock']['duration_s']
    for s in doc['slots']:
        ids = [t['id'] for t in s['takes']]
        if len(set(ids)) != len(ids):
            out.append(f'slot {s["id"]}: duplicate take ids')
        if not s['t0'] < s['t1']:
            out.append(f'slot {s["id"]}: t0 must be before t1')
    asset_ids = [a['id'] for a in doc.get('assets', [])]
    if len(set(asset_ids)) != len(asset_ids):
        out.append('assets: duplicate ids')
    for a in doc.get('assets', []):
        for sid in a.get('used_by', []):
            if sid not in slots:
                out.append(f'asset {a["id"]}: used_by names unknown slot {sid}')
    cps = doc['checkpoints']
    if len({c['id'] for c in cps}) != len(cps):
        out.append('checkpoints: duplicate ids')
    for c in cps:
        length = c.get('duration_s', end)
        for sid, tid in (c.get('picks') or {}).items():
            if sid not in slots:
                out.append(f'checkpoint {c["id"]}: picks unknown slot {sid}')
            elif tid not in {t['id'] for t in slots[sid]['takes']}:
                out.append(f'checkpoint {c["id"]}: slot {sid} picks unknown take {tid}')
        for sid, (b0, b1) in (c.get('bounds') or {}).items():
            if sid not in slots:
                out.append(f'checkpoint {c["id"]}: bounds unknown slot {sid}')
            if not b0 < b1 or b1 > length + 1e-6:
                out.append(f'checkpoint {c["id"]}: bounds for {sid} are off the clock')
    last = cps[-1].get('picks')
    if last is None:
        out.append('the last checkpoint must record its picks')
        return
    earlier = {(sid, tid) for c in cps[:-1] for sid, tid in (c.get('picks') or {}).items()}
    for s in doc['slots']:
        for t in s['takes']:
            key = (s['id'], t['id'])
            if t['status'] == 'picked' and last.get(s['id']) != t['id']:
                out.append(f'take {s["id"]}/{t["id"]}: picked but not in the last checkpoint')
            if last.get(s['id']) == t['id'] and t['status'] != 'picked':
                out.append(f'take {s["id"]}/{t["id"]}: in the last checkpoint but marked {t["status"]}')
            if t['status'] == 'superseded' and key not in earlier:
                out.append(f'take {s["id"]}/{t["id"]}: superseded but never picked')
        own = [cp.get('bounds', {}).get(s['id'], [s['t0'], s['t1']]) for cp in cps if s['id'] in (cp.get('picks') or {})]
        if s['id'] in last and [s['t0'], s['t1']] != own[-1]:
            out.append(f'slot {s["id"]}: t0 and t1 must match the last checkpoint')
        if s['t1'] > end + 1e-6 and s['id'] in last:
            out.append(f'slot {s["id"]}: ends after the clock')


def main(argv):
    data = argv[1] if len(argv) > 1 else os.path.join(HERE, 'storyboard.json')
    schema_path = argv[2] if len(argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(data)), 'schema.json')
    if not os.path.exists(schema_path):
        schema_path = os.path.join(HERE, 'schema.json')
    doc = json.load(open(data))
    schema = json.load(open(schema_path))
    out = []
    check(doc, schema, schema, '$', out)
    if not out:
        links(doc, out)
    for line in out:
        print(line)
    takes = sum(len(s['takes']) for s in doc.get('slots', []))
    print(f'{os.path.basename(data)}: {"FAIL" if out else "ok"}, {len(doc.get("slots", []))} slots, {takes} takes, '
          f'{len(doc.get("assets", []))} assets, {len(doc.get("checkpoints", []))} checkpoints')
    return 1 if out else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
