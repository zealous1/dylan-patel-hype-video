import sys, time
from faster_whisper import WhisperModel
m = WhisperModel("small.en", device="cpu", compute_type="int8")
for p in sys.argv[1:]:
    t = time.time()
    segs, _ = m.transcribe(p, word_timestamps=True, vad_filter=False)
    out = [f"[{s.start:.1f}-{s.end:.1f}] {s.text.strip()}" for s in segs]
    print(p.split("/")[-1], f"{time.time()-t:.1f}s", "|", " / ".join(out)[:300])
