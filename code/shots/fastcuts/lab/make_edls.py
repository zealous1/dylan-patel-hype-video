# Writes edl-v15a to edl-v15d: v14's clips and tags with a lab block each (see build.py, 'Podcast lab').
#   python3 shots/fastcuts/lab/make_edls.py
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import copy, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
v14 = json.load(open(os.path.join(HERE, '..', 'edl-v14.json')))
# Tuned against lab/data/lab.json: the first pass (face_L 55, room 0.62, subject_C 24, skin ceiling 27) left the
# faces at Lab chroma 28 against the original's 21 and the rooms at 1.7 times darker than the face against 2.2.
COLOUR = {'contrast': 1.15, 'face_L': 55, 'room': 0.5, 'room_min': 0.66, 'neutral_a': 0.0, 'neutral_b': 3.0,
          'subject_C': 21, 'room_C': 15, 'skin_C': 23}
PUNCH = [4.50, 5.73, 6.15]  # beats that land inside a clip; every other beat is a cut
VARIANTS = {
    'a': {'note': 'A, direction and colour only. v14 framing and eased pans, each rightward pan turned to travel left, the subject-aware grade.',
          'camera': {'mode': 'v14'},
          'moves': ['left', 'left', 'up', 'left', 'left', 'down', 'left', 'left', 'up', 'left']},
    'b': {'note': 'B, face-matched zoom-through. Every cut puts his face on one screen point at one size while the zoom keeps going, alternating push-in and pull-out like the original\'s hoop cut.',
          'camera': {'mode': 'zoomthrough', 'h': 0.32, 'v': 2.2, 'anchor': [0.46, 0.40],
                     'cuts': [[0.26, 1.5], 'in', 'out', 'in', [0.42, 2.5], [0.32, 2.5, [0.5, 0.47]], 'out', 'in', 'out', 'in', 'out', [0.3, 0]]},
          'hero': {'tau': 0.2},
          'moves': ['zoom'] * 10},
    'c': {'note': 'C, hybrid. Each clip lands with his face on one screen point at one size, then v14\'s push about the face; eased pans kept, only left, up or down.',
          'camera': {'mode': 'land', 'h': 0.28, 'anchor': [0.46, 0.40]},
          'hero': {'h': 0.28, 'at': [0.46, 0.40], 'tau': 0.15},
          'moves': ['left', 'up', 'left', 'down', 'left', 'up', 'left', 'down', 'left', 'up']},
    'd': {'note': 'D, one camera travelling right. The newspaper\'s exit pan never stops; each clip\'s face drifts left at one speed and one size, hard cuts on the beat with a landing punch.',
          'camera': {'mode': 'travel', 'h': 0.30, 'anchor': [0.46, 0.40], 'speed': 0.45, 'creep': 0.04},
          'hero': {'h': 0.30, 'at': [0.62, 0.40], 'tau': 0.18},
          'moves': ['cut', 'cut', 'cut', 'left', 'left', 'cut', 'cut', 'cut', 'cut', 'cut']},
}
for v, spec in VARIANTS.items():
    e = copy.deepcopy(v14)
    e['section']['output'] = f'fastcuts-v15{v}.mp4'
    lab = {k: spec[k] for k in ('camera', 'moves', 'hero') if k in spec}
    e['section']['lab'] = dict(lab, colour=COLOUR, jensen_k=0.95, punch=PUNCH)
    e['note'] = e['note'] + ' v15' + v + ': ' + spec['note']
    json.dump(e, open(os.path.join(HERE, '..', f'edl-v15{v}.json'), 'w'), indent=2, ensure_ascii=False)
    print(f'edl-v15{v}.json')

# Round 2 (Zeal made B the podcast section): B2 is B with the Jensen slot face-matched. The cut lands on Jensen's face
# at B's anchor and size, the zoom pulls out to the whole stage on the strong hit at 2.04, then pushes into the belt
# plate for the slam one beat later at 2.46 (face, wide and belt in the 0.42 s before 2.04 would zoom at about 50% a
# frame, four times the original's fastest). P1 to P4 are B2 with treatments that make him pop (build.py, treat()).
# The gtc slot's source tag, drawn like every podcast clip's (the big channel name over the search). Zeal confirmed
# the search; Jensen's entity id is from arcmira.resolve("Jensen Huang") on 2026-10-17.
JENSEN_TAG = {
    'provenance': {'tool': 'arcmira_execute_read', 'method': 'arcmira.search', 'run': '2026-10-17',
                   'filter': 'by (speakerIds) = ent_122115 Jensen Huang; channel NVIDIA UCHuiy8bXnmK5nisYHUd1J5g',
                   'input': {'query': 'semianalysis', 'speakerIds': ['ent_122115'], 'channelIds': ['UCHuiy8bXnmK5nisYHUd1J5g']},
                   'result': {'video_id': 'jw_o0xr8MWU', 'video_title': 'NVIDIA GTC Keynote 2026', 'channel_name': 'NVIDIA',
                              'published_at': '2026-03-16', 'start_seconds': 3817.36,
                              'text': 'Blackwell NVLink 72 was 35 times perf per watt. Nobody believed me. And then SemiAnalysis came out and Dylan Patel had a quote. He accused me of sandbagging.'},
                   'note': 'Premium transcript with Jensen labelled by Zeal; checked by Zeal in Arcmira search, index catching up'},
}
BEATS_IN_CLIPS = [4.50, 5.73, 6.15, 6.57]  # the beats inside a clip (every other beat is a cut); 6.57 is the hero's kick
TREATS = {
    'b2': {'note': 'B2, Jensen face-matched. The zoom-through lands on his face, pulls out to the whole stage on the strong hit, then slams into the belt a beat later.'},
    'p1': {'note': 'P1, print room. The room in the warm monochrome print of the opener and the Worn ending, Dylan in full colour.',
           'treat': {'matte': 'seg', 'print': 1.0}},
    'p2': {'note': 'P2, halation wrap. A warm halation and light wrap off his silhouette in the reel\'s orange glow.',
           'treat': {'matte': 'seg', 'halo': 1.0}},
    'p3': {'note': 'P3, burn hits. On each beat inside a clip, two frames of the opener\'s burn on his silhouette.',
           'treat': {'matte': 'seg', 'burn': BEATS_IN_CLIPS}},
    'p4': {'note': 'P4, print room, half halation and burn hits. The room recedes into the print, a soft warm wrap holds his edge, and the beats burn him in.',
           'treat': {'matte': 'seg', 'print': 1.0, 'halo': 0.5, 'burn': BEATS_IN_CLIPS}},
}
for v, spec in TREATS.items():
    e = json.load(open(os.path.join(HERE, '..', 'edl-v15b.json')))
    e['section']['output'] = f'fastcuts-v16-{v}.mp4'
    for c in e['clips']:
        if c.get('provenance'):  # Zeal, 2026-10-17: every search query on screen is lowercase, and so is its record
            c['provenance']['input']['query'] = c['provenance']['input']['query'].lower()
        if c.get('kind') == 'jensen-zoom':
            c.pop('beat2')
            c.update(reveal=2.04, hit=2.46, **JENSEN_TAG)
    e['section']['hud']['lower'] = True
    if 'treat' in spec:
        e['section']['lab']['treat'] = spec['treat']
    e['note'] = e['note'] + ' v16-' + v + ': ' + spec['note']
    json.dump(e, open(os.path.join(HERE, '..', f'edl-v16-{v}.json'), 'w'), indent=2, ensure_ascii=False)
    print(f'edl-v16-{v}.json')

# Round 4 (Zeal locked B2 with P2): a Super Saiyan aura behind him that pops on in one frame on the hero's kick at
# 6.57 s and holds to the cut. Extents are in face heights: up is the shell's height over his head, side its width
# beside him; flow is how far the tongues' curves rise per frame.
AURA = {'on': 6.57, 'up': 1.1, 'side': 0.22, 'amp': 0.7, 'flow': 0.05}
AURAS = {
    's1': {'note': 'S1, the classic gold Super Saiyan aura.', 'aura': AURA},
    's2': {'note': 'S2, S1 with thin lightning crackling inside the aura, Super Saiyan 2 style.', 'aura': dict(AURA, arcs=5)},
    's3': {'note': 'S3, a tighter, thinner aura at about half the height.', 'aura': dict(AURA, up=0.55, side=0.11)},
}
for v, spec in AURAS.items():
    e = json.load(open(os.path.join(HERE, '..', 'edl-v16-p2.json')))
    e['section']['output'] = f'fastcuts-v18-{v}.mp4'
    e['section']['lab']['aura'] = spec['aura']
    e['note'] = e['note'] + ' v18-' + v + ': ' + spec['note']
    json.dump(e, open(os.path.join(HERE, '..', f'edl-v18-{v}.json'), 'w'), indent=2, ensure_ascii=False)
    print(f'edl-v18-{v}.json')
