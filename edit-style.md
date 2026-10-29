# Reel Edit Style

Last updated: (the date you last changed this)

How you edit reels. `/capcut-edit` builds every edit from these rules, and every change you make to a build inside CapCut becomes a rule here (`capcut.py diff "<project>"` shows what you changed). The starting values below come from one creator's reels. Change any you disagree with and add what's missing. Keep each rule something the editor can act on, with the reason in brackets.

## Rules for every edit

- **Hook:** first caption on screen at 0.0 s. It names the topic, a name people know, or a pain the viewer knows within 2 seconds. No "alright today", no "so". The hook plays over B-roll from 0.0 s to the end of the hook clip, with your voice and the hook graphic on top. Pick a shot with a plain background at caption height.
- **Length:** teaching reels 30 to 45 seconds. The main point lands before the 15-second mark; the rest is proof. When trimming to length would cut a line that carries its own graphic, the editor asks first.
- **Cuts:** no dead air at cuts, but smooth. Each clip starts on your first sound and ends on your last word, breath noise after it cut, no hold between sentences, a soft audio fade on every cut. No quiet stretch over about 0.13 s at any cut. Short pauses inside a line that you use for emphasis stay. A clip never clips the end of its last word (fix the word's end time, don't add the next line).
- **Topic:** (what the account is about, and what counts as off-topic)
- **CTA:** every teaching reel ends with one ask, in the last line and the caption. (Yours: )
- **B-roll:** only footage you shot or have cleared in writing, from (folder). Check the frame before placing a clip: it has to show the action the line names. B-roll cuts on your cuts: it covers the whole talking-head clip that holds its word when that clip is under 2.5 s, otherwise it runs from the word to that clip's end. Never a B-roll edge in the middle of a clip. Anything under 720 px on its short side is skipped. A borrowed podcast clip opens the reel, before your hook, with a "via <show>" credit on screen.
- **Color:** (your grade: LUT name and strength, saved from one of your reels by `capcut.py style`; `"grade": 0.6` in the EDL sets the strength)
- **Captions:** (font), white, sentence case, 1 to 3 words at a time, (position: on the chest, same height the whole reel). Each group fades and rises 12 px over 0.2 s. The word that carries a line shows in the accent colour, static: the topic, the pain, a number, the CTA keyword. No bars, boxes, glows or blur behind text. No captions over a full-screen graphic.
- **Push-ins:** a slow push-in on the hook and on two or three lines that carry the point (the payoff, the CTA). Every other clip keeps the hard 100% / 115% cut, which only changes after a sentence ends so a mid-sentence cut doesn't also jump in size.
- **Motion graphics:** keep every graphic idea, calm the execution. Two fonts: (display font) for anything big, Inter 600 with 0.08 em tracking for small labels. White on footage, the accent colour for one panel, rule, fill or key word, near-black #231f20 panels at 40 to 60%. One soft shadow. `power2.out` in (0.35 to 0.5 s), `power2.in` out (0.25 s), fades and 10 to 16 px slides. No blur pops, scale slams, shakes, flashing or per-letter effects. Nothing new more than about once a second. Top band 180 to 400 px for running elements, 1130 to 1330 px for cards and explainers, captions at about 960 px (check against where your head sits in frame).
- **Whiteboard cutaways:** only while something new lands on them, never more than about 1.5 s without a change (`check.py still` lists the holds). Lines that name an action get B-roll, lines that explain get the whiteboard, turns in the argument and the CTA stay on your face.
- **Music:** (track and volume) about 15 dB under your voice, fading in and out. Leave it out of the export when you'll add trending audio inside Instagram.
- **SFX:** one soft sound per graphic at most (a sweep or click at 0.3 to 0.5), a whoosh on a cutaway. Nothing on captions or B-roll.

## Your numbers

Paste your last 10 reels from Instagram insights. Watched = average watch time ÷ length. Shares, saves and follows are per 1,000 views. The medians are the baseline each new reel has to beat.

| Posted | Reel | Length | Views | Avg watch | Watched | Shares | Saves | Follows |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

**Baseline to beat (medians of those 10):**

## What your numbers say

One line per pattern you can see. The kind of thing that shows up: people give a reel about 15 seconds whatever its length; topic and first line beat edit style; the reels with a CTA bring the followers; off-topic loses; a strong uncut clip can beat a heavy edit.

## Changes you made to builds

One entry per tweak: date, what you changed in CapCut, the rule it became above.
