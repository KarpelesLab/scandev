import sys
import numpy as np
from faster_whisper import WhisperModel
AUDIO = np.fromfile("audio.f32", dtype=np.float32)
try:
    m = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
    segs, info = m.transcribe(AUDIO, language="en", vad_filter=True)
    segs = list(segs)
except Exception as e:
    print("cuda failed:", e, file=sys.stderr)
    m = WhisperModel("small.en", device="cpu", compute_type="int8")
    segs, info = m.transcribe(AUDIO, language="en", vad_filter=True)
    segs = list(segs)
with open("transcript.txt", "w") as f:
    for s in segs:
        f.write(f"[{int(s.start)//60:02d}:{int(s.start)%60:02d}] {s.text.strip()}\n")
print(len(segs), "segments")
