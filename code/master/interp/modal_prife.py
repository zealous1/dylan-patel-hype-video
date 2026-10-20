# Practical-RIFE (hzwer) in PyTorch on a Modal GPU. The checkout and the weights only ever run in the container.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt \
#     python -I -m modal run --detach master/interp/modal_prife.py [--vers 4.25,4.26] [--scale 1.0]
# Each scene's take is decoded in the container with the same ffmpeg scale as render60.frames. The in-betweens land as
# lossless RGB x264 on the practical-rife-out Volume first, so a rerun after a dropped client skips finished scenes and
# only downloads, then in master/interp/work/prife-<ver>-<scale>/<scene>.mkv.
import json, os, pathlib, re, subprocess, sys, time
import modal

HERE = pathlib.Path(__file__).parent
PRIFE = 'https://github.com/hzwer/Practical-RIFE/archive/bbfd2ea90910789a860ea3e2b32a240cd577b75e.tar.gz'  # the commit both runs recorded
PRIFE_SHA256 = 'b4c979a966e0070ae513e3757bf4d41baaa53f1ab301d0c9d20c596329e32726'
W, H = 1920, 1080

image = (modal.Image.from_registry('nvidia/cuda:12.8.1-runtime-ubuntu24.04', add_python='3.11')
         .apt_install('curl', 'ffmpeg', 'unzip')
         .pip_install_from_requirements(str(HERE.parent.parent / 'modal' / 'requirements-prife.txt'),
                                        extra_index_url='https://download.pytorch.org/whl/cu128', extra_options='--require-hashes')
         .run_commands(f'curl -fsSL -o /tmp/prife.tar.gz {PRIFE} && echo "{PRIFE_SHA256}  /tmp/prife.tar.gz" | sha256sum -c -',
                       'mkdir -p /prife && tar -xzf /tmp/prife.tar.gz --strip-components=1 -C /prife && rm /tmp/prife.tar.gz',
                       f'echo {PRIFE} > /prife/COMMIT')
         .add_local_file(HERE / 'prife_worker.py', '/prife/prife_worker.py'))
weights = modal.Volume.from_name('practical-rife-weights', create_if_missing=True)
outs = modal.Volume.from_name('practical-rife-out', create_if_missing=True)
app = modal.App('practical-rife', image=image)


def drive_id(ver):
    # The id comes from the official README's own row for the version, not from anything typed here.
    for line in open('/prife/README.md'):
        if re.match(rf'^\s*v?{re.escape(ver)}\s*-', line):
            m = re.search(r'drive\.google\.com/file/d/([\w-]+)', line)
            if m:
                return m.group(1)
    raise SystemExit(f'no Google Drive link for {ver} in the README')


@app.function(timeout=900, volumes={'/weights': weights})
def fetch(ver: str) -> str:
    import glob, shutil
    import gdown
    dst = f'/weights/{ver}/train_log'
    if not os.path.exists(f'{dst}/flownet.pkl'):
        tmp = f'/tmp/dl-{ver}'
        os.makedirs(tmp, exist_ok=True)
        gdown.download(id=drive_id(ver), output=f'{tmp}/model.zip', quiet=True)
        subprocess.run(['unzip', '-q', '-o', f'{tmp}/model.zip', '-d', f'{tmp}/x'], check=True)
        pkl = [p for p in glob.glob(f'{tmp}/x/**/flownet.pkl', recursive=True) if '__MACOSX' not in p][0]
        os.makedirs(dst, exist_ok=True)
        for p in glob.glob(os.path.join(os.path.dirname(pkl), '*')):
            if os.path.isfile(p):
                shutil.copy(p, dst)
        weights.commit()
    return ' '.join(sorted(os.listdir(dst))) + ' commit ' + open('/prife/COMMIT').read().strip()


@app.function(gpu='L40S', timeout=1800, volumes={'/weights': weights, '/out': outs}, max_containers=6)
def interp(ver: str, scale: float, name: str, take: bytes, n: int | None, jobs: list | None) -> float:
    import shutil
    dst = f'/out/{ver}-{scale:g}/{name}.mkv'
    if os.path.exists(dst):
        return 0.0
    work = f'/tmp/{name}'
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree('/prife', work)
    shutil.copytree(f'/weights/{ver}/train_log', f'{work}/train_log', dirs_exist_ok=True)
    open(f'{work}/take.mp4', 'wb').write(take)
    cmd = ['ffmpeg', '-v', 'error', '-i', f'{work}/take.mp4', '-vf', f'scale={W}:{H}:flags=lanczos']
    cmd += ['-frames:v', str(n)] if n else []
    subprocess.run(cmd + ['-f', 'rawvideo', '-pix_fmt', 'bgr24', f'{work}/in.u8'], check=True)
    count = os.path.getsize(f'{work}/in.u8') // (W * H * 3)
    jobs = jobs or [[i, 0.5] for i in range(count - 1)]
    json.dump(jobs, open(f'{work}/jobs.json', 'w'))
    t = time.time()
    subprocess.run([sys.executable, 'prife_worker.py', 'in.u8', str(count), 'jobs.json', 'out.u8', str(scale)], check=True, cwd=work)
    secs = time.time() - t
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', '30', '-i', f'{work}/out.u8',
                    '-c:v', 'libx264rgb', '-qp', '0', '-preset', 'fast', f'{work}/out.mkv'], check=True)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy(f'{work}/out.mkv', dst)
    outs.commit()
    shutil.rmtree(work)
    return secs


@app.local_entrypoint()
def main(vers: str = '4.25,4.26', scale: float = 1.0, scenes: str = '', slow: bool = True):
    sys.path.insert(0, str(HERE.parent))
    import render60 as r6
    for v in vers.split(','):
        print(v, fetch.remote(v), flush=True)
    calls = []
    for v in vers.split(','):
        for s in r6.SCENES:
            if scenes and s.name not in scenes.split(','):
                continue
            calls.append((v, s.name, s.take, s.n, None))
            if s.slow and slow:
                count = len(r6.frames(s.slow))
                jobs = [[int(p), p - int(p)] for p in r6.slow_positions(count, 2 * s.n) if p % 1]
                calls.append((v, s.name + '-slow', s.slow, None, jobs))
    args = [(v, scale, nm, open(os.path.join(r6.R, take), 'rb').read(), n, jobs) for v, nm, take, n, jobs in calls]
    t = time.time()
    for (v, nm, *_), secs in zip(calls, interp.starmap(args)):
        print(v, nm, f'{secs:.1f} s on the GPU, {time.time() - t:.0f} s so far', flush=True)
    for v, nm, *_ in calls:
        d = HERE / 'work' / f'prife-{v}-{scale:g}'
        d.mkdir(parents=True, exist_ok=True)
        # The SDK's read_file stream dies on large files under starmap's event loop; the CLI does not.
        subprocess.run(['modal', 'volume', 'get', '--force', 'practical-rife-out', f'{v}-{scale:g}/{nm}.mkv', str(d / f'{nm}.mkv')],
                       check=True, capture_output=True)
