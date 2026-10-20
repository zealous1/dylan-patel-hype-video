# Collects the lab's measurements into lab/data/lab.json for index.html: colour per version, the original's shots
# with measured motion, where his face starts in each clip, the direction audits and the beats.
#   python3 shots/fastcuts/lab/stats.py      (after measure.py, audit.py and the v15 builds)
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, os, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, 'data')
load = lambda n: json.load(open(os.path.join(D, n)))
T0 = 13.84
beats = [round((b - T0) * 30, 1) for b in json.load(open(os.path.join(HERE, '..', '..', '..', 'analysis', 'audio.json')))['beats'] if T0 - 0.01 <= b < T0 + 7]
v14 = json.load(open(os.path.join(HERE, '..', 'edl-v14.json')))
pod = set()
for c in v14['clips']:
    if not c.get('kind'):
        pod.update(range(round(c['slot_in'] * 30), round(c['slot_out'] * 30)))

def colour(rows, only=None):
    rs = [r for r in rows if r['y'] < 110 and (only is None or r['f'] in only)]
    m = lambda k, src=None: round(st.mean([(r.get(src) or {}).get(k) if src else r.get(k) for r in rs
                                            if ((r.get(src) or {}).get(k) if src else r.get(k)) is not None]), 1)
    out = {'y': m('y'), 'contrast': m('ystd'), 'vivid': m('vivid'), 'sat': m('sat'), 'warm': m('warm'), 'tint': m('tint')}
    try:
        out.update(face_y=m('y', 'face_c'), face_vivid=m('vivid', 'face_c'), room_y=m('y', 'bg_c'))
        out['ratio'] = round(out['face_y'] / out['room_y'], 2)
    except st.StatisticsError:
        pass
    return out

versions = {'original': 'The LeBron edit', 'v14': 'v14 (current)', 'v15a': 'A', 'v15b': 'B', 'v15c': 'C', 'v15d': 'D'}
versions.update({'v16-b2': 'B2', 'v16-p1': 'B2 P1 print room', 'v16-p2': 'B2 P2 halation wrap', 'v16-p3': 'B2 P3 burn hits', 'v16-p4': 'B2 P4 print, half halo, burns'})
table = []
for k, label in versions.items():
    rows = load(f'{k}.json')['rows']
    row = {'key': k, 'label': label, 'all': colour(rows)}
    if k != 'original':
        row['podcast'] = colour(rows, pod)
    table.append(row)

# The original's shots, marked from the contact sheet; motion is the median of the matched-corner measures inside each.
orig = load('original.json')['rows']
SHOTS = [
    (0, 18, 'Dunk', 'LeBron at the rim, right of centre and low'),
    (19, 23, 'Zoom whip', 'Blur, lands on the beat at 24'),
    (24, 46, 'Arena ceiling', 'No subject; the lights'),
    (47, 53, 'Purple whip', 'Blur into the All-Star game'),
    (54, 83, 'All-Star drive', 'LeBron right of centre; flash at 81'),
    (84, 120, 'Ball in the dark', 'The ball top centre, followed down to the hoop'),
    (121, 123, 'Punch in', 'Hard push into the backboard on the beat'),
    (124, 155, 'Hoop hold', 'Hoop top centre, filling the frame'),
    (156, 158, 'Match cut', 'Same hoop point and size across the cut'),
    (159, 179, 'Court pull-out', 'The hoop holds top centre while the court opens out'),
    (180, 186, 'Vertical whip', 'Same court'),
    (187, 208, 'Tilt and white', 'The picture rises faster and faster into white'),
]
shots = []
for a, b, name, subject in SHOTS:
    ms = [r['mo'] for r in orig[a + 1:b + 1] if r.get('mo') and r['mo']['n'] >= 100]
    mo = {'dx': round(st.median([m['dx'] for m in ms]), 1), 'dy': round(st.median([m['dy'] for m in ms]), 1),
          'zoom': round((st.median([m['s'] for m in ms]) - 1) * 100, 2)} if len(ms) >= 2 else None
    near = [x for x in beats if a - 3 <= x <= b + 3]
    shots.append({'from': a, 'to': b, 'name': name, 'subject': subject, 'motion': mo, 'beats': near})
# The zoom across the hoop cut, frame by frame (percent per frame; negative is pulling out).
hoop_zoom = [{'f': r['f'], 'zoom': round((r['mo']['s'] - 1) * 100, 1)} for r in orig[148:181] if r.get('mo') and r['mo']['n'] >= 30]

starts = {}
for v in 'abcd':
    p = load(f'path-fastcuts-v15{v}.json')
    starts['v14' if v == 'a' else f'v15{v}'] = [{'src': k, 'f0': x['f0'], 'face': x['boxes'][0][:2], 'h': round(x['boxes'][0][3], 3)}
                                                  for k, x in sorted(p.items(), key=lambda kv: kv[1]['f0'])]
audits = {k: load(f'audit-{k}.json') for k in versions}
json.dump({'beats': beats, 'colour': table, 'shots': shots, 'hoop_zoom': hoop_zoom, 'starts': starts, 'audits': audits},
          open(os.path.join(D, 'lab.json'), 'w'), indent=1)
for r in table:
    print(r['label'].ljust(16), r['all'], r.get('podcast', ''))
