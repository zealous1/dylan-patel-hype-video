#!/bin/sh
# Rebuilds the hashed locks from the .in files. Run from code/. --exclude-newer keeps every package, direct or not,
# to releases made before the date, so nothing in a lock is newer than a week when it was made.
set -e
cd "$(dirname "$0")/.."
for n in requirements requirements-matte requirements-stems; do
  uv pip compile "$n.in" --generate-hashes --universal --python-version 3.12 --exclude-newer 2026-10-10 -q -o "$n.txt"
done
# The Modal image locks target the container, Python 3.11 on linux x86_64, with torch from the CUDA 12.8 index.
# pip in the image picks the best match across both indexes, and so does the resolver here. --upgrade stops uv
# reading the old lock, which fails under --exclude-newer for the files the CUDA index lists without a publish time.
for n in modal/requirements-seedvr2 modal/requirements-prife; do
  uv pip compile "$n.in" --upgrade --generate-hashes --python-version 3.11 --python-platform x86_64-manylinux_2_28 \
    --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match \
    --exclude-newer 2026-10-10 -q -o "$n.txt"
done
