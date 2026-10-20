#!/bin/sh
# Downloads the open fonts the graphics use into ${FONT_DIR:-fonts}: Inter and Inter Display in place of
# Helvetica-family faces, Barlow and Barlow Condensed in place of DIN Condensed and Futura, and UnifrakturMaguntia for
# the newspaper masthead, which shots/newspaper/render.mjs serves to Chrome from here. All are SIL Open Font License 1.1, and each family's licence file is saved beside it. Every download is a fixed release or commit
# and is checked against its sha256 before use. Run from code/.
set -e
cd "$(dirname "$0")/.."
D=${FONT_DIR:-fonts}
mkdir -p "$D"
sha() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }
get() {  # url, file, sha256
  curl -fsSL -o "$2" "$1"
  [ "$(sha "$2")" = "$3" ] || { rm -f "$2"; echo "sha256 mismatch for $1" >&2; exit 1; }
}
if [ ! -e "$D/InterDisplay-Medium.ttf" ]; then
  T=$(mktemp -d)
  get https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip "$T/inter.zip" \
    9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e
  unzip -q -j -o "$T/inter.zip" 'extras/ttf/InterDisplay-*.ttf' 'extras/ttf/Inter-Bold.ttf' 'LICENSE.txt' -d "$T/inter"
  cp "$T"/inter/InterDisplay-*.ttf "$T/inter/Inter-Bold.ttf" "$D/"
  cp "$T/inter/LICENSE.txt" "$D/Inter-OFL.txt"
  rm -rf "$T"
fi
G=https://raw.githubusercontent.com/google/fonts/6cdf01867df0813c2390f90dff7dc66c87f14cf7/ofl
while read -r f out sum; do
  [ -e "$D/$out" ] || get "$G/$f" "$D/$out" "$sum"
done <<'LIST'
barlow/Barlow-Medium.ttf Barlow-Medium.ttf f8906f762cb73dca441da034bc363b2d8e2e68bc10d5c05e58717646c20cc4b4
barlow/Barlow-Bold.ttf Barlow-Bold.ttf 84e6a4d61e7c3e21f3c50ea6a4f7e5303a3467864c038be6ea3759bab8d547f9
barlow/OFL.txt Barlow-OFL.txt 186d750eb496a4c17a76385f82be6aea2ac1cf2de074a811d63786cf374ea73f
barlowcondensed/BarlowCondensed-Bold.ttf BarlowCondensed-Bold.ttf e476562ec9c1e16cf16475895b511f08c804f438cc9a9f80a44ea50a0eeb5b65
barlowcondensed/BarlowCondensed-ExtraBold.ttf BarlowCondensed-ExtraBold.ttf 724c9c25952d5f4a2d87185d9767aa006144c5f0d944dc05bf7d5d603551c260
unifrakturmaguntia/UnifrakturMaguntia-Book.ttf UnifrakturMaguntia-Book.ttf d64afc0547059dd2e4a78da48bda0aba0a9901be58c7f8c201a8b2b6b4492cc8
unifrakturmaguntia/OFL.txt UnifrakturMaguntia-OFL.txt 96199bf9ff12dd471a66911dee95440737b437e7f5a6fd30e9e950c16d66e8df
LIST
ls "$D"
