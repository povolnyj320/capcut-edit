# capcut-edit

Claude edits your talking-head reels inside CapCut desktop without clicking anything. It transcribes the raw clip, picks the keeps, cuts retakes and dead air, adds push-ins, your colour grade, word-by-word captions with key words in your accent colour, B-roll, motion graphics, SFX and music, then writes the whole timeline straight into CapCut's project files. You open the project, tweak, export. Claude reads your tweaks and turns them into rules, so the next reel starts closer to what you would have done.

Started from Matt Loui's "Automate Your CapCut Editing With Claude" (Oct 2026) and built out over a few weeks of real reels.

## The strategy

Five ideas carry the whole thing:

1. **Claude never clicks.** CapCut keeps each project as JSON (`draft_info.json`). The builder writes that file. It's fast, repeatable, and every edit is a diff you can read.
2. **Words are the timeline.** Whisper gives every word a start and end time. You edit by naming the word ranges to keep (`"keep": [[0, 12], [17, 32]]`). B-roll, graphics and SFX are pinned to a word, not a second, so when a cut moves everything moves with it.
3. **Cuts snap to the voice, not the transcript.** Whisper's times are a guide. The builder finds the real silence around each cut and fits every clip to the first sound and the last word, with a 20 ms fade in and 60 ms fade out so nothing pops.
4. **A rules file is the editor's brain.** `edit-style.md` holds how you cut, what your numbers say and every correction you've made. Claude reads it before every edit. After you tweak a build in CapCut, `capcut.py diff` shows what changed and Claude writes the rule.
5. **Check with ears, not eyes.** `check.py ears` re-transcribes every clip as cut and flags any that don't say what the plan says. The plan reads clean far more often than the audio does.

## What you need

- An Apple Silicon Mac. Whisper runs on the GPU through MLX. 8 GB of RAM works if CapCut is closed while transcribing.
- CapCut desktop 9.x from capcut.com (the Mac App Store build keeps projects somewhere else).
- Python 3.11 or newer. Node 20 or newer for the HyperFrames motion graphics (skip it if you only want cuts and captions).
- Claude Code.

## Setup, once

```bash
git clone https://github.com/povolnyj320/capcut-edit.git
cd capcut-edit
./setup.sh
```

Then:

1. In CapCut, make one **empty project** (call it `Empty`) and quit CapCut with Cmd+Q. New reels are cloned from it.
2. Pick one **finished reel of yours** that has CapCut auto-captions (any template), a B-roll track and music. With CapCut closed, save its templates:
   ```bash
   .venv/bin/python -I capcut.py style "That reel's name"
   ```
   That writes `style.json`: the clip, B-roll, caption, audio and colour-grade templates every build clones, so builds look like your own edits. It stays out of git because it holds paths into your CapCut cache. If a piece is missing the command says so; pass a second project name and the first one listed wins for each piece.
3. Open `edit-style.md` and fill in the blanks: topic, CTA, caption font, B-roll folder, grade, music.
4. Fonts. The graphics kit expects a display font in `hyperframes-kit/assets/fonts/`. Fonts are licensed, so none ship here. Copy the one you use in CapCut out of its cache (`~/Library/Containers/com.lemon.lvoverseas/Data/Movies/CapCut/User Data/Cache/effect/`, search by name) or use any font you own, and point the `@font-face` lines in the templates at it. Without it the templates fall back to a system sans.
5. Keep raw clips, B-roll, SFX and music under `~/Movies`. CapCut is sandboxed: it reads `~/Movies` and files you imported through it, nothing else. The build copies audio and B-roll from anywhere into the work folder, but the A-roll has to live under `~/Movies` before you plan.

Work files (transcripts, loudness caches, backups, staged media, rendered graphics) go in `~/Movies/capcut-edit-work/`. Set `CAPCUT_EDIT_WORK` to put them somewhere else.

## Editing a reel

Open Claude Code in this folder and run `/capcut-edit`. Tell it which clip and what the reel is about. The skill runs everything below; here it is so you can run any step yourself.

```bash
PY=.venv/bin/python; CC="$PY -I capcut.py"
$CC new "Reel 1101" --from Empty                      # a project in CapCut's list (CapCut closed)
$PY -I transcribe.py ~/Movies/clips/take.MP4          # words with times: <work>/take.words.json and take.txt
# pick keeps from the .txt and write edl.json (format below)
$CC plan edl.json                                     # the clip list; read it like a script
$PY -I check.py ears edl.json                         # re-transcribe every clip as cut, flag mismatches
$CC graphics edl.json                                 # render the HyperFrames graphics with cue times from the words
$PY -I check.py frames edl.json look.jpg 1.0 4.5 9.0  # real frames with every graphic and caption live
$PY -I check.py look edl.json                         # captions against your chin every 0.5 s; a clip in another outfit
$PY -I check.py still edl.json                        # any graphic sitting still over 1.5 s
$CC build edl.json                                    # write the timeline (CapCut closed; --replace to rebuild)
$PY -I check.py gaps edl.json                         # quiet stretches over 0.15 s; one at a cut needs a look
# open CapCut, tweak, export, quit
$CC diff "Reel 1101"                                  # what you changed, to turn into rules in edit-style.md
```

Every build keeps a backup of the project files it replaces, in the work folder.

## The EDL

`edl-example.json` is a working example. Paths may start with `~`.

| Field | What it does |
|---|---|
| `project` | The CapCut project name (made by `new`). |
| `words` | The `.words.json` from `transcribe.py`. Make a copy per reel and fix word times or spellings there. |
| `keep` | Word index ranges to keep, inclusive, in play order. Lines can be reordered. |
| `zoom` | Sizes the talking-head clips alternate between at sentence ends. Default `[1.0, 1.15]`. |
| `volume` | Gain on the voice. |
| `accent` | Hex colour for key words in captions. Default `#ee2824`. The graphics kit has its own in `assets/hp.css` and `assets/wb.js`. |
| `fix` | Caption spellings Whisper gets wrong (names, mostly). |
| `key` | Word indices that show in the accent colour. |
| `push` | Word indices whose clip gets a slow push-in (about 2.5% a second, at most 8%). The hook always gets one; `false` turns them off. |
| `captions` | `true` for CapCut captions from your template (default), `false` when a HyperFrames caption track replaces them. `caption_words` (6) is the most words per caption. |
| `grade` | `true` (default), `false`, or a number for the LUT strength. |
| `broll` | `{"media", "at_word" or "at", "src", "force", "cover_max", "scale"}`. Each clip stretches to end on your next cut and starts on the previous cut when the talking clip is under `cover_max` (2.5 s), so no B-roll edge sits inside a clip. Under 720 px on the short side is skipped unless `force`. |
| `intro` | `{"media", "words", "grade", "music"}`: a finished clip that plays before your first word (a podcast quote). Everything placed by `at_word` starts after it. |
| `graphics_dir` | Your copy of `hyperframes-kit/` for this reel. |
| `graphics` | `{"html", "name", "at_word", "until_word", "cues", "lane", "vars", "format", "scenes", "scale", "x", "y"}`. See below. |
| `sfx` | `{"path", "at_word" or "at", "volume", "offset", "dur"}`. Spread over as many audio tracks as they need. |
| `music` | `{"path", "volume", "src", "fade_in", "fade_out"}`. |
| `gap_max`, `pad_in`, `breath`, `ring`, `min_clip` | Tuning, rarely needed: a pause longer than `gap_max` (0.3 s) becomes a cut; `pad_in` (0.02 s) is room before the first sound; `breath` (0) is hold after a sentence; `ring` (0.03 s) is how long a last word may ring out; `min_clip` (0.5 s). |

## The graphics kit

`hyperframes-kit/` is a HyperFrames project: HTML templates rendered to transparent ProRes MOV (overlays) or MP4 (full-screen cutaways) and placed on their own CapCut tracks above the grade, so their colours stay true. Each template starts with `const C = /*CUES*/{...}/*END*/`; the EDL fills the cues with word indices (`"reveal": 22`, `"281e"` for the end of word 281) and `capcut.py graphics` turns them into seconds from the final timeline. Re-run it after any change to the keeps.

What's in it: a hook title, a progress tracker, cards, meters, a battery, comparison bars, a zone scale, checks, chips, a myth strike-through, a heartbeat trace, a name tag, two caption tracks (`captions-min.html`, 1 to 3 words at a time; `captions-word.html`, one word at a time), a comment-box CTA, and `whiteboard.html`, a full-screen cutaway that plays a `scenes` list (icons, bars, zones, big numbers, a week, a heartbeat, lists, checks) from `assets/wb.js`. `edl-five-pillars.json` and `edl-recovery-merged.json` are two full reels that use them.

The templates are one creator's brand. Change `--red` in `assets/hp.css` and `RED` in `assets/wb.js` to your accent, swap the font, and edit the CTA templates (`cta.html`, `cta-comment.html`) to type your keyword.

Rules the kit follows and new templates should too: transparent page for overlays; fonts named in each file's own style block (HyperFrames ignores fonts named only in a linked stylesheet); starting states set with `gsap.set` before the timeline; no `<style>` text inside CSS comments; `hyperframes lint <file>` before a first render.

## Things learned the hard way

- **Close CapCut before any write.** It rewrites the draft and its project list when it quits, over whatever you wrote.
- **Whisper folds retakes.** A false start and its full retake come back as one line with a long gap, so the plan plays the line twice. `ears` catches it. Fix the word times in the reel's copy of the words file, not the keeps.
- **Whisper ends words early.** If a clip sounds cut off, the last word's `e` is short. Extend it in the words copy; don't add the next line.
- **"So," leaks into the hook.** Whisper runs it into the next word with no silence to snap to. Set `"hard": true` on the word you want the clip to start on.
- **iCloud-only files hang.** Anything on a synced Desktop or Documents can be "dataless"; `ls -lO` shows it. `probe` stops with a message. Download it first.
- **CapCut can't see your Desktop.** Files outside `~/Movies` that you didn't import through CapCut come up in a "Link media" box. The build stages audio and B-roll into the work folder; the A-roll has to start under `~/Movies`.
- **Emoji in file names break CapCut.** Staged copies get ASCII-safe names.
- **Opacity keyframes are ignored** by CapCut 9.5 when written into the draft, so B-roll cuts on your cuts instead of dissolving.
- **Caption names must match.** Every caption in a draft shares one `name` (the caption-group id). Change it per caption and CapCut shows "THE QUICK BROWN FOX".
- **After a CapCut update**, if builds stop opening, run `capcut.py style` again: the cached templates and fonts move.
- **Frame-stepping in CapCut drops key presses** on a low-memory Mac. Trust the plan's numbers for edge timing and use CapCut to confirm media loads and graphics render.
- **Graphics can render a frame short.** The builder adds one spare frame and trims to length.

## Not built

Transitions, and voiceover-over-B-roll reels. Add them when you need them.

## Credits

Matt Loui for the idea. [HyperFrames](https://github.com/heygen-com/hyperframes) for HTML-to-video. [mlx-whisper](https://github.com/ml-explore/mlx-examples) for transcription on Apple Silicon. Mixkit's free music and SFX work well as a starting library; their license covers social video with no credit needed.

MIT license.
