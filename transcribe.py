#!/usr/bin/env python3
"""Word-level transcript + silence map for one clip, so cuts can be planned from text.

Run with the project venv:
  .venv/bin/python transcribe.py <media> [--model turbo|large]

Writes <work dir>/<stem>.words.json and <stem>.txt (the .txt is the
numbered, readable version used to pick keeps). Re-running reuses the cache.
"""
import argparse, json, os, re, subprocess, sys, tempfile
from pathlib import Path

import imageio_ffmpeg

WORK = Path(os.environ.get("CAPCUT_EDIT_WORK", "~/Movies/capcut-edit-work")).expanduser()
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
# On an 8 GB Mac the 4-bit turbo fits next to CapCut; the full model thrashes swap.
MODELS = {
    "turbo": "mlx-community/whisper-large-v3-turbo-q4",
    "small": "mlx-community/whisper-small.en-mlx-q4",
}
# Nudges Whisper to keep fillers and false starts instead of cleaning them up.
PROMPT = "Um, uh, so, like, I mean, you know, okay so, the the, I- I think, yeah."


def ffmpeg_on_path():
    # mlx_whisper shells out to `ffmpeg`; point it at the pip-installed binary.
    d = Path(tempfile.gettempdir()) / "capcut-edit-bin"
    d.mkdir(exist_ok=True)
    link = d / "ffmpeg"
    if not link.exists():
        link.symlink_to(FFMPEG)
    os.environ["PATH"] = f"{d}:{os.environ['PATH']}"


def silences(media, noise_db=-35, min_len=0.25):
    out = subprocess.run(
        [FFMPEG, "-hide_banner", "-nostats", "-i", media, "-vn",
         "-af", f"silencedetect=noise={noise_db}dB:d={min_len}", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    total = int(dur[1]) * 3600 + int(dur[2]) * 60 + float(dur[3]) if dur else None
    if len(ends) < len(starts) and total:
        ends.append(total)
    return [[round(s, 3), round(e, 3)] for s, e in zip(starts, ends)], total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--model", default="turbo", choices=MODELS)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    media = str(Path(a.media).expanduser().resolve())
    WORK.mkdir(parents=True, exist_ok=True)
    stem = Path(media).stem
    out_json, out_txt = WORK / f"{stem}.words.json", WORK / f"{stem}.txt"
    if out_json.exists() and not a.force:
        print(f"cached: {out_json}\n{out_txt}")
        return

    ffmpeg_on_path()
    import mlx_whisper

    sil, total = silences(media)
    r = mlx_whisper.transcribe(
        media, path_or_hf_repo=MODELS[a.model], word_timestamps=True,
        initial_prompt=PROMPT, condition_on_previous_text=False, language="en")

    words = []
    for seg in r["segments"]:
        for w in seg.get("words", []):
            words.append({"i": len(words), "w": w["word"].strip(),
                          "s": round(w["start"], 3), "e": round(w["end"], 3),
                          "p": round(w.get("probability", 1), 2)})
    json.dump({"media": media, "duration": total, "model": MODELS[a.model],
               "words": words, "silences": sil}, open(out_json, "w"), indent=1)

    # Readable version: one line per phrase, broken at pauses >= 0.4s.
    # Format: [first_word_index] start-end  text   (gap before line in brackets)
    lines, cur, prev_end = [], [], 0.0
    for w in words:
        if cur and w["s"] - cur[-1]["e"] >= 0.4:
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    with open(out_txt, "w") as f:
        f.write(f"# {media}\n# {total:.1f}s, {len(words)} words. [i] = index of first word on the line.\n")
        for ln in lines:
            gap = ln[0]["s"] - prev_end
            text = " ".join(x["w"] if x["p"] >= 0.5 else f"{x['w']}?" for x in ln)
            f.write(f"[{ln[0]['i']}-{ln[-1]['i']}] {ln[0]['s']:.2f}-{ln[-1]['e']:.2f} (+{gap:.1f}s) {text}\n")
            prev_end = ln[-1]["e"]
    print(f"{out_json}\n{out_txt}")


if __name__ == "__main__":
    sys.exit(main())
