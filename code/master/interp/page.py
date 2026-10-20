# Builds master/interp/index.html and its strips from the measured routes in master/interp/routes.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I master/interp/page.py
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import html, json, os, sys
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lab

ROUTES = lab.ROUTES
STRIPS = os.path.join(HERE, 'strips')
CODE = {'real': 'r', 'rife': 'R', 'hold': 'h', 'blend': 'b', 'native': 'n', 'end': 'e', 'x': 'x'}
NAMES = {'r': 'real 30 fps frame', 'R': 'RIFE in-between', 'h': 'held frame', 'b': '50/50 blend', 'n': 'native 60 fps frame', 'e': 'scene end hold'}


def load():
    out = []
    for name in lab.ROUTE:
        p = os.path.join(ROUTES, f'{name}.json')
        if os.path.exists(p):
            out.append((name, json.load(open(p))))
    return out


def scene_of(j):
    k = j // 2
    return next(s.name for s in lab.SC if lab.START[s.name] <= k < lab.START[s.name] + s.n)


def summary(rows):
    rows = [x for x in rows if x['how'] != 'end']  # every route holds the same frame across a scene boundary
    r = np.array([2 ** x['dip'] for x in rows])
    dip = np.array([x['dip'] for x in rows])
    cad = [x['cad'] for x in rows if x['cad'] is not None]
    hows = [x['how'] for x in rows]
    w = int(np.argmin(r))
    text = [2 ** x['dip'] for x in rows if scene_of(x['j']) in lab.TEXT]
    rest = [2 ** x['dip'] for x in rows if scene_of(x['j']) not in lab.TEXT]
    return dict(ratio=float(r.mean()), worst=float(r[w]), worst_j=rows[w]['j'], judder=float(np.abs(dip).mean()),
                soft=int((r < 0.7).sum()), cad=float(np.mean(cad)), text=float(np.mean(text)), rest=float(np.mean(rest)),
                mix={h: hows.count(h) for h in sorted(set(hows))})


def strip_grid(routes, F):
    rows = []
    for name, d in routes:
        tiles = [cv2.imdecode(np.frombuffer(bytes.fromhex(h), np.uint8), cv2.IMREAD_COLOR) for h in d['strips'][str(F)]]
        row = np.concatenate([cv2.resize(t, (480, 270), interpolation=cv2.INTER_AREA) for t in tiles], 1)
        label = lab.ROUTE[name]['label']
        cv2.rectangle(row, (0, 0), (8 + 9 * len(label), 26), (0, 0, 0), -1)
        cv2.putText(row, label, (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        rows.append(row)
    os.makedirs(STRIPS, exist_ok=True)
    path = os.path.join(STRIPS, f'f{F}.jpg')
    cv2.imwrite(path, np.concatenate(rows, 0), [cv2.IMWRITE_JPEG_QUALITY, 86])
    return os.path.relpath(path, HERE)


def pct(x):
    return f'{x:.2f}'


def main():
    routes = load()
    S = {name: summary(d['rows']) for name, d in routes}
    best = max(S, key=lambda n: (S[n]['ratio'] - S[n]['judder'] - 0.5 * S[n]['cad']))
    rows_html = []
    for name, d in routes:
        s = S[name]
        mix = ', '.join(f'{h} {c}' for h, c in s['mix'].items())
        rows_html.append(f"<tr><td>{html.escape(lab.ROUTE[name]['label'])}</td><td>{pct(s['ratio'])}</td><td>{pct(s['text'])}</td><td>{pct(s['rest'])}</td>"
                         f"<td>{pct(s['worst'])} <span class=m>@{s['worst_j']}</span></td><td>{s['soft']}</td><td>{pct(s['judder'])}</td>"
                         f"<td>{pct(s['cad'])}</td><td class=mix>{mix}</td></tr>")
    strips = [(F, strip_grid(routes, F)) for F in lab.strip_frames()]
    ally = json.load(open(os.path.join(ROUTES, 'alleyoop.json'))) if os.path.exists(os.path.join(ROUTES, 'alleyoop.json')) else {}
    ally_rows = []
    for way, d in ally.items():
        r = np.array([2 ** x['dip'] for x in d['rows']])
        cad = [x['cad'] for x in d['rows'] if x['cad'] is not None]
        ally_rows.append(f"<tr><td>{html.escape(d['label'])}</td><td>{np.mean(d['sharp']):.1f}</td><td>{np.min(d['sharp']):.1f}</td>"
                         f"<td>{pct(r.mean())}</td><td>{pct(np.abs(np.log2(r)).mean())}</td><td>{pct(np.mean(cad))}</td></tr>")
    data = dict(
        reel=dict(n=2 * lab.N, sources=[dict(name=n, label=lab.ROUTE[n]['label'], src=f'routes/{n}.mp4',
                                             how=''.join(CODE[h] for h in route_hows(d))) for n, d in routes],
                  marks=lab.strip_frames(), scenes=[[s.name, 2 * lab.START[s.name]] for s in lab.SC]),
        ally=dict(n=2 * next(s.n for s in lab.SC if s.name == 'alleyoop'),
                  sources=[dict(name=w, label=d['label'], src=f'routes/alleyoop-{w}.mp4', how='') for w, d in ally.items()], marks=[], scenes=[]),
        names=NAMES)
    page = open(os.path.join(HERE, 'page.tmpl.html')).read()
    page = (page.replace('%ROWS%', '\n'.join(rows_html)).replace('%ALLY%', '\n'.join(ally_rows))
            .replace('%STRIPS%', '\n'.join(f'<figure><img loading=lazy src="{p}" alt="Frames {F - 1}, {F} and {F + 1} on every route">'
                                            f'<figcaption>60 fps frames {F - 1}, {F}, {F + 1} ({scene_of(F)}). Rows top to bottom follow the table.</figcaption></figure>'
                                            for F, p in strips))
            .replace('%DATA%', json.dumps(data)).replace('%VERDICT%', verdict()))
    open(os.path.join(HERE, 'index.html'), 'w').write(page)
    print('best by score', best)
    for n in S:
        print(n, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in S[n].items()})


def verdict():
    p = os.path.join(HERE, 'verdict.html')
    return open(p).read() if os.path.exists(p) else ''


def route_hows(d):
    hows = ['native' if scene_of(j) in d['cfg'].get('native', ()) else 'real' for j in range(2 * lab.N)]
    for x in d['rows']:
        hows[x['j']] = x['how']
    return hows


if __name__ == '__main__':
    main()
