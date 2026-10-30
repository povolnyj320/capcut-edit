#!/usr/bin/env python3
"""Check a reel's EDL before and after the build, without opening CapCut.

Run with the project venv:
  PY=.venv/bin/python
  $PY -I check.py ears <edl.json>             re-transcribe every planned clip as cut, next to the text the plan expects
  $PY -I check.py frames <edl.json> <out.jpg> t1 t2 ..   A-roll or B-roll + every graphic live at t + captions, tiled
  $PY -I check.py gaps <edl.json> [-db -32]   quiet stretches over 0.15 s on the reel's voice track
  $PY -I check.py still <edl.json> [-max 1.5]  any graphic (not name tags or the text hook) that holds still longer than that
  $PY -I check.py look <edl.json>             captions against the face every 0.5 s, and the outfit across the clips

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


def base_at(p, t):
    """What fills the frame at reel time t: (media, source time, scale, "broll" | "intro" | clip index).
    A push-in clip's scale grows across the clip as the build's keyframes do."""
    for b in p["broll"]:
        if b["t"] <= t < b["t"] + b["dur"]:
            return b["media"], b.get("src", 0) + t - b["t"], 1.0, "broll"
    if p.get("intro") and t < p["intro"]["dur"]:
        return str(Path(p["intro"]["media"]).expanduser()), t, 1.0, "intro"
    k, c = next((k, c) for k, c in enumerate(p["clips"]) if c["t"] <= t < c["t"] + c["dur"])
    sc = c["scale"] * (1 + min(0.08, 0.025 * c["dur"]) * (t - c["t"]) / c["dur"]) if c["push"] else c["scale"]
    return p["media"], c["s"] + t - c["t"], sc, k


def base_filter(sc):
    return (f"setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"scale=iw*{sc}:ih*{sc},crop=1080:1920")


def cmd_frames(a):
    edl = cc.load(a.edl)
    p = cc.build_plan(edl)
    gdir = Path(edl.get("graphics_dir", "~")).expanduser()
    tmp = Path(a.out).with_suffix("")
    tmp.mkdir(exist_ok=True)
    frames = []
    for k, t in enumerate(a.times):
        base, st, sc, _ = base_at(p, t)
        # setpts on every input: a seek into the DJI HEVC leaves an offset that makes overlay grab an earlier, blank frame
        ins = ["-ss", f"{st:.3f}", "-i", base]
        fc = f"[0:v]{base_filter(sc)}[v0]"
        last, n = "v0", 1
        for g in sorted([g for g in p["graphics"] if g["t"] <= t < g["t"] + g["dur"]], key=lambda g: g.get("lane", 0)):
            ins += ["-ss", f"{t - g['t']:.3f}", "-i", str(gdir / "out" / f"{g['name']}.{g.get('format', 'mov')}")]
            # where CapCut puts it: scaled about the centre, x/y in half-canvas units, y up (name tags, Oct 29:
            # drawn at the template's own spot, the tags looked clear of the captions and weren't)
            gs, gx, gy = g.get("scale", 1.0), g.get("x", 0.0), g.get("y", 0.0)
            ox, oy = 540 - 540 * gs + gx * 540, 960 - 960 * gs - gy * 960
            fc += (f";[{n}:v]setpts=PTS-STARTPTS,scale=iw*{gs}:ih*{gs}[g{n}];"
                   f"[{last}][g{n}]overlay=x={ox:.0f}:y={oy:.0f}[v{n}]")
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


# labels that are meant to sit: the text hook and name tags. Captions change with every word.
STILL_OK = ("text-hook.html", "captions-word.html", "captions-min.html")


def cmd_still(a):
    """Any graphic that sits on screen without changing (the creator, Oct 29: "the whiteboard doesn't change for a
    few seconds while I just talk over it", then the same night: "visuals that show up then just sit there"
    on all six Jett reels; this check had only looked at full whiteboards, so the floating visuals held still
    for up to 6 s unflagged). Lists every stretch over `-max` seconds where the graphic is visible and no
    pixel moves, in reel time. Name tags and text hooks are labels and are skipped."""
    import numpy as np
    edl = cc.load(a.edl)
    p = cc.build_plan(edl)
    gdir = Path(edl.get("graphics_dir", "~")).expanduser()
    found, W, H, FPS = 0, 216, 384, 10
    for g in p["graphics"]:
        html = g.get("html", "")
        if g.get("kind") == "captions" or html in STILL_OK or html.startswith(("name-", "intro-tag")):
            continue
        fmt = g.get("format", "mov")
        raw = subprocess.run([FF, "-v", "error", "-t", f"{g['dur']:.3f}", "-i", str(gdir / "out" / f"{g['name']}.{fmt}"),
                              "-vf", f"fps={FPS},scale={W}:{H}", "-pix_fmt", "rgba", "-f", "rawvideo", "-"],
                             capture_output=True).stdout
        fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 4).astype(np.int16)
        if fmt == "mp4":
            fr[..., 3] = 255
        pm = fr[..., :3] * fr[..., 3:] // 255                        # what shows over the footage
        vis = (fr[..., 3] > 16).sum(axis=(1, 2)) > 20
        moved = np.r_[True, (np.abs(np.diff(pm, axis=0)) > 6).any(axis=3).sum(axis=(1, 2)) > 2]
        still = vis & ~moved
        i = 0
        while i < len(still):
            j = i
            while j < len(still) and still[j]:
                j += 1
            if (j - i) / FPS > a.max:
                print(f"{g['name']:9} {g['t'] + i / FPS:6.2f}-{g['t'] + j / FPS:6.2f} ({(j - i) / FPS:.1f}s) holds still")
                found += 1
            i = max(j, i + 1)
    print(f"{found} graphic holds over {a.max} s")


FACES = Path.home() / ".cache/capcut-edit/faces"
SDK = "/Library/Developer/CommandLineTools/SDKs/MacOSX15.5.sdk"  # the default SDK doesn't match the compiler


def faces(paths):
    """macOS Vision face boxes [cx, cy, w, h] (0-1, top-left origin) for each image."""
    if not FACES.exists():
        FACES.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", "-sdk", SDK, str(Path(__file__).with_name("faces.swift")), "-o", str(FACES)], check=True)
    out = subprocess.run([str(FACES), *map(str, paths)], capture_output=True, text=True).stdout
    by = {json.loads(l)["f"]: json.loads(l)["faces"] for l in out.splitlines() if l.strip()}
    return [max(by.get(str(f), []), key=lambda b: b[2], default=None) for f in paths]


def caption_top(edl, gdir):
    g = next((g for g in edl.get("graphics", []) if g.get("kind") == "captions"), None)
    if not g:
        return None, 0
    css = g.get("css", "") + (gdir / g["html"]).read_text()
    m = re.search(r"\.cap-word\s*\{[^}]*?top:\s*(\d+)px", css)
    fs = re.search(r"\.cap-word\s*\{[^}]*?font-size:\s*(\d+)px", css)
    return int(m.group(1)), int(fs.group(1)) if fs else 80


def cmd_look(a):
    """Captions against the face, and the outfit across the creator's clips, every 0.5 s of the reel.
    Oct 29: "the captions are right over my chin" (the caption height was set on one shoot and another shoot
    sits lower in the frame), and "every video ends with a clip of me in a completely different outfit"
    (a CTA take from another day). Prints the lowest chin, the
    caption top that clears it, every frame where the captions touch a face, and any clip whose shirt
    colour doesn't match the rest."""
    import numpy as np
    edl = cc.load(a.edl)
    p = cc.build_plan(edl)
    gdir = Path(edl.get("graphics_dir", "~")).expanduser()
    tmp = Path(tempfile.mkdtemp(prefix="look-"))
    hide = [(g["t"], g["t"] + g["dur"]) for g in p["graphics"] if g.get("format") == "mp4"]  # opaque cutaways
    samples = []
    t = 0.05
    while t < p["end"] - 0.05:
        if not any(s <= t < e for s, e in hide):
            base, st, sc, who = base_at(p, t)
            if who != "broll":
                samples.append((t, base, st, sc, who))
        t += 0.5
    for c in p["clips"]:  # the end of every push-in, where the face is biggest
        if c["push"]:
            tt = c["t"] + c["dur"] - 0.05
            if not any(s <= tt < e for s, e in hide) and base_at(p, tt)[3] != "broll":
                samples.append((tt, *base_at(p, tt)))
    paths = []
    for k, (t, base, st, sc, who) in enumerate(samples):
        f = tmp / f"{k:04d}.png"
        subprocess.run([FF, "-v", "error", "-y", "-ss", f"{st:.3f}", "-i", base, "-vf", base_filter(sc),
                        "-frames:v", "1", str(f)], check=True)
        paths.append(f)
    boxes = faces(paths)
    top, size = caption_top(edl, gdir)
    chins, shirts, bad = [], {}, []
    for (t, base, st, sc, who), f, b in zip(samples, paths, boxes):
        if not b:
            continue
        cx, cy, w, h = b[0] * 1080, b[1] * 1920, b[2] * 1080, b[3] * 1920
        chin = cy + h / 2 + 0.06 * h     # Vision's box stops just above the chin
        chins.append((chin, t, who))
        if top is not None and top < chin + 30:
            bad.append(f"  {t:6.2f}s ({'intro' if who == 'intro' else 'clip ' + str(who)}) chin at {chin:.0f}, captions at {top}")
        if who != "intro":   # shirt: a patch under the chin, the width of the face
            img = subprocess.run([FF, "-v", "error", "-i", str(f), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                 capture_output=True).stdout
            px = np.frombuffer(img, np.uint8).reshape(1920, 1080, 3)
            y0, y1 = int(min(chin + 0.5 * h, 1880)), int(min(chin + 1.3 * h, 1919))
            x0, x1 = int(max(cx - w / 2, 0)), int(min(cx + w / 2, 1079))
            if y1 > y0 + 10:
                shirts.setdefault(who, []).append(np.median(px[y0:y1, x0:x1].reshape(-1, 3), axis=0))
    for part, cs in (("intro", [c for c in chins if c[2] == "intro"]), ("face", [c for c in chins if c[2] != "intro"])):
        if cs:
            low = max(cs)
            print(f"{part:5} lowest chin {low[0]:.0f} px at {low[1]:.2f}s, captions at {top} px (need {low[0] + 30:.0f} or lower)")
    print(f"{len(bad)} frames with the captions on a face" + ("" if bad else ""))
    for line in bad[:12]:
        print(line)
    if shirts:
        per = {k: np.median(v, axis=0) for k, v in shirts.items()}
        # the clip closest to all the others is the outfit of the shoot; anything far from it is another day
        ref = min(per.values(), key=lambda v: sum(np.abs(v - u).max() for u in per.values()))
        odd = [(k, v) for k, v in per.items() if np.abs(v - ref).max() > 45]
        print(f"outfit: {len(per)} clips, shirt colour {ref.astype(int).tolist()} (RGB)")
        for k, v in odd:
            c = p["clips"][k]
            print(f"  DIFFERENT OUTFIT clip {k} at {c['t']:.2f}s, shirt {v.astype(int).tolist()}: "
                  f"\"{' '.join(w['w'] for w in c['words'])[:60]}\"")


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
    sub.add_parser("look").add_argument("edl")
    s = sub.add_parser("still")
    s.add_argument("edl")
    s.add_argument("-max", type=float, default=1.5)
    a = ap.parse_args()
    {"ears": cmd_ears, "frames": cmd_frames, "gaps": cmd_gaps, "still": cmd_still, "look": cmd_look}[a.cmd](a)


if __name__ == "__main__":
    main()
