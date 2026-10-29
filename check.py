#!/usr/bin/env python3
"""Check a reel's EDL before and after the build, without opening CapCut.

Run with the project venv:
  PY=.venv/bin/python
  $PY -I check.py ears <edl.json>             re-transcribe every planned clip as cut, next to the text the plan expects
  $PY -I check.py frames <edl.json> <out.jpg> t1 t2 ..   A-roll or B-roll + every graphic live at t + captions, tiled
  $PY -I check.py gaps <edl.json> [-db -32]   quiet stretches over 0.15 s on the reel's voice track
  $PY -I check.py still <edl.json> [-max 1.5]  whiteboard stretches that hold still longer than that

`ears` is the one that matters most. Whisper's word times are only a guide: it folds retakes into one
line, stretches a word across a pause, and runs "So," into the next word. On Oct 27 the plan read clean
on all four reels, and `ears` still found a doubled line ("And the most efficient way..." twice), two
false starts kept as clips, "So" leaking into two hooks, and a list word cut in half. Fix those by
correcting the word times in the reel's own copy of the words file, then run `ears` again.
"""
import argparse, difflib, json, os, re, subprocess, sys, tempfile
from pathlib import Path

import imageio_ffmpeg

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capcut as cc  # noqa: E402

FF = imageio_ffmpeg.get_ffmpeg_exe()
MODEL = "mlx-community/whisper-large-v3-turbo-q4"  # the same 4-bit model transcribe.py uses


def cmd_ears(a):
    import mlx_whisper
    d = Path(tempfile.gettempdir()) / "capcut-edit-bin"  # mlx_whisper shells out to `ffmpeg`
    d.mkdir(exist_ok=True)
    if not (d / "ffmpeg").exists():
        (d / "ffmpeg").symlink_to(FF)
    os.environ["PATH"] = f"{d}:{os.environ['PATH']}"
    p = cc.build_plan(cc.load(a.edl))
    norm = lambda s: re.sub(r"[^a-z0-9% ]", "", s.lower().replace("-", " ")).split()
    wav, bad = d / "clip.wav", 0
    for c in p["clips"]:
        subprocess.run([FF, "-v", "error", "-y", "-ss", f"{c['s']:.3f}", "-t", f"{c['dur']:.3f}", "-i", p["media"],
                        "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
        heard = mlx_whisper.transcribe(str(wav), path_or_hf_repo=MODEL, language="en")["text"].strip()
        want = " ".join(w["w"] for w in c["words"])
        r = difflib.SequenceMatcher(None, norm(want), norm(heard)).ratio()
        flag = "" if r > 0.85 else "  <<< CHECK"
        bad += bool(flag)
        print(f"{c['t']:6.2f}  {r:.2f}{flag}\n   plan : {want}\n   heard: {heard}")
    print(f"{len(p['clips'])} clips, {bad} to check")


def cmd_frames(a):
    edl = cc.load(a.edl)
    p = cc.build_plan(edl)
    gdir = Path(edl.get("graphics_dir", "~")).expanduser()
    tmp = Path(a.out).with_suffix("")
    tmp.mkdir(exist_ok=True)
    frames = []
    for k, t in enumerate(a.times):
        base = None
        for b in p["broll"]:
            if b["t"] <= t < b["t"] + b["dur"]:
                base, st, sc = b["media"], b.get("src", 0) + t - b["t"], 1.0
        if not base and p.get("intro") and t < p["intro"]["dur"]:
            base, st, sc = str(Path(p["intro"]["media"]).expanduser()), t, 1.0
        if not base:
            c = next(c for c in p["clips"] if c["t"] <= t < c["t"] + c["dur"])
            base, st, sc = p["media"], c["s"] + t - c["t"], c["scale"]
        # setpts on every input: a seek into the DJI HEVC leaves an offset that makes overlay grab an earlier, blank frame
        ins = ["-ss", f"{st:.3f}", "-i", base]
        fc = (f"[0:v]setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
              f"scale=iw*{sc}:ih*{sc},crop=1080:1920[v0]")
        last, n = "v0", 1
        for g in sorted([g for g in p["graphics"] if g["t"] <= t < g["t"] + g["dur"]], key=lambda g: g.get("lane", 0)):
            ins += ["-ss", f"{t - g['t']:.3f}", "-i", str(gdir / "out" / f"{g['name']}.{g.get('format', 'mov')}")]
            fc += f";[{n}:v]setpts=PTS-STARTPTS[g{n}];[{last}][g{n}]overlay[v{n}]"
            last, n = f"v{n}", n + 1
        fc += f";[{last}]scale=360:640,drawtext=text='{t:.1f}':x=6:y=6:fontsize=22:fontcolor=yellow[o]"
        fr = tmp / f"{k:02d}.jpg"
        subprocess.run([FF, "-v", "error", "-y", *ins, "-filter_complex", fc, "-map", "[o]", "-frames:v", "1", str(fr)], check=True)
        frames.append(fr)
    cols = min(5, len(frames))
    layout = "|".join(f"{(i % cols) * 360}_{(i // cols) * 640}" for i in range(len(frames)))
    fc = "".join(f"[{i}:v]" for i in range(len(frames))) + f"xstack=inputs={len(frames)}:layout={layout}:fill=black" if len(frames) > 1 else "null"
    subprocess.run([FF, "-v", "error", "-y", *sum([["-i", str(f)] for f in frames], []), "-filter_complex", fc, a.out], check=True)
    print(a.out)


def cmd_gaps(a):
    import numpy as np
    p = cc.build_plan(cc.load(a.edl))
    db = cc.loudness(p["media"])
    seq, cuts = [], []
    for c in p["clips"]:
        seq.extend(db[int(round(c["s"] * 100)):int(round((c["s"] + c["dur"]) * 100))])
        cuts.append(round(c["t"] + c["dur"], 2))
    q, i, found = np.array(seq) < a.db, 0, 0
    while i < len(q):
        j = i
        while j < len(q) and q[j]:
            j += 1
        if j - i > 15:
            t0, t1 = i / 100, j / 100
            near = [c for c in cuts if t0 - 0.1 <= c <= t1 + 0.1]
            print(f"{t0:6.2f}-{t1:6.2f} ({t1 - t0:.2f}s)" + (f"  AT CUT {near}" if near else "  inside a line"))
            found += 1
        i = max(j, i + 1)
    print(f"{found} quiet stretches over 0.15 s, {len(p['clips'])} clips")


def cmd_still(a):
    """Whiteboards that hold still while the creator talks over them (the creator, Oct 29: "the whiteboard doesn't change
    for a few seconds while I just talk over it"). Lists every stretch over `-max` seconds, in reel time."""
    edl = cc.load(a.edl)
    p = cc.build_plan(edl)
    gdir = Path(edl.get("graphics_dir", "~")).expanduser()
    found = 0
    for g in p["graphics"]:
        if g.get("format") != "mp4":
            continue
        r = subprocess.run([FF, "-v", "info", "-t", f"{g['dur']:.3f}", "-i", str(gdir / "out" / f"{g['name']}.mp4"),
                            "-vf", f"scale=270:-1,freezedetect=n=0.002:d={a.max}", "-f", "null", "-"], capture_output=True, text=True)
        starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", r.stderr)]
        ends = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", r.stderr)]
        ends += [g["dur"]] * (len(starts) - len(ends))  # a hold that runs to the end of the cutaway
        for s0, s1 in zip(starts, ends):
            print(f"{g['name']:6} {g['t'] + s0:6.2f}-{g['t'] + s1:6.2f} ({s1 - s0:.1f}s) holds still")
            found += 1
    print(f"{found} whiteboard holds over {a.max} s")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ears").add_argument("edl")
    f = sub.add_parser("frames")
    f.add_argument("edl")
    f.add_argument("out")
    f.add_argument("times", nargs="+", type=float)
    g = sub.add_parser("gaps")
    g.add_argument("edl")
    g.add_argument("-db", type=float, default=-32)
    s = sub.add_parser("still")
    s.add_argument("edl")
    s.add_argument("-max", type=float, default=1.5)
    a = ap.parse_args()
    {"ears": cmd_ears, "frames": cmd_frames, "gaps": cmd_gaps, "still": cmd_still}[a.cmd](a)


if __name__ == "__main__":
    main()
