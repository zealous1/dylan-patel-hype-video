# SeedVR2 sweep over the soft Wan generations on Modal, extended from shots/upscale-test/modal_seedvr2.py.
# Each run upscales a whole 720p generation (not the sped-up take cut from it), so the model sees the slow, smooth
# motion; rebuild.py re-cuts the takes from the result with trace.py's frame picks.
#   modal run --detach shots/upscale-sweep/modal_seedvr2.py --variants A,B [--shots rim,alleyoop]
#   then shots/upscale-sweep/collect.sh
# Each result is written to the Volume seedvr2-sweep-out by the GPU function itself, with a JSON sidecar holding its
# GPU seconds, so a dead client loses nothing; collect.sh pulls them and rebuilds runs.tsv. A (shot, variant) whose
# output already exists locally or in the Volume is skipped, so a relaunch only runs what is missing.
import os, pathlib, time
import modal

SEEDVR2 = 'https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler/archive/4490bd1f482e026674543386bb2a4d176da245b9.tar.gz'  # main of 2025-12-24
SEEDVR2_SHA256 = '73ebee9da0bfa6876613e23a5f898ebd72ea938eb1d26d9322063172bfb788be'
HERE = pathlib.Path(__file__).parent
R = HERE.parent.parent
DIT = {'3b': 'seedvr2_ema_3b_fp16.safetensors', '7b': 'seedvr2_ema_7b_fp16.safetensors',
       '7b_sharp': 'seedvr2_ema_7b_sharp_fp16.safetensors'}
SHOTS = {
    'rim': 'shots/rim/out/wan-3.0-noframes-slow-focus.mp4',
    'celebrate': 'shots/celebrate/out/wan-3.0-novideo-min.mp4',
    'fadeout': 'shots/fadeout/out/wan-3.0-noframes-slow-focus.mp4',
    'alleyoop': 'shots/alleyoop/out/wan-3.0-noframes-slow-focus-2.mp4',
    'backdown': 'shots/backdown/out/wan-3.0-noframes-slow-focus.mp4',
    'fadeaway': 'shots/fadeaway/out/wan-3.0-noframes-slow-focus.mp4',
    'jersey': 'shots/jersey/out/wan-3.0-noframes-slow-focus.mp4',
    'intro': 'shots/intro/out/wan-3.0-noframes-strong-slow.mp4',
}
FRAMES = {'alleyoop': 150, 'backdown': 150, 'intro': 300}  # the rest are 90
# (dit, short side, input noise, latent noise)
VARIANTS = {
    'A': ('7b', 1080, 0.0, 0.0),
    'B': ('7b_sharp', 1080, 0.0, 0.0),
    'C': ('7b_sharp', 1440, 0.0, 0.0),
    'D': ('7b_sharp', 1080, 0.1, 0.0),
}

def gpu_for(shot, res):
    # One whole-shot batch of 153 frames at 1080, or 93 at 1440, is past what an H100's 80 GB was trusted with.
    n = FRAMES.get(shot, 90)
    if n > 160 or (n > 100 and res > 1080):
        return 'B200'
    return 'H200' if n > 100 or res > 1080 else 'H100'

image = (modal.Image.from_registry('nvidia/cuda:12.8.1-runtime-ubuntu24.04', add_python='3.11')
         .apt_install('curl', 'ffmpeg', 'libgl1', 'libglib2.0-0')
         .pip_install_from_requirements(str(HERE.parent.parent / 'modal' / 'requirements-seedvr2.txt'),
                                        extra_index_url='https://download.pytorch.org/whl/cu128', extra_options='--require-hashes')
         .run_commands(f'curl -fsSL -o /tmp/seedvr2.tar.gz {SEEDVR2} && echo "{SEEDVR2_SHA256}  /tmp/seedvr2.tar.gz" | sha256sum -c -',
                       'mkdir -p /seedvr2 && tar -xzf /tmp/seedvr2.tar.gz --strip-components=1 -C /seedvr2 && rm /tmp/seedvr2.tar.gz',
                       'rm -rf /seedvr2/docs /seedvr2/example_workflows'))
weights = modal.Volume.from_name('seedvr2-weights', create_if_missing=True)
results = modal.Volume.from_name('seedvr2-sweep-out', create_if_missing=True)
app = modal.App('seedvr2-sweep', image=image)
PRICE = {'H100': 0.001097, 'H200': 0.001261, 'B200': 0.001736}  # Modal list price, $ per GPU second

def upscale(key: str, video: bytes, dit: str, resolution: int, input_noise: float, latent_noise: float, gpu: str):
    import json, shutil, subprocess
    t = time.time()
    if os.path.exists(f'/out/{key}.json'):
        return json.load(open(f'/out/{key}.json'))
    os.makedirs('/tmp/in', exist_ok=True)
    src, out = f'/tmp/in/{key}.mp4', f'/tmp/{key}-out.mp4'
    open(src, 'wb').write(video)
    n = int(subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
                            '-of', 'csv=p=0', src], capture_output=True, text=True, check=True).stdout.strip())
    batch = ((n + 2) // 4) * 4 + 1
    subprocess.run(['python', '/seedvr2/inference_cli.py', src, '--output', out, '--output_format', 'mp4', '--video_backend', 'ffmpeg',
                    '--model_dir', '/weights', '--dit_model', DIT[dit], '--resolution', str(resolution), '--batch_size', str(batch),
                    '--uniform_batch_size', '--color_correction', 'lab', '--input_noise_scale', str(input_noise),
                    '--latent_noise_scale', str(latent_noise), '--10bit'], check=True, cwd='/seedvr2')
    shutil.copyfile(out, f'/out/{key}.mp4')
    meta = {'key': key, 'dit': dit, 'resolution': resolution, 'input_noise': input_noise, 'latent_noise': latent_noise,
            'gpu': gpu, 'frames': n, 'gpu_seconds': round(time.time() - t, 1)}
    json.dump(meta, open(f'/out/{key}.json', 'w'))
    results.commit()
    return meta

# One function per GPU type, since a spawn from inside a container cannot retarget the GPU with with_options.
KW = dict(timeout=3600, memory=65536, volumes={'/weights': weights, '/out': results})

@app.function(gpu='H100', **KW)
def upscale_h100(*a): return upscale(*a)

@app.function(gpu='H200', **KW)
def upscale_h200(*a): return upscale(*a)

@app.function(gpu='B200', **KW)
def upscale_b200(*a): return upscale(*a)

GPU_FNS = {'H100': upscale_h100, 'H200': upscale_h200, 'B200': upscale_b200}

@app.function(timeout=7200)
def sweep(jobs: list):
    # Runs remotely so the fan-out outlives the client: --detach keeps only the last call alive, which is this one.
    calls = {j[0]: GPU_FNS[j[-1]].spawn(*j) for j in jobs}
    out = {}
    for key, call in calls.items():
        try:
            out[key] = call.get()
        except Exception as e:  # one OOM must not hide the other runs' results
            out[key] = f'FAILED {type(e).__name__}: {e}'
    return out

@app.local_entrypoint()
def main(variants: str = 'A,B', shots: str = 'rim,celebrate,fadeout,alleyoop'):
    done = {e.path.strip('/') for e in results.listdir('/')}
    jobs = []
    for v in variants.split(','):
        d, res, inn, ln = VARIANTS[v]
        for s in shots.split(','):
            key = f'{s}-{v}'
            if (HERE / 'out' / f'{key}.mp4').exists() or f'{key}.json' in done:
                print(f'{key}: have it', flush=True)
                continue
            jobs.append((key, (R / SHOTS[s]).read_bytes(), d, res, inn, ln, gpu_for(s, res)))
    for key, meta in sweep.remote(jobs).items():
        print(key, meta, flush=True)
