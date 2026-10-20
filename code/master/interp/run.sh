#!/bin/zsh
# Builds every interpolated route in master/interp/routes. Each lab step skips finished work, so rerun after a crash.
#   zsh master/interp/run.sh
set -e
cd "$(dirname "$0")/../.."
lab() { uv run --no-project --python 3.12 --with-requirements requirements.txt python -I master/interp/lab.py "$@"; }
for r in r1-double r0-current r2-v46 r2-v46-blendwhip; do lab route $r; done
for v in 25 26; do
  [[ -f master/interp/routes/r4-p4$v.json ]] && continue
  lab prife p4$v prife-4.$v-1; lab midfeat p4$v; lab route r4-p4$v; lab drop p4$v
done
for k in x z u xzu; do
  [[ -f master/interp/routes/r3-$k.json ]] && continue
  flags=(${(s::)k}); lab rife $k ${flags/#/-}; lab midfeat $k; lab route r3-$k; lab drop $k
done
