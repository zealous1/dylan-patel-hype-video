# Writes shots/upscale-sweep/index.html from metrics.json, the run sidecars in out/, the crops and verdict.json.
#   python3 -I shots/upscale-sweep/page.py
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import glob, html, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
PRICE = {'H100': 0.001097, 'H200': 0.001261, 'B200': 0.001736}
NAMES = {'lanczos': 'Lanczos (current)', 'A': 'A 7B', 'B': 'B 7B sharp', 'C': 'C 7B sharp 1440', 'D': 'D 7B sharp noise 0.1'}
metrics = json.load(open(f'{HERE}/metrics.json'))
verdict = json.load(open(f'{HERE}/verdict.json'))
runs = {json.load(open(p))['key']: json.load(open(p)) for p in glob.glob(f'{HERE}/out/*-*.json')}
esc = html.escape

def table(shot):
    m = metrics[shot]
    base = m['lanczos']
    rows = []
    for v, x in m.items():
        r = runs.get(f'{shot}-{v}')
        gpu = f"{r['gpu_seconds']:.0f} s {r['gpu']}" if r else ''
        cost = f"${r['gpu_seconds'] * PRICE[r['gpu']]:.2f}" if r else ''
        win = ' class="win"' if v == verdict['scenes'].get(shot, {}).get('winner') else ''
        rows.append(f"<tr{win}><td>{esc(NAMES.get(v, v))}</td><td>{x['sharp']:.0f}</td><td>{x['sharp'] / base['sharp']:.1f}x</td>"
                    f"<td>{x['hf']:.2f}</td><td>{x['flicker']:.2f}</td><td>{x['flicker_per_hf']:.2f}</td><td>{gpu}</td><td>{cost}</td></tr>")
    return ('<table><thead><tr><th>variant</th><th>Laplacian var</th><th>vs Lanczos</th><th>detail (hf)</th><th>shimmer</th>'
            '<th>shimmer per detail</th><th>GPU</th><th>cost</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>')

def player(title, vids):
    cells = ''.join(f'<figure><figcaption>{esc(label)}</figcaption><video muted playsinline loop preload="auto" src="{esc(src)}"></video></figure>'
                    for label, src in vids)
    return (f'<div class="sync"><div class="controls"><button data-a="play">Play</button><button data-a="back">-1 frame</button>'
            f'<button data-a="fwd">+1 frame</button><label>speed <select><option>0.25</option><option>0.5</option><option selected>1</option></select></label>'
            f'<input type="range" min="0" max="1000" value="0"><span class="t"></span></div><div class="grid">{cells}</div></div>')

def crops(shot):
    labels = sorted({os.path.basename(p)[len(shot) + 1:].rsplit('-', 1)[0] for p in glob.glob(f'{HERE}/crops/{shot}-*-lanczos.png')})
    out = []
    for lab in labels:
        imgs = ''.join(f'<figure><figcaption>{esc(NAMES.get(v, v))}</figcaption><img src="crops/{shot}-{lab}-{v}.png" width="400" height="225" alt="{esc(lab)} {v}"></figure>'
                       for v in metrics[shot] if os.path.exists(f'{HERE}/crops/{shot}-{lab}-{v}.png'))
        out.append(f'<h4>{esc(lab.replace("_", " "))}</h4><div class="crops">{imgs}</div>')
    return ''.join(out)

def runs_table():
    rows = [l.split('\t') for l in open(f'{HERE}/runs.tsv').read().strip().split('\n')]
    head, body = rows[0], rows[1:]
    total = sum(float(r[-1]) for r in body if r[0] == 'billed')
    tr = ''.join('<tr>' + ''.join(f'<td>{esc(c)}</td>' for c in r) + '</tr>' for r in body)
    return ('<table><thead><tr>' + ''.join(f'<th>{esc(h)}</th>' for h in head) + '</tr></thead><tbody>' + tr +
            f'<tr class="win"><td>billed total</td>' + '<td></td>' * (len(head) - 2) + f'<td>{total:.2f}</td></tr></tbody></table>')

secs = []
for shot, info in verdict['scenes'].items():
    if shot not in metrics:
        continue
    vids = [(NAMES.get(v, v), f'web/{shot}-{v}.mp4') for v in metrics[shot]]
    body = (f'<section id="{shot}"><h2>{esc(shot)}</h2><p>{esc(info["source"])}</p><p><b>Winner {esc(NAMES.get(info["winner"], info["winner"]))}.</b> {esc(info["why"])}</p>'
            + table(shot) + '<h3>Upscaled generation, synced</h3>' + player(shot, vids) + '<h3>1:1 crops</h3>' + crops(shot))
    if info.get('takes'):
        body += '<h3>Rebuilt take against the take render.py uses now</h3>' + ''.join(
            f'<p class="note">{esc(t["note"])}</p>' + player(shot, [('current ' + t['old'], '../../' + t['old']), ('new ' + t['new'], '../../' + t['new'])])
            for t in info['takes'])
    secs.append(body + '</section>')

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Upscale Sweep</title>
<style>
:root{{--bg:#f6f5f1;--fg:#16161a;--muted:#5d5d66;--card:#fff;--line:#dedbd3;--win:#e7f3e3}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#111114;--fg:#ececf0;--muted:#a0a0aa;--card:#1a1a20;--line:#2d2d36;--win:#1d2d1d}}}}
:root[data-theme="dark"]{{--bg:#111114;--fg:#ececf0;--muted:#a0a0aa;--card:#1a1a20;--line:#2d2d36;--win:#1d2d1d}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 Helvetica,Arial,sans-serif}}
main{{max-width:1600px;margin:0 auto;padding:24px 16px 60px}}h2{{font-size:20px;margin:40px 0 6px;border-top:1px solid var(--line);padding-top:18px}}
h3{{font-size:15px;margin:22px 0 8px}}h4{{font-size:13px;margin:12px 0 4px;color:var(--muted);font-weight:normal}}.note{{color:var(--muted)}}
table{{border-collapse:collapse;font-variant-numeric:tabular-nums;display:block;overflow-x:auto;max-width:100%}}
td,th{{border-bottom:1px solid var(--line);padding:4px 10px;text-align:right;white-space:nowrap}}td:first-child,th:first-child{{text-align:left}}
tr.win td{{background:var(--win);font-weight:bold}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:8px}}
figure{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px}}figcaption{{font-size:12px;color:var(--muted);margin-bottom:4px;overflow-wrap:anywhere}}
video{{width:100%;display:block;background:#000;border-radius:4px}}
.crops{{display:flex;gap:8px;overflow-x:auto;max-width:100%;padding-bottom:4px}}.crops img{{display:block;width:400px;max-width:none;height:225px;image-rendering:pixelated}}
.controls{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:6px 0}}.controls input{{flex:1;min-width:160px}}
button,select{{font:inherit;padding:5px 10px;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px}}
</style></head><body><main>
<h1>Upscale sweep</h1>\n{verdict['intro']}
<h2>Runs</h2><p class="note">GPU seconds run from function entry to the saved output at Modal list price. The billed rows are Modal&#39;s own figure per app, which adds container boot and image load, and include two batches that produced nothing (one lost its client, one failed to save its outputs) and a smoke test.</p>
{runs_table()}
{''.join(secs)}
</main><script>
const FPS = 30;
document.querySelectorAll('.sync').forEach(box => {{
  const vs = [...box.querySelectorAll('video')], lead = vs[0];
  const range = box.querySelector('input'), t = box.querySelector('.t'), play = box.querySelector('[data-a=play]');
  const seek = s => vs.forEach(v => {{ v.currentTime = Math.max(0, Math.min(s, (v.duration || 0) - 0.001)); }});
  const frame = () => Math.floor(lead.currentTime * FPS + 1e-3);
  play.onclick = () => {{
    if (lead.paused) {{ seek(lead.currentTime); vs.forEach(v => v.play()); play.textContent = 'Pause'; }}
    else {{ vs.forEach(v => v.pause()); seek(lead.currentTime); play.textContent = 'Play'; }}
  }};
  box.querySelector('[data-a=back]').onclick = () => {{ vs.forEach(v => v.pause()); play.textContent = 'Play'; seek((frame() - 1 + 0.5) / FPS); }};
  box.querySelector('[data-a=fwd]').onclick = () => {{ vs.forEach(v => v.pause()); play.textContent = 'Play'; seek((frame() + 1 + 0.5) / FPS); }};
  box.querySelector('select').onchange = e => vs.forEach(v => v.playbackRate = +e.target.value);
  range.oninput = () => {{ vs.forEach(v => v.pause()); play.textContent = 'Play'; seek(range.value / 1000 * (lead.duration || 0)); }};
  lead.ontimeupdate = () => {{
    if (lead.duration) range.value = lead.currentTime / lead.duration * 1000;
    t.textContent = 'frame ' + frame();
    if (!lead.paused) vs.slice(1).forEach(v => {{ if (Math.abs(v.currentTime - lead.currentTime) > 0.05) v.currentTime = lead.currentTime; }});
  }};
}});
</script></body></html>
'''
open(f'{HERE}/index.html', 'w').write(page)
print('wrote', f'{HERE}/index.html')
