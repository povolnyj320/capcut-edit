#!/usr/bin/env python3
"""Build and inspect CapCut desktop projects by writing their draft files directly.

Run with the project venv (setup.sh makes it):
  PY=.venv/bin/python
  $PY capcut.py list                      recent projects
  $PY capcut.py new <name> --from <empty> a new empty project, cloned from an empty one of yours (CapCut must be closed)
  $PY capcut.py inspect <project>         tracks and clips of one project
  $PY capcut.py style <ref> [<ref2>..]    save clip/caption/audio templates from the creator's own edits
  $PY capcut.py plan <edl.json>           dry run: print the clips and captions a build would make
  $PY capcut.py build <edl.json>          write the timeline (CapCut must be closed)
  $PY capcut.py diff <project>            what the creator changed since the last build
  $PY capcut.py thumbs <folder>           one frame per clip, to pick B-roll by looking
  $PY capcut.py graphics <edl.json>       render the HyperFrames graphics with cue times from the words

Times in CapCut drafts are microseconds. The EDL format is in README.md.
"""
import argparse, copy, difflib, json, os, re, shutil, subprocess, sys, time, uuid
from pathlib import Path

ROOT = Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
WORK = Path(os.environ.get("CAPCUT_EDIT_WORK", "~/Movies/capcut-edit-work")).expanduser()  # transcripts, backups, staged media
STYLE = Path(__file__).resolve().parent / "style.json"
US = 1_000_000
ACCENT = [0xEE / 255, 0x28 / 255, 0x24 / 255]  # key-word colour in captions; the EDL's "accent" (hex) overrides it


def set_accent(hex_color):
    global ACCENT
    h = hex_color.lstrip("#")
    ACCENT = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def uid():
    return str(uuid.uuid4()).upper()


def load(p):
    with open(p) as f:
        return json.load(f)


def save(p, d):
    with open(p, "w") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))


def capcut_running():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def project_dir(name):
    p = ROOT / name
    if p.is_dir():
        return p
    for d in load(ROOT / "root_meta_info.json")["all_draft_store"]:
        if d["draft_name"] == name:
            return Path(d["draft_fold_path"])
    sys.exit(f"No CapCut project named {name!r} in {ROOT}")


def draft_paths(pdir):
    """Root draft_info.json plus the per-timeline copy CapCut 9.x keeps in Timelines/<id>/."""
    paths = [pdir / "draft_info.json"]
    pj = pdir / "Timelines/project.json"
    if pj.exists():
        t = pdir / "Timelines" / load(pj)["main_timeline_id"] / "draft_info.json"
        if t.exists():
            paths.append(t)
    return paths


def index(d):
    ids = {}
    for k, v in d["materials"].items():
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict) and "id" in x:
                    ids[x["id"]] = (k, x)
    return ids


def probe(path):
    import imageio_ffmpeg
    path = str(Path(path).expanduser())
    # a Desktop or Documents folder that syncs with iCloud can hold evicted ("dataless") files; reading one hangs until it downloads
    if os.stat(path).st_flags & 0x40000000:
        sys.exit(f"{path} is stored in iCloud only. Download it (Finder: right-click, Download Now), then build again.")
    err = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", path],
                         capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    if not m:
        sys.exit(f"Can't read media: {path}")
    dur = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    v = re.search(r"Video: .*?(\d{3,5})x(\d{3,5})", err)
    w, h = (int(v[1]), int(v[2])) if v else (0, 0)
    rot = re.search(r"rotation of (-?[\d.]+)|rotate\s*:\s*(-?\d+)", err)
    if rot and abs(round(float(rot[1] or rot[2]))) % 180 == 90:
        w, h = h, w
    return {"duration": round(dur * US), "width": w, "height": h,
            "has_audio": "Audio:" in err, "has_video": bool(v)}


# ---------- templates ----------

def unit(d, ids, seg):
    """A segment with every material it touches, including text materials inside a caption template."""
    mats = [ids[seg["material_id"]]] + [ids[r] for r in seg["extra_material_refs"] if r in ids]
    k, m = ids[seg["material_id"]]
    if k == "text_templates":
        for r in m.get("text_info_resources", []):
            if r["text_material_id"] in ids:
                mats.append(ids[r["text_material_id"]])
    return {"segment": seg, "materials": [list(x) for x in mats]}


def clone(u):
    """Deep copy of a unit with fresh ids everywhere (ids are unique UUID strings, so replace is safe)."""
    s = json.dumps(u)
    olds = {u["segment"]["id"]} | {m["id"] for _, m in u["materials"]}
    for k, m in u["materials"]:
        for r in m.get("text_info_resources", []) if k == "text_templates" else []:
            olds.add(r["id"])
    for o in olds:
        s = s.replace(o, uid())
    return json.loads(s)


def cmd_style(a):
    st = {"from": a.projects, "saved": time.strftime("%Y-%m-%d")}
    for name in a.projects:
        d = load(project_dir(name) / "draft_info.json")
        ids = index(d)
        st.setdefault("canvas", d["canvas_config"])
        st.setdefault("fps", d["fps"])
        hdr = lambda t: {k: v for k, v in t.items() if k != "segments"}
        vids = [t for t in d["tracks"] if t["type"] == "video" and t["segments"]]
        if vids and "video" not in st:
            seg = next(s for s in vids[0]["segments"] if ids[s["material_id"]][1].get("type") == "video")
            st["video"] = unit(d, ids, seg) | {"track": hdr(vids[0])}
        if len(vids) > 1 and "broll" not in st:
            st["broll"] = unit(d, ids, vids[1]["segments"][0]) | {"track": hdr(vids[1])}
        texts = sorted((t for t in d["tracks"] if t["type"] == "text" and t["segments"]),
                       key=lambda t: -len(t["segments"]))
        if texts and "caption" not in st:
            st["caption"] = unit(d, ids, texts[0]["segments"][0]) | {"track": hdr(texts[0])}
        auds = [t for t in d["tracks"] if t["type"] == "audio" and t["segments"]]
        if auds and "audio" not in st:
            st["audio"] = unit(d, ids, auds[0]["segments"][0]) | {"track": hdr(auds[0])}
        adj = [t for t in d["tracks"] if t["type"] == "adjust" and t["segments"]]
        if adj and "grade" not in st:  # their color adjustment layer (LUT + HSL)
            st["grade"] = unit(d, ids, adj[0]["segments"][0]) | {"track": hdr(adj[0])}
    missing = [k for k in ("video", "broll", "caption", "audio") if k not in st]
    save(STYLE, st)
    print(f"Saved {STYLE}" + (f" (missing: {', '.join(missing)})" if missing else ""))


# ---------- planning ----------

def loudness(media):
    """Audio level in dB every 10 ms (cached next to the transcript)."""
    import numpy as np
    import imageio_ffmpeg
    cache = WORK / f"{Path(media).stem}.db.npy"
    if cache.exists():
        return np.load(cache)
    raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", media, "-vn", "-ac", "1",
                          "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = len(x) // 160
    db = 20 * np.log10(np.sqrt((x[:n * 160].reshape(n, 160) ** 2).mean(1)) + 1e-6)
    np.save(cache, db)
    return db


def tighten(c, db, pad_in, breath, limit_e, ring=0.03):
    """Trim a clip to the creator's voice: start on their first sound, end once their last word has rung out.

    The silence map counts breaths and shuffles as sound, which left up to 0.5 s of dead air
    at cuts (the creator, Oct 25: "too much of a pause before I start talking again"). Cutting right
    at the voice then chopped words mid-decay, which sounded choppy ("make it smoother"), so
    the end runs on until the word has mostly decayed (max `ring`, 0.03 s; the clip's fade-out takes
    the rest). A 0.1 s breath after each sentence still read as a pause ("I still think there are
    pauses that are too long"), so `breath` is 0 unless an EDL asks for it. Thresholds are relative to their speaking level (90th
    percentile) and room tone (median), so they hold across rooms and mics.
    """
    import numpy as np
    speech, room = float(np.percentile(db, 90)), float(np.percentile(db, 50))
    # the end needs 30 ms of real voice: breath noise after their last word sits around speech - 18
    on, off = speech - 14, speech - 16
    f0 = int(c["s"] * 100)
    f1 = int(min(c["e"], c["words"][0]["e"] + 0.3) * 100)
    for f in range(f0, f1 - 2):
        if (db[f:f + 3] > on).all():  # 30 ms of voice, not a click
            c["s"] = max(c["s"], f / 100 - pad_in)
            break
    if c["words"][-1].get("hard_end"):
        # "hard_end": true ends the clip on the word's own e, for a soft last sound under the voice threshold
        c["e"] = min(c["words"][-1]["e"], limit_e)
        return
    g0 = int(max(c["s"], c["words"][-1]["s"] - 0.3) * 100)
    for f in range(int(c["e"] * 100), g0 + 2, -1):
        if (db[f - 3:f] > off).all():
            g = f
            while g < min(f + int(ring * 100), len(db)) and db[g] > room + 18:
                g += 1
            end = g / 100
            if re.search(r"[.?!]$", c["words"][-1]["w"]):
                end = max(end, f / 100 + breath)
            c["e"] = min(end, limit_e)
            break


def plan_clips(words, silences, keeps, gap_max, pad_in, pad_out, min_len, db=None, breath=0.0, ring=0.03):
    """Turn kept word ranges into source clips, cut at real pauses.

    Whisper stretches the first word after a pause back into the silence (up to ~0.8 s), so
    clip edges snap to the silence map first: start where the silence ends, end where it
    begins. Then `tighten` fits each edge to the voice itself.
    """
    def real_start(w):
        # "hard": true in a reel's words copy starts the clip right at the word, for a word run into the one
        # before it with no silence to snap to (Oct 29: "So, what…" kept the "So")
        if w.get("hard"):
            return w["s"]
        ends = [se for ss, se in silences if w["s"] - 0.4 <= se <= w["e"] - 0.05]
        return max(ends) if ends else w["s"]

    def real_end(w):
        rs = real_start(w)
        starts = [ss for ss, se in silences if rs + 0.05 <= ss <= w["e"] + 0.4]
        return min(starts) if starts else w["e"]

    def open_clip(w):
        if w.get("hard"):
            return {"s": w["s"], "words": [w]}
        return {"s": real_start(w) - (pad_in if real_start(w) != w["s"] else 0.05), "words": [w]}

    def close_clip(c):
        w = c["words"][-1]
        c["e"] = real_end(w) + (pad_out if real_end(w) != w["e"] else 0.08)
        return c

    raw = []
    for a, b in keeps:
        cur = open_clip(words[a])
        for w in words[a + 1:b + 1]:
            if real_start(w) - real_end(cur["words"][-1]) > gap_max:
                raw.append(close_clip(cur))
                cur = open_clip(w)
            else:
                cur["words"].append(w)
        raw.append(close_clip(cur))

    clips = []
    for c in raw:
        first, last = c["words"][0], c["words"][-1]
        # never bleed into a neighbouring word that was cut
        if first["i"] > 0:
            c["s"] = max(c["s"], real_end(words[first["i"] - 1]))
        if last["i"] + 1 < len(words):
            c["e"] = min(c["e"], real_start(words[last["i"] + 1]))
        c["s"] = max(c["s"], 0)
        if db is not None:
            nxt = real_start(words[last["i"] + 1]) - 0.02 if last["i"] + 1 < len(words) else len(db) / 100
            tighten(c, db, pad_in, breath, nxt, ring)
        prev = clips[-1] if clips else None
        # a short clip that runs straight on from the one before joins it; across a pause it stays
        if prev and c["e"] - c["s"] < min_len and c["s"] - prev["e"] < 0.15:
            prev["e"], prev["words"] = c["e"], prev["words"] + c["words"]
        elif c["e"] - c["s"] > 0.05:
            clips.append(c)
    return clips


def plan_captions(placed, max_words, fix, keys=()):
    """One caption per clip (the creator's style), long clips split into even chunks; no punctuation.
    Words whose index is in `keys` are marked to show in the accent colour."""
    out = []
    for c in placed:
        ws = []
        for w in c["words"]:
            t0 = min(max(c["t"] + w["s"] - c["s"], c["t"]), c["t"] + c["dur"])
            t1 = min(c["t"] + w["e"] - c["s"], c["t"] + c["dur"])
            text = re.sub(r"[.,!?;:]+$", "", w["w"])
            if ws and text[:1] in "-'":  # Whisper splits "long-term" into "long" "-term"
                ws[-1]["w"] += text
                ws[-1]["t1"] = max(t1, ws[-1]["t1"])
                ws[-1]["key"] = ws[-1]["key"] or w["i"] in keys
                continue
            ws.append({"w": fix.get(text, text), "t0": t0, "t1": max(t1, t0 + 0.05), "key": w["i"] in keys})
        n = -(-len(ws) // max_words)
        size = -(-len(ws) // n)
        for j in range(0, len(ws), size):
            chunk = ws[j:j + size]
            start = c["t"] if j == 0 else chunk[0]["t0"]
            end = ws[j + size]["t0"] if j + size < len(ws) else c["t"] + c["dur"]
            out.append({"start": start, "end": end, "words": chunk,
                        "text": " ".join(x["w"] for x in chunk)})
    return out


def build_plan(edl):
    tx = load(Path(edl["words"]).expanduser())
    words, sil = tx["words"], tx["silences"]
    fps = edl.get("fps", 30)
    snap = lambda t: round(t * fps) / fps
    clips = plan_clips(words, sil, edl["keep"], edl.get("gap_max", 0.3), edl.get("pad_in", 0.02),
                       edl.get("pad_out", 0.0), edl.get("min_clip", 0.5), loudness(tx["media"]),
                       edl.get("breath", 0.0), edl.get("ring", 0.03))
    # "intro": a finished clip (a podcast quote, say) that opens the reel before the creator's first word.
    # Their clips, and everything placed by at_word, start after it; "at" stays timeline seconds.
    intro = edl.get("intro")
    if intro:
        intro = dict(intro, media=str(Path(intro["media"]).expanduser()))
        intro["dur"] = int(probe(intro["media"])["duration"] / US * fps) / fps  # whole frames
    t, placed = (intro["dur"] if intro else 0.0), []
    zoom = edl.get("zoom", [1.0, 1.15])
    # slow push-in on the hook (first clip) and on any clip holding a `push` word; "push": false turns it off
    push = edl.get("push", [])
    zi = 0  # the punch-in only changes after a sentence ends (the creator, Oct 26: "jumps around too much")
    for i, c in enumerate(clips):
        s, e = snap(c["s"]), snap(c["e"])
        placed.append({"s": s, "dur": e - s, "t": t, "words": c["words"], "scale": zoom[zi % len(zoom)],
                       "push": push is not False and (i == 0 or any(w["i"] in push for w in c["words"]))})
        t += e - s
        if re.search(r"[.?!]$", c["words"][-1]["w"]):
            zi += 1
    keys = set(edl.get("key", []))
    caps = plan_captions(placed, edl.get("caption_words", 6), edl.get("fix", {}), keys) \
        if edl.get("captions", True) else []
    for c in caps:  # CapCut snaps to whole frames on save; matching it keeps diffs clean
        c["start"], c["end"] = snap(c["start"]), snap(c["end"])
    at = lambda x: x["at"] if "at" in x else word_time(placed, x["at_word"])
    # B-roll under 720 px on its short side looks blurry next to their 3K camera: skip it unless
    # it has "force": true; 720 to 1079 px is used but reported as soft
    broll, soft, skipped = [], [], []
    for b in edl.get("broll", []):
        info = probe(b["media"])
        side = min(info["width"], info["height"])
        if side < 720 and not b.get("force"):
            skipped.append(f"{Path(b['media']).name} ({info['width']}x{info['height']})")
            continue
        if side < 1080:
            soft.append(f"{Path(b['media']).name} ({info['width']}x{info['height']})")
        b = dict(b, t=snap(at(b)))
        # B-roll starts and ends on the creator's own cuts (Oct 26: "it jumps around too much" and a clip
        # ending just before their cut "looks glitchy"). It covers the whole talking-head clip that holds
        # its word when that clip is short; otherwise it runs from its word to that clip's end.
        # first clip ending after t (with a frame's slack: a word right on a cut once picked the clip
        # before it and made a 0 s B-roll, Oct 27)
        host = next((c for c in placed if b["t"] < c["t"] + c["dur"] - 0.02), placed[-1])
        if host["dur"] <= b.get("cover_max", 2.5):
            b["t"] = host["t"]
        b["dur"] = round(host["t"] + host["dur"] - b["t"], 3)
        b["src"] = max(0.0, b.get("src", 0) - max(0.0, b.get("dur_wanted", 0)))  # keep the chosen moment
        broll.append(b)
    # HyperFrames graphics with an "html" template get their length and cue times from the words,
    # so they stay in sync however the cuts move ("281e" = the end of word 281). A float (5.0) is timeline
    # seconds, for cues inside an intro clip, whose words aren't the speaker's
    gdir = Path(edl.get("graphics_dir", ".")).expanduser()
    cue = lambda v: (word_end(placed, int(v[:-1])) if isinstance(v, str) else
                     v if isinstance(v, float) else word_time(placed, v))
    graphics = []
    for g in edl.get("graphics", []):
        g = dict(g, t=snap(at(g)))
        if g.get("format") == "mp4" and "at_word" in g:
            # an opaque cutaway starts on the cut, not a frame or two into the clip (Oct 29)
            host = next((c for c in placed if c["t"] <= g["t"] < c["t"] + c["dur"]), None)
            if host and (host["words"][0]["i"] == g["at_word"] or g["t"] - host["t"] < 0.15):
                g["t"] = host["t"]
        if "until_word" in g:
            g["dur"] = snap(word_time(placed, g["until_word"])) - g["t"]
        elif "html" in g and "dur" not in g:
            g["dur"] = t - g["t"]
        if "html" in g:
            g["cues"] = {k: round(cue(v) - g["t"], 3) for k, v in g.get("cues", {}).items()}
            g["cues"].setdefault("out", round(g["dur"] - 0.3, 3))
            if "scenes" in g:
                g["scenes"] = scene_cues(g["scenes"], lambda v: round(cue(v) - g["t"], 3))
            g["media"] = str(gdir / "out" / f"{g['name']}.{g.get('format', 'mov')}")
        graphics.append(g)
    sfx = [dict(x, t=snap(at(x) + x.get("offset", 0))) for x in edl.get("sfx", [])]
    return {"media": tx["media"], "clips": placed, "captions": caps, "broll": broll, "graphics": graphics,
            "sfx": sfx, "music": edl.get("music"), "end": t, "fps": fps, "keys": keys, "intro": intro,
            "soft": soft, "skipped": skipped}


def scene_cues(x, f):
    """Times in a whiteboard's "scenes" (whiteboard.html): "at" and any key ending in "cue" hold a word
    index ("281e" = its end, "start" = the graphic's start) and become seconds into the graphic."""
    if isinstance(x, list):
        return [scene_cues(v, f) for v in x]
    if isinstance(x, dict):
        return {k: (0.0 if v == "start" else f(v)) if k == "at" or k.lower().endswith("cue") else scene_cues(v, f)
                for k, v in x.items()}
    return x


def report_broll(p):
    for name in p["skipped"]:
        print(f"Skipped, too low-res: {name}")
    for name in p["soft"]:
        print(f"Soft B-roll used: {name}")


def word_time(placed, i):
    for c in placed:
        for w in c["words"]:
            if w["i"] == i:
                return c["t"] + max(w["s"] - c["s"], 0)
    sys.exit(f"Word {i} isn't in the kept clips")


def word_end(placed, i):
    for c in placed:
        for w in c["words"]:
            if w["i"] == i:
                return c["t"] + min(w["e"] - c["s"], c["dur"])
    sys.exit(f"Word {i} isn't in the kept clips")


def caption_data(p, edl):
    """Words on the reel's timeline for the HyperFrames caption track, in groups of 1 to 3.

    Groups break after a comma or sentence end, before a capitalized word (a new sentence Whisper
    left unpunctuated; a name right after another stays together), at a pause over 0.15 s, before 15 letters,
    and nothing shows during an opaque full-screen cutaway (its own labels carry the words).
    """
    fix, keys = edl.get("fix", {}), set(edl.get("key", []))
    hide = [(g["t"], g["t"] + g["dur"]) for g in p["graphics"] if g.get("format") == "mp4"]
    words = []
    if p.get("intro") and p["intro"].get("words"):
        # intro words are already on the reel's timeline: [{"w", "s", "e", "src": [s, e], "key"}]
        for w in load(Path(p["intro"]["words"]).expanduser()):
            text = re.sub(r"[.,!?;:]+$", "", w["w"])
            words.append({"text": text, "start": round(w["s"], 3), "end": round(max(w["e"], w["s"] + 0.08), 3),
                          "key": bool(w.get("key")), "stop": bool(re.search(r"[.?!,]$", w["w"])),
                          "cap": bool(re.match(r"[A-Z]", w["w"])) and not re.match(r"I('|$)", w["w"]),
                          "src": tuple(w.get("src", (w["s"], w["e"])))})
    for c in p["clips"]:
        for w in c["words"]:
            t0 = c["t"] + max(w["s"] - c["s"], 0)
            t1 = min(c["t"] + w["e"] - c["s"], c["t"] + c["dur"])
            text = re.sub(r"[.,!?;:]+$", "", w["w"])
            if words and text[:1] in "-'":  # Whisper splits "long-term" into "long" "-term"
                words[-1]["text"] += text
                words[-1]["end"] = round(max(t1, words[-1]["end"]), 3)
                continue
            if any(a - 0.05 <= t0 < b for a, b in hide):
                continue
            # original case kept (Whisper writes sentence case and names); a template may uppercase in CSS
            words.append({"text": fix.get(text, text), "start": round(t0, 3),
                          "end": round(max(t1, t0 + 0.08), 3), "key": w["i"] in keys,
                          "stop": bool(re.search(r"[.?!,]$", w["w"])),
                          # Whisper drops some periods, but a capital still marks a new sentence ("I" aside)
                          "cap": bool(re.match(r"[A-Z]", w["w"])) and not re.match(r"I('|$)", w["w"]),
                          "src": (w["s"], w["e"])})
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        nxt = words[i + 1] if i + 1 < len(words) else None
        chars = sum(len(words[j]["text"]) for j in cur)
        if (not nxt or len(cur) == 3 or w["stop"] or nxt["start"] - w["end"] > 0.15
                or chars + len(nxt["text"]) > 15 or (nxt["cap"] and not w["cap"])
                or nxt["src"][0] - w["src"][1] > 0.6  # a pause was cut out here: new thought
                or any(w["end"] <= a <= nxt["start"] for a, _ in hide)):
            groups.append(cur)
            cur = []
    out = []
    for gi, g in enumerate(groups):
        start = words[g[0]]["start"] if gi else 0.0
        end = min(words[g[-1]]["end"] + 0.3, words[groups[gi + 1][0]]["start"] if gi + 1 < len(groups) else p["end"])
        for a, _ in hide:
            if start < a < end:
                end = a
        out.append({"w": g, "start": round(start, 3), "end": round(end, 3)})
    return words, out


def cmd_graphics(a):
    """Render the reel's HyperFrames graphics, each with its cue times taken from the words."""
    edl = load(a.edl)
    p = build_plan(edl)
    gdir = Path(edl["graphics_dir"]).expanduser()
    (gdir / "out").mkdir(exist_ok=True)
    for g in p["graphics"]:
        if "html" not in g or (a.only and g["name"] not in a.only):
            continue
        src = (gdir / g["html"]).read_text()
        if g.get("kind") == "captions":
            words, groups = caption_data(p, edl)
            src = src.replace("/*WORDS*/[]", "/*WORDS*/" + json.dumps([{k: v for k, v in w.items() if k != "src"} for w in words]))
            src = src.replace("/*GROUPS*/[]", "/*GROUPS*/" + json.dumps(groups))
        if "scenes" in g:
            src = src.replace("/*SCENES*/[]", "/*SCENES*/" + json.dumps(g["scenes"]))
        src = re.sub(r"/\*CUES\*/\{.*?\}/\*END\*/", lambda m: "/*CUES*/" + json.dumps(g["cues"]) + "/*END*/",
                     src, flags=re.S)
        if g.get("css"):
            # per-reel placement without touching the template: the caption height that clears the chin
            # (check.py look) and the lower band moved under it, e.g. ".clip{translate:0 150px}" (Oct 29)
            src = src.replace("</head>", f"<style>{g['css']}</style>\n  </head>", 1)
        # one spare frame: HyperFrames sometimes renders a frame short, which left a frame of the last
        # face clip before the next cut (Oct 29); the build trims every graphic to its own length anyway
        src = re.sub(r'data-duration="[\d.]+"', f'data-duration="{g["dur"] + 1 / p["fps"]:.3f}"', src)
        gen = gdir / f"_gen_{g['name']}.html"  # beside the templates, so assets/ paths still resolve
        gen.write_text(src)
        fmt = g.get("format", "mov")
        cmd = ["hyperframes", "render", "-c", gen.name, "--format", fmt, "-o", f"out/{g['name']}.{fmt}", "--quiet"]
        if g.get("vars"):
            cmd += ["--variables", json.dumps(g["vars"])]
        r = subprocess.run(cmd, cwd=gdir, capture_output=True, text=True)
        print(("ok   " if r.returncode == 0 else "FAIL ") + f"{g['name']:10} {g['dur']:5.2f}s  cues {g['cues']}")
        if r.returncode:
            print(r.stderr[-600:])


def cmd_plan(a):
    p = build_plan(load(a.edl))
    if p["intro"]:
        print(f"  0.00  intro  {Path(p['intro']['media']).name}  {p['intro']['dur']:.2f}s")
    for c in p["clips"]:  # *word* = shows in the accent colour; "push" = slow push-in on that clip
        txt = " ".join(f"*{w['w']}*" if w["i"] in p["keys"] else w["w"] for w in c["words"])
        print(f"{c['t']:6.2f}  src {c['s']:7.2f}+{c['dur']:4.2f}  x{c['scale']:.2f}"
              f"{' push' if c['push'] else '     '}  {txt}")
    for g in p["graphics"]:
        print(f"{g['t']:6.2f}  graphic  {Path(g['media']).name}")
    print(f"\n{len(p['clips'])} clips, {p['end']:.1f}s, {len(p['captions'])} captions, "
          f"{len(p['broll'])} b-roll, {len(p['graphics'])} graphics, {len(p['sfx'])} sfx, "
          f"music: {bool(p['music'])}")
    report_broll(p)


# ---------- build ----------

def us(t):
    return int(round(t * US))


def set_video(u, path, info, src, dur, t, scale=1.0, volume=1.0, y=0.0, x=0.0):
    seg = u["segment"]
    seg["source_timerange"] = {"start": us(src), "duration": us(dur)}
    seg["target_timerange"] = {"start": us(t), "duration": us(dur)}
    seg["clip"]["scale"] = {"x": scale, "y": scale}
    seg["clip"]["transform"] = {"x": x, "y": y}
    seg["volume"] = seg["last_nonzero_volume"] = volume
    seg["common_keyframes"], seg["keyframe_refs"] = [], []
    for k, m in u["materials"]:
        if k == "videos":
            m.update(path=path, material_name=Path(path).name, duration=info["duration"],
                     width=info["width"], height=info["height"], has_audio=info["has_audio"],
                     local_material_id=str(uuid.uuid4()), type="video")
        elif k == "material_animations":
            m["animations"] = []
    return u


def set_audio(u, path, info, src, dur, t, volume):
    seg = u["segment"]
    seg["source_timerange"] = {"start": us(src), "duration": us(dur)}
    seg["target_timerange"] = {"start": us(t), "duration": us(dur)}
    seg["volume"] = seg["last_nonzero_volume"] = volume
    for k, m in u["materials"]:
        if k == "audios":
            m.update(path=path, name=Path(path).name, duration=info["duration"],
                     local_material_id=str(uuid.uuid4()), music_id=str(uuid.uuid4()))
    return u


def set_caption(u, cap):
    seg = u["segment"]
    dur = us(cap["end"] - cap["start"])
    seg["target_timerange"] = {"start": us(cap["start"]), "duration": dur}
    text = cap["text"]
    # CapCut's per-word timing: ms from caption start, with a " " entry between words
    st, en, tx = [], [], []
    for j, w in enumerate(cap["words"]):
        a = int((w["t0"] - cap["start"]) * 1000)
        b = int((w["t1"] - cap["start"]) * 1000)
        if j:
            st.append(en[-1]); en.append(en[-1]); tx.append(" ")
        st.append(a); en.append(b); tx.append(w["w"].rstrip(",.") if j == len(cap["words"]) - 1 else w["w"])
    for k, m in u["materials"]:
        if k == "texts":
            c = json.loads(m["content"])
            c["styles"], c["text"] = key_styles(c["styles"][0], cap["words"]), text
            m["content"] = json.dumps(c, ensure_ascii=False, separators=(",", ":"))
            # m["name"] stays: every caption in a draft shares the template's caption-group id
            if "recognize_text" in m:
                m["recognize_text"] = text
            if isinstance(m.get("words"), dict):
                m["words"] = {"start_time": st, "end_time": en, "text": tx}
        elif k == "text_templates":
            for r in m.get("text_info_resources", []):
                r["attach_info"]["duration"] = dur
        elif k == "material_animations":
            for an in m.get("animations", []):
                if an.get("type") == "caption":
                    an["duration"] = dur
    return u


def key_styles(base, words):
    """Style runs covering the caption text: the template's style, with key words in the accent colour."""
    runs, pos = [], 0  # [start, end, red] in UTF-16 units, which is what CapCut counts
    for j, w in enumerate(words):
        a = pos + (1 if j else 0)
        b = a + len(w["w"].encode("utf-16-le")) // 2
        runs += [[pos, a, False], [a, b, True]] if w.get("key") else [[pos, b, False]]
        pos = b
    merged = []
    for r in runs:
        if r[1] <= r[0]:
            continue
        if merged and merged[-1][2] == r[2]:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    out = []
    for a, b, red in merged:
        s = copy.deepcopy(base)
        s["range"] = [a, b]
        if red:
            s["fill"]["content"]["solid"]["color"] = ACCENT
        out.append(s)
    return out


def dissolve(u, dur, fin, fout, t=0.25):
    """Opacity keyframes for a B-roll fade. Unused: CapCut 9.5 ignored them (checked Oct 26), so B-roll
    cuts on the creator's cuts instead."""
    kf = lambda at, v: {"id": uid(), "curveType": "Line", "graphID": "", "time_offset": us(at),
                        "left_control": {"x": 0.0, "y": 0.0}, "right_control": {"x": 0.0, "y": 0.0},
                        "values": [v]}
    pts = []
    if fin:
        pts += [kf(0, 0.0), kf(min(t, dur / 2), 1.0)]
    if fout:
        pts += [kf(max(dur - t, dur / 2), 1.0), kf(dur, 0.0)]
    if pts:
        u["segment"]["common_keyframes"].append({"id": uid(), "material_id": "", "property_type": "KFTypeAlpha",
                                                 "keyframe_list": pts})
    return u


def push_in(u, scale, dur):
    """Slow push-in across the whole clip, about 2.5% a second and at most 8%, as scale keyframes."""
    end = round(scale * (1 + min(0.08, 0.025 * dur)), 4)
    kf = lambda t, v: {"id": uid(), "curveType": "Line", "graphID": "", "time_offset": t,
                       "left_control": {"x": 0.0, "y": 0.0}, "right_control": {"x": 0.0, "y": 0.0},
                       "values": [v]}
    u["segment"]["common_keyframes"] = [
        {"id": uid(), "material_id": "", "property_type": p, "keyframe_list": [kf(0, scale), kf(us(dur), end)]}
        for p in ("KFTypeScaleX", "KFTypeScaleY")]
    return u


def stage(path, project):
    """CapCut is sandboxed: it opens files under ~/Movies and files the creator imported himself, nothing
    else (Oct 26: the new SFX and music on the Desktop came up as "couldn't find", 0/13 linked).
    Audio and B-roll the builder brings in are copied next to the build, where CapCut can always read
    them. The A-roll stays where the creator imported it."""
    src = Path(path).expanduser()
    if str(src).startswith(str(Path.home() / "Movies")):
        return str(src)
    # ASCII-safe name: CapCut lost two clips whose names carry emoji with variation selectors
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", src.stem).strip("_ ")[:60] + src.suffix.lower()
    dst = WORK / project / "media" / safe
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or dst.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dst)
    return str(dst)


def fade(u, fin, fout):
    """CapCut audio fade on a clip (same material the creator's 0122 draft uses on video clips)."""
    f = {"id": uid(), "type": "audio_fade", "fade_type": 0,
         "fade_in_duration": us(fin), "fade_out_duration": us(fout)}
    u["materials"].append(["audio_fades", f])
    u["segment"]["extra_material_refs"].append(f["id"])
    return u


def add(d, u):
    for k, m in u["materials"]:
        d["materials"].setdefault(k, []).append(m)
    return u["segment"]


def new_track(hdr, segs, idx):
    t = copy.deepcopy(hdr)
    t["id"], t["segments"] = uid(), segs
    for s in segs:
        s["track_render_index"] = idx
    return t


def validate(d):
    """Problems CapCut would choke on: dangling ids, overlaps, clips past the end of their media."""
    ids, errs = index(d), []
    for ti, t in enumerate(d["tracks"]):
        end = 0
        for s in sorted(t["segments"], key=lambda s: s["target_timerange"]["start"]):
            tg = s["target_timerange"]
            for r in [s["material_id"]] + s["extra_material_refs"]:
                if r not in ids:
                    errs.append(f"T{ti} {tg['start']}: missing material {r}")
            if tg["start"] < end - 1000:
                errs.append(f"T{ti} {tg['start']}: overlaps the clip before")
            end = tg["start"] + tg["duration"]
            k, m = ids.get(s["material_id"], ("?", {}))
            sr = s.get("source_timerange")
            if k in ("videos", "audios") and sr and sr["start"] + sr["duration"] > m["duration"] + 1000:
                errs.append(f"T{ti} {tg['start']}: runs past the end of {Path(m['path']).name}")
    if d["duration"] < max((s["target_timerange"]["start"] + s["target_timerange"]["duration"]
                            for t in d["tracks"] for s in t["segments"]), default=0) - 1000:
        errs.append("project duration shorter than its clips")
    return errs


def cmd_build(a):
    edl = load(a.edl)
    if not STYLE.exists():
        sys.exit(f"{STYLE} is missing. Save your templates first: capcut.py style \"<one of your finished reels>\"")
    st = load(STYLE)
    set_accent(edl.get("accent", "#ee2824"))
    pdir = project_dir(edl["project"])
    if capcut_running() and not a.force:
        sys.exit("CapCut is open. Quit it first (it overwrites the draft on close), then run build again.")
    paths = draft_paths(pdir)
    d = load(paths[0])
    if any(t["segments"] for t in d["tracks"]) and not a.replace:
        sys.exit(f"{edl['project']} already has a timeline. Use --replace to rebuild it (a backup is kept).")

    p = build_plan(edl)
    main = probe(p["media"])

    # backup first
    bdir = WORK / pdir.name / f"backup-{time.strftime('%Y%m%d-%H%M%S')}"
    bdir.mkdir(parents=True)
    for i, f in enumerate(paths + [pdir / "draft_meta_info.json"]):
        shutil.copy2(f, bdir / f"{i}-{f.name}")

    for k, v in d["materials"].items():
        if isinstance(v, list):
            v.clear()
    tracks = []

    # a 20 ms fade in and 60 ms fade out on every clip so no cut pops
    segs = []
    it = p["intro"]
    if it:
        info = probe(it["media"])
        u = set_video(clone(st["video"]), stage(it["media"], pdir.name), info, 0, it["dur"], 0,
                      it.get("scale", 1.0), it.get("volume", edl.get("volume", 1.0)))
        segs.append(add(d, fade(u, 0.02, 0.06)))
    # the color grade and music start with the creator unless the intro says "grade": true / "music": true
    g0 = it["dur"] if it and not it.get("grade") else 0.0
    m0 = it["dur"] if it and not it.get("music") else 0.0
    for c in p["clips"]:
        u = set_video(clone(st["video"]), p["media"], main, c["s"], c["dur"], c["t"],
                      c["scale"], edl.get("volume", 1.0))
        if c["push"]:
            push_in(u, c["scale"], c["dur"])
        segs.append(add(d, fade(u, 0.02, min(0.06, c["dur"] / 4))))
    tracks.append(new_track(st["video"]["track"], segs, 0))

    if p["broll"]:
        segs = []
        for b in p["broll"]:
            info = probe(b["media"])
            b = dict(b, media=stage(b["media"], pdir.name))  # into ~/Movies, where CapCut can read it
            src = b.get("src", 0)
            dur = min(b["dur"], info["duration"] / US - src - 0.05)  # trim to fit the source
            dur = int(dur * p["fps"]) / p["fps"]
            segs.append(add(d, set_video(clone(st["broll"]), b["media"], info, src, dur, b["t"],
                                         b.get("scale", 1.0), b.get("volume", 0.0))))
        tracks.append(new_track(st["broll"]["track"], segs, len(tracks)))

    # the creator's color grade (the LUT layer saved by `style`) over the camera footage and
    # B-roll, under graphics and captions so the accent colour stays true. "grade": false turns it off; a
    # number sets the LUT strength.
    grade = edl.get("grade", True)
    if grade is not False and "grade" in st:
        u = clone(st["grade"])
        u["segment"]["target_timerange"] = {"start": us(g0), "duration": us(p["end"] - g0)}
        for k, m in u["materials"]:
            if k == "effects" and m.get("type") == "lut" and grade is not True:
                m["value"] = float(grade)
        tracks.append(new_track(st["grade"]["track"], [add(d, u)], len(tracks)))

    # HyperFrames renders (transparent ProRes MOV) above the B-roll, one track per `lane`
    # (a long one like a progress tracker sits on a low lane, short cards stack higher)
    for lane in sorted({g.get("lane", 0) for g in p["graphics"]}):
        segs = []
        for g in (g for g in p["graphics"] if g.get("lane", 0) == lane):
            info = probe(g["media"])
            # + 1e-6: 16.9 * 30 is 506.999..., and int() alone dropped the last frame (Oct 28)
            dur = int(min(g.get("dur", 1e9), info["duration"] / US) * p["fps"] + 1e-6) / p["fps"]
            # "scale", "x", "y" keep a size or position the creator set in CapCut (x/y in CapCut's own units)
            segs.append(add(d, set_video(clone(st["broll"]), g["media"], info, 0, dur, g["t"],
                                         g.get("scale", 1.0), 0.0, y=g.get("y", 0.0), x=g.get("x", 0.0))))
        tracks.append(new_track(st["broll"]["track"], segs, len(tracks)))

    if p["captions"]:
        segs = [add(d, set_caption(clone(st["caption"]), c)) for c in p["captions"]]
        tracks.append(new_track(st["caption"]["track"], segs, len(tracks)))

    if p["music"]:
        m = dict(p["music"])
        info = probe(m["path"])
        m["path"] = stage(m["path"], pdir.name)
        src = m.get("src", 0)
        dur = min(p["end"] - m0, info["duration"] / US - src)
        u = set_audio(clone(st["audio"]), m["path"], info, src, dur, m0, m.get("volume", 0.15))
        seg = add(d, fade(u, m.get("fade_in", 0.3), m.get("fade_out", 1.2)))
        tracks.append(new_track(st["audio"]["track"], [seg], len(tracks)))

    # SFX go on the first audio track that is free at that moment, so hits close together never overlap
    lanes = []
    for x in sorted(p["sfx"], key=lambda x: x["t"]):
        info = probe(x["path"])
        x = dict(x, path=stage(x["path"], pdir.name))
        length = min(x.get("dur", 1e9), info["duration"] / US)  # "dur" trims a long effect (typing)
        u = set_audio(clone(st["audio"]), x["path"], info, 0, length, x["t"], x.get("volume", 1.0))
        seg = add(d, fade(u, 0, min(0.08, length / 4)) if "dur" in x else u)
        free = next((ln for ln in lanes if ln["end"] <= x["t"]), None)
        if free is None:
            free = {"end": 0, "segs": []}
            lanes.append(free)
        free["segs"].append(seg)
        free["end"] = x["t"] + length
    for ln in lanes:
        tracks.append(new_track(st["audio"]["track"], ln["segs"], len(tracks)))

    d["tracks"] = tracks
    d["duration"] = us(p["end"])
    portrait = main["height"] > main["width"]
    d["canvas_config"].update(ratio="original", width=1080 if portrait else 1920,
                              height=1920 if portrait else 1080)
    errs = validate(d)
    if errs:
        sys.exit("Not written, the draft failed its check:\n  " + "\n  ".join(errs))
    for f in paths:
        save(f, d)
    meta = load(pdir / "draft_meta_info.json")
    meta["tm_duration"] = d["duration"]
    meta["tm_draft_modified"] = int(time.time() * US)
    save(pdir / "draft_meta_info.json", meta)
    save(WORK / pdir.name / "last-build.json", d)
    print(f"Built {edl['project']}: {len(p['clips'])} clips, {p['end']:.1f}s, {len(p['captions'])} captions, "
          f"{len(p['broll'])} b-roll, {len(p['graphics'])} graphics, {len(p['sfx'])} sfx, "
          f"music: {bool(p['music'])}, grade: {any(t['type'] == 'adjust' for t in tracks)}, "
          f"push-ins: {sum(c['push'] for c in p['clips'])}, red words: {len(p['keys'])}\nBackup: {bdir}")
    report_broll(p)


# ---------- read-only views ----------

def describe(d):
    ids = index(d)
    rows = []
    for ti, t in enumerate(d["tracks"]):
        for s in t["segments"]:
            k, m = ids.get(s["material_id"], ("?", {}))
            tg, sr = s["target_timerange"], s.get("source_timerange") or {}
            if k == "texts":
                what = json.loads(m["content"]).get("text", "")
            elif k == "text_templates":
                inner = [ids[r["text_material_id"]][1] for r in m["text_info_resources"] if r["text_material_id"] in ids]
                what = json.loads(inner[0]["content"]).get("text", "") if inner else m.get("name", "")
            else:
                what = Path(m.get("path", "")).name or m.get("name", k)
            extra = ""
            if t["type"] == "video":
                extra = f" src {sr.get('start', 0) / US:.2f} x{s['clip']['scale']['x']:.2f} vol {s['volume']:.2f}"
            elif t["type"] == "audio":
                extra = f" vol {s['volume']:.2f}"
            rows.append(f"T{ti} {t['type']:5} {tg['start'] / US:7.2f} +{tg['duration'] / US:5.2f}{extra}  {what}")
    return rows


def cmd_inspect(a):
    pdir = project_dir(a.project)
    d = load(pdir / "draft_info.json")
    c = d["canvas_config"]
    print(f"{a.project}: {c['width']}x{c['height']} {d['duration'] / US:.1f}s, {len(d['tracks'])} tracks")
    print("Media bin:")
    for g in load(pdir / "draft_meta_info.json").get("draft_materials", []):
        for m in g.get("value", []):
            if m.get("file_Path"):
                ok = "" if Path(m["file_Path"]).exists() else "  (OFFLINE)"
                print(f"  {m['duration'] / US:7.1f}s {m['width']}x{m['height']}  {m['file_Path']}{ok}")
    print("\n".join(describe(d)))


def cmd_thumbs(a):
    """One frame from the middle of each clip in a folder, so B-roll can be picked by looking."""
    import imageio_ffmpeg
    out = WORK / "thumbs" / Path(a.folder).name
    out.mkdir(parents=True, exist_ok=True)
    for f in sorted(Path(a.folder).expanduser().iterdir()):
        if f.suffix.lower() not in (".mp4", ".mov", ".m4v"):
            continue
        if f.stat().st_flags & 0x40000000:  # iCloud-only: reading it would hang until it downloads
            print(f"  (in iCloud only, skipped)  {f.name}")
            continue
        info = probe(str(f))
        jpg = out / f"{f.stem}.jpg"
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-ss",
                        f"{info['duration'] / US / 2:.2f}", "-i", str(f), "-frames:v", "1",
                        "-vf", "scale=-2:360", str(jpg)])
        side = min(info["width"], info["height"])
        tag = "  TOO LOW, build skips it" if side < 720 else "  soft" if side < 1080 else ""
        print(f"{info['duration'] / US:6.1f}s {info['width']}x{info['height']}{tag}  {jpg}  <- {f}")


def cmd_diff(a):
    pdir = project_dir(a.project)
    before = WORK / pdir.name / "last-build.json"
    if not before.exists():
        sys.exit("No build snapshot for this project.")
    old, new = describe(load(before)), describe(load(pdir / "draft_info.json"))
    out = list(difflib.unified_diff(old, new, "claude-build", "james-edit", lineterm="", n=0))
    print("\n".join(out) if out else "No changes since the build.")


def cmd_new(a):
    """A new empty project, cloned from an empty one the creator made, with fresh ids, added to CapCut's list."""
    if capcut_running():
        sys.exit("CapCut is open. Quit it first (it rewrites its project list on close).")
    if (ROOT / a.name).exists():
        sys.exit(f"{a.name!r} already exists.")
    src = project_dir(a.src)
    if any(t["segments"] for t in load(src / "draft_info.json")["tracks"]):
        sys.exit(f"{a.src} has a timeline; clone an empty project.")
    meta = load(src / "draft_meta_info.json")
    pj = load(src / "Timelines/project.json")
    dst = ROOT / a.name
    shutil.copytree(src, dst)
    # the draft, project and timeline ids appear across several files; swap each for a new one
    swap = {meta["draft_id"]: uid(), pj["id"]: uid(), pj["main_timeline_id"]: uid()}
    (dst / "Timelines" / pj["main_timeline_id"]).rename(dst / "Timelines" / swap[pj["main_timeline_id"]])
    now = int(time.time() * US)
    for f in dst.rglob("*"):
        if f.is_file() and f.suffix in (".json", ".bak", ".tmp") and f.stat().st_size:
            s = f.read_text()
            for old, new in swap.items():
                s = s.replace(old, new)
            f.write_text(s.replace(str(src), str(dst)))
    m = load(dst / "draft_meta_info.json")
    m.update(draft_name=a.name, draft_fold_path=str(dst), tm_draft_create=now, tm_draft_modified=now)
    save(dst / "draft_meta_info.json", m)
    rp = ROOT / "root_meta_info.json"
    root = load(rp)
    shutil.copy2(rp, WORK / f"root_meta_info.backup-{time.strftime('%Y%m%d-%H%M%S')}.json")
    entry = next(e for e in root["all_draft_store"] if Path(e["draft_fold_path"]) == src)
    entry = dict(entry, draft_name=a.name, draft_fold_path=str(dst), draft_id=swap[meta["draft_id"]],
                 draft_json_file=str(dst / "draft_info.json"), draft_cover=str(dst / "draft_cover.jpg"),
                 tm_draft_create=now, tm_draft_modified=now, tm_duration=0)
    root["all_draft_store"].insert(0, entry)
    root["draft_ids"] = root.get("draft_ids", 0) + 1
    save(rp, root)
    print(f"Created {a.name} from {a.src}")


def cmd_list(a):
    rows = sorted(load(ROOT / "root_meta_info.json")["all_draft_store"], key=lambda x: -x["tm_draft_modified"])
    for r in rows[:a.n]:
        print(f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(r['tm_draft_modified'] / US))}  "
              f"{r['tm_duration'] / US:7.1f}s  {r['draft_name']}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").add_argument("-n", type=int, default=15)
    sub.add_parser("inspect").add_argument("project")
    sub.add_parser("style").add_argument("projects", nargs="+")
    sub.add_parser("plan").add_argument("edl")
    b = sub.add_parser("build")
    b.add_argument("edl")
    b.add_argument("--replace", action="store_true")
    b.add_argument("--force", action="store_true", help="build even if CapCut is open")
    sub.add_parser("diff").add_argument("project")
    sub.add_parser("thumbs").add_argument("folder")
    n = sub.add_parser("new")
    n.add_argument("name")
    n.add_argument("--from", dest="src", required=True, help="an empty project of yours to clone")
    gr = sub.add_parser("graphics")
    gr.add_argument("edl")
    gr.add_argument("--only", nargs="*", help="render just these graphic names")
    a = ap.parse_args()
    {"list": cmd_list, "inspect": cmd_inspect, "style": cmd_style, "plan": cmd_plan,
     "build": cmd_build, "diff": cmd_diff, "thumbs": cmd_thumbs, "graphics": cmd_graphics, "new": cmd_new}[a.cmd](a)


if __name__ == "__main__":
    main()
