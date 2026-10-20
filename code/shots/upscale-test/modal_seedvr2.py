# SeedVR2 upscale of the soft Wan shots on a Modal H100, since the 3B model at 1080p runs the Mac out of memory
# during VAE encoding. Unpacks SeedVR2 at a pinned commit into the image; the weights download once into a Volume.
#   modal run shots/upscale-test/modal_seedvr2.py [--model 3b|7b] [--shots datacenter,alleyoop,celebrate]
# Inputs come from shots/upscale-test/in/<shot>.mp4, outputs land in shots/upscale-test/out/<shot>-seedvr2-<model>.mp4.
import os, pathlib, time
import modal

SEEDVR2 = 'https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler/archive/4490bd1f482e026674543386bb2a4d176da245b9.tar.gz'  # main of 2025-12-24
SEEDVR2_SHA256 = '73ebee9da0bfa6876613e23a5f898ebd72ea938eb1d26d9322063172bfb788be'
HERE = pathlib.Path(__file__).parent
MODELS = {'3b': 'seedvr2_ema_3b_fp16.safetensors', '7b': 'seedvr2_ema_7b_fp16.safetensors'}

# The workspace's debian_slim is Debian 11, whose security packages are gone from the mirror, so build on Ubuntu.
image = (modal.Image.from_registry('nvidia/cuda:12.8.1-runtime-ubuntu24.04', add_python='3.11')
         .apt_install('curl', 'ffmpeg', 'libgl1', 'libglib2.0-0')
         .pip_install_from_requirements(str(HERE.parent.parent / 'modal' / 'requirements-seedvr2.txt'),
                                        extra_index_url='https://download.pytorch.org/whl/cu128', extra_options='--require-hashes')
         .run_commands(f'curl -fsSL -o /tmp/seedvr2.tar.gz {SEEDVR2} && echo "{SEEDVR2_SHA256}  /tmp/seedvr2.tar.gz" | sha256sum -c -',
                       'mkdir -p /seedvr2 && tar -xzf /tmp/seedvr2.tar.gz --strip-components=1 -C /seedvr2 && rm /tmp/seedvr2.tar.gz',
                       'rm -rf /seedvr2/docs /seedvr2/example_workflows'))
weights = modal.Volume.from_name('seedvr2-weights', create_if_missing=True)
app = modal.App('seedvr2-upscale', image=image)

@app.function(gpu='H100', timeout=3600, volumes={'/weights': weights})
def upscale(name: str, video: bytes, model: str) -> tuple[bytes, float]:
    import subprocess
    os.makedirs('/tmp/in', exist_ok=True)
    src, out = f'/tmp/in/{name}.mp4', f'/tmp/{name}-out.mp4'
    open(src, 'wb').write(video)
    n = int(subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
                            '-of', 'csv=p=0', src], capture_output=True, text=True, check=True).stdout.strip())
    # One batch over the whole shot keeps it temporally coherent; SeedVR2 wants 4k+1 frames per batch.
    batch = ((n - 1) // 4) * 4 + 1
    t = time.time()
    subprocess.run(['python', '/seedvr2/inference_cli.py', src, '--output', out, '--output_format', 'mp4', '--video_backend', 'ffmpeg',
                    '--model_dir', '/weights', '--dit_model', MODELS[model], '--resolution', '1080', '--batch_size', str(batch),
                    '--color_correction', 'lab'], check=True, cwd='/seedvr2')
    weights.commit()
    return open(out, 'rb').read(), time.time() - t

@app.local_entrypoint()
def main(model: str = '3b', shots: str = 'datacenter,alleyoop,celebrate'):
    names = shots.split(',')
    vids = [open(HERE / 'in' / f'{s}.mp4', 'rb').read() for s in names]
    (HERE / 'out').mkdir(exist_ok=True)
    for s, (data, secs) in zip(names, upscale.starmap([(s, v, model) for s, v in zip(names, vids)])):
        (HERE / 'out' / f'{s}-seedvr2-{model}.mp4').write_bytes(data)
        print(f'{s}: {secs:.0f} s on the GPU', flush=True)
