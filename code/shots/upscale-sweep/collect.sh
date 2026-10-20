#!/bin/sh
# Pulls finished sweep outputs from the Modal Volume and rebuilds runs.tsv from their sidecars. Safe to rerun.
# A sidecar's GPU seconds run from function entry to the output commit, so they leave out container boot; the
# billed line at the end is Modal's own figure for every seedvr2-sweep app today, the batches that produced
# nothing included.
set -e
cd "$(dirname "$0")"
mkdir -p out
for f in $(modal volume ls seedvr2-sweep-out / | grep -E '\.(mp4|json)$'); do
  [ -e "out/$f" ] || { modal volume get --force seedvr2-sweep-out "/$f" "out/.part-$f" >/dev/null && mv "out/.part-$f" "out/$f"; }
done
modal billing report --for today --resolution h --json > out/billing.json || echo '[]' > out/billing.json
python3 -I - <<'PY'
import glob, json
PRICE = {'H100': 0.001097, 'H200': 0.001261, 'B200': 0.001736}  # Modal list price, $ per GPU second
rows = ['variant\tshot\tdit\tresolution\tinput_noise\tlatent_noise\tgpu\tframes\tgpu_seconds\tcost_usd']
for p in sorted(glob.glob('out/*-*.json')):
    m = json.load(open(p))
    shot, v = m['key'].rsplit('-', 1)
    rows.append(f"{v}\t{shot}\t{m['dit']}\t{m['resolution']}\t{m['input_noise']}\t{m['latent_noise']}\t{m['gpu']}\t{m['frames']}"
                f"\t{m['gpu_seconds']:.0f}\t{m['gpu_seconds'] * PRICE[m['gpu']]:.2f}")
apps = {}
for r in json.load(open('out/billing.json')):
    if r['description'] == 'seedvr2-sweep':
        apps[r['object_id']] = apps.get(r['object_id'], 0) + float(r['cost'])
billed = sum(apps.values())
rows += [f'billed\t{a}\t\t\t\t\t\t\t\t{c:.2f}' for a, c in apps.items()]
open('runs.tsv', 'w').write('\n'.join(rows) + '\n')
print('\n'.join(rows)); print(f'measured ${sum(float(r.split(chr(9))[-1]) for r in rows[1:] if not r.startswith("billed")):.2f}, billed ${billed:.2f}')
PY
