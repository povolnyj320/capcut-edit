// HP whiteboard kit (merged the creator + Tony style, Oct 28): the moto line-icon library and the reusable
// scenes that whiteboard.html plays from the EDL's "scenes" list. Off-white page, ZY Starry titles,
// Helvetica Neue labels, 6 px line icons, solid bars; one HP red word per line. Pieces fade and rise
// 12 px on their word; earlier pieces dim to 30% when the next point lands. Opaque, full screen.
window.WB = (() => {
  const INK = "#231f20", RED = "#ee2824", GRAY = "#9a9a9a", LINE = "#b5b5b5", TRACK = "#e3e3e3";
  let root, tl;
  const init = (rootEl, timeline) => ((root = rootEl), (tl = timeline));
  // "*word*" turns HP red, "\n" breaks the line
  const rich = (s) => String(s).replace(/\*(.+?)\*/g, '<span class="r">$1</span>').replace(/\n/g, "<br>");

  // ---------- icons: 120 x 120 line drawings, stroke colour c ----------
  const checker = (c) => {
    let s = "";
    for (let r = 0; r < 3; r++) for (let k = 0; k < 4; k++) if ((r + k) % 2 === 0) s += `<rect x="${26 + k * 19}" y="${16 + r * 17}" width="19" height="17" fill="${c}" stroke="none"/>`;
    return s;
  };
  const ICONS = {
    heart: () => `<path d="M60 104 C26 80 8 62 8 40 C8 22 21 10 37 10 C47 10 55 16 60 24 C65 16 73 10 83 10 C99 10 112 22 112 40 C112 62 94 80 60 104 Z"/>`,
    clock: () => `<circle cx="60" cy="60" r="50"/><path d="M60 28 V60 L82 74"/>`,
    stopwatch: () => `<circle cx="60" cy="68" r="42"/><path d="M50 12 H70 M60 12 V26 M60 68 L78 50 M94 32 L102 24"/>`,
    calendar: () => `<rect x="14" y="22" width="92" height="86" rx="12"/><path d="M14 48 H106 M38 10 V32 M82 10 V32"/>`,
    dirtbike: () => `<circle cx="24" cy="88" r="20"/><circle cx="98" cy="88" r="20"/><circle cx="24" cy="88" r="4"/><circle cx="98" cy="88" r="4"/><path d="M24 88 L52 74 M52 74 H70 L78 56 H46 Z M14 36 L40 46 H80 L86 40 M48 46 L46 56 M98 88 L84 32 M76 30 H94 M88 46 L110 54"/>`,
    helmet: () => `<path d="M24 80 C20 46 44 18 76 18 C98 18 108 34 108 52"/><path d="M108 52 V86 C108 96 100 102 90 102 H52 C38 102 28 94 24 80"/><path d="M62 52 H108 V72 H70 C65 72 62 68 62 63 Z"/><path d="M80 20 L116 30"/>`,
    gate: () => `<path d="M8 94 H112 M16 94 V66 H104 V94 M16 66 L28 40 M50 66 L62 40 M84 66 L96 40"/>`,
    flag: (c) => `<path d="M24 112 V12"/><rect x="26" y="16" width="76" height="51"/>${checker(c)}`,
    trophy: () => `<path d="M38 14 H82 V44 C82 60 72 70 60 70 C48 70 38 60 38 44 Z M38 24 H22 C22 40 28 48 38 50 M82 24 H98 C98 40 92 48 82 50 M60 70 V90 M40 106 H80 L76 90 H44 Z"/>`,
    arm: () => `<path d="M10 72 C20 42 54 40 64 62 L74 38 L72 30 C70 16 78 10 88 10 L98 12 C106 14 108 24 104 32 L100 38 V84 C100 94 92 100 82 100 H10 Z"/><path d="M76 24 H102 M64 62 C70 70 80 72 88 66"/>`,
    lungs: () => `<path d="M60 12 V54 M60 44 L50 56 M60 44 L70 56"/><path d="M46 32 C28 36 14 60 14 88 C14 104 26 108 38 102 C46 98 48 90 48 80 V36 Z"/><path d="M74 32 C92 36 106 60 106 88 C106 104 94 108 82 102 C74 98 72 90 72 80 V36 Z"/>`,
    person: () => `<circle cx="60" cy="28" r="16"/><path d="M30 110 V78 C30 60 44 50 60 50 C76 50 90 60 90 78 V110"/>`,
    dumbbell: () => `<path d="M30 60 H90"/><rect x="10" y="42" width="12" height="36" rx="4"/><rect x="98" y="42" width="12" height="36" rx="4"/><rect x="22" y="32" width="12" height="56" rx="4"/><rect x="86" y="32" width="12" height="56" rx="4"/>`,
    barbell: () => `<path d="M6 60 H114"/><rect x="20" y="32" width="12" height="56" rx="3"/><rect x="88" y="32" width="12" height="56" rx="3"/><rect x="34" y="42" width="8" height="36" rx="3"/><rect x="78" y="42" width="8" height="36" rx="3"/>`,
    bicycle: () => `<circle cx="28" cy="80" r="22"/><circle cx="92" cy="80" r="22"/><path d="M28 80 L48 46 H82 L92 80 M48 46 L60 80 L82 46 M60 80 H28 M42 36 H56 M82 46 L78 30 H90"/>`,
    watch: () => `<rect x="32" y="30" width="56" height="60" rx="12"/><path d="M44 30 L48 10 H72 L76 30 M44 90 L48 110 H72 L76 90 M40 62 H52 L56 52 L62 72 L66 62 H80"/>`,
    gauge: () => `<path d="M14 86 A46 46 0 0 1 106 86"/><path d="M60 86 L86 54"/><path d="M14 86 H24 M96 86 H106 M60 40 V50"/>`,
    bottle: () => `<path d="M48 8 H72 V22 H48 Z M44 22 H76 L82 36 V104 C82 108 78 112 74 112 H46 C42 112 38 108 38 104 V36 Z M38 56 H82"/>`,
    food: () => `<path d="M30 12 V40 C30 52 40 56 40 56 C40 56 50 52 50 40 V12 M40 12 V44 M40 56 V110 M82 110 V12 C94 24 96 50 82 64"/>`,
    sleep: () => `<path d="M78 16 C52 20 36 42 36 64 C36 90 56 108 82 106 C96 105 106 98 110 90 C84 96 60 78 60 52 C60 36 68 22 78 16 Z"/>`,
    target: () => `<circle cx="60" cy="60" r="48"/><circle cx="60" cy="60" r="28"/><circle cx="60" cy="60" r="7"/>`,
    flame: () => `<path d="M60 108 C36 108 22 92 22 72 C22 50 40 40 44 16 C56 28 60 40 58 54 C66 48 70 40 70 30 C86 44 98 60 98 76 C98 94 84 108 60 108 Z"/>`,
    bolt: () => `<path d="M68 8 L28 66 H58 L50 112 L92 50 H62 Z"/>`,
    up: () => `<path d="M14 12 V106 H108 M24 88 L48 64 L66 76 L100 34 M84 34 H100 V50"/>`,
    down: () => `<path d="M14 12 V106 H108 M24 34 L48 58 L66 46 L100 88 M84 88 H100 V72"/>`,
    scale: () => `<rect x="14" y="14" width="92" height="92" rx="18"/><rect x="38" y="28" width="44" height="20" rx="5"/>`,
    send: () => `<path d="M10 58 L110 14 L74 106 L56 66 Z M56 66 L110 14"/>`,
    check: () => `<path d="M22 62 L48 88 L100 30"/>`,
    cross: () => `<path d="M26 26 L94 94 M94 26 L26 94"/>`,
  };
  // the battery is wider (300 x 130) and fills segment by segment
  const battery = (c) =>
    `<rect x="3" y="3" width="270" height="124" rx="18" stroke="${c}" stroke-width="6"/><rect x="279" y="42" width="16" height="46" rx="5" fill="${c}" stroke="none"/>` +
    [0, 1, 2, 3].map((i) => `<rect class="seg" x="${20 + i * 63}" y="20" width="51" height="90" rx="8" fill="${c}" stroke="none"/>`).join("");
  // k scales the drawing (stroke too); the icons scene draws them at 1.35x
  function iconSvg(name, color, k = 1) {
    const c = color === "red" ? RED : color === "gray" ? LINE : INK;
    if (name === "battery") return `<svg width="300" height="130" viewBox="0 0 300 130" fill="none">${battery(c)}</svg>`;
    const body = (ICONS[name] || ICONS.target)(c);
    return `<svg width="${120 * k}" height="${120 * k}" viewBox="0 0 120 120" fill="none" stroke="${c}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
  }

  // ---------- building blocks ----------
  function el(html, css, cls) {
    const d = document.createElement("div");
    d.className = cls || "";
    d.innerHTML = html;
    Object.assign(d.style, { position: "absolute" }, css);
    root.appendChild(d);
    return d;
  }
  const title = (s, top, size = 104) =>
    el(rich(s), { left: "0", width: "1080px", top: top + "px", textAlign: "center", fontSize: size + "px" }, "wb-title");
  const label = (s, cx, top, size = 32, w = 460, dark = false) =>
    el(rich(s), { left: cx - w / 2 + "px", width: w + "px", top: top + "px", textAlign: "center", fontSize: size + "px", color: dark ? INK : GRAY }, "wb-label");
  const footnote = (s) => el(rich(s), { left: "0", width: "1080px", top: "1370px", textAlign: "center" }, "wb-foot");
  function rise(els, t, stagger = 0) {
    gsap.set(els, { opacity: 0, y: 12 });
    tl.to(els, { opacity: 1, y: 0, duration: 0.4, ease: "power2.out", stagger }, t);
  }
  const dim = (els, t) => tl.to(els, { opacity: 0.3, duration: 0.3, ease: "power2.out" }, t);
  const clear = (els, t) => tl.to(els, { opacity: 0, duration: 0.25, ease: "power2.in" }, t);
  const grow = (bar, t, dur = 0.45) => {
    gsap.set(bar, { scaleY: 0, transformOrigin: "50% 100%" });
    tl.to(bar, { scaleY: 1, duration: dur, ease: "power2.out" }, t);
  };
  const T = (v, fallback) => (typeof v === "number" ? v : fallback);
  // a sub line under a scene, and an italic footnote at the bottom, on any scene
  function extras(s, els, y) {
    if (s.sub) {
      const e = label(s.sub, s.x || 540, s.subY || y, 32, 900);
      rise(e, T(s.subCue, s.at + 0.4));
      els.push(e);
    }
    if (s.note) {
      const e = footnote(s.note);
      rise(e, T(s.noteCue, s.at + 0.6));
      els.push(e);
    }
    return els;
  }

  // ---------- scenes ----------
  const SCENES = {
    // 1 to 3 icons with labels. Each lands on its own cue; the ones already up slide over to make room.
    // items: [{icon, label, cue, color: "red"|"gray", fillCue (battery)}], link: "dash"|"arrow"|"vs"
    icons(s) {
      const y = s.y || 470, items = s.items, els = [], k = s.size || 1.35;
      const gapFor = (n) => (n === 2 ? 420 : 320);
      const boxes = items.map((it) => {
        const bat = it.icon === "battery", w = bat ? 300 : 120 * k, h = bat ? 130 : 120 * k;
        const box = el(`<div style="width:${w}px;margin:0 auto">${iconSvg(it.icon, it.color, bat ? 1 : k)}</div>`, { left: "360px", top: y + "px", width: "360px" });
        box.dataset.icon = it.icon;
        if (it.label) {
          const l = el(rich(it.label), { left: "0", top: h + 28 + "px", width: "360px", textAlign: "center", fontSize: "32px", position: "absolute" }, "wb-label");
          box.appendChild(l);
        }
        return box;
      });
      // replay the landings in time order, re-spacing whatever is visible
      const order = items.map((it, i) => [T(it.cue, s.at), i]).sort((a, b) => a[0] - b[0]);
      const shown = [];
      order.forEach(([t, i]) => {
        shown.push(i);
        shown.sort((a, b) => a - b);
        const n = shown.length;
        shown.forEach((j, k) => {
          const dx = (k - (n - 1) / 2) * gapFor(n);
          if (j === i) gsap.set(boxes[j], { x: dx });
          else tl.to(boxes[j], { x: dx, duration: 0.4, ease: "power2.inOut" }, t - 0.15);
        });
        rise(boxes[i], t);
        if (s.focus) shown.filter((j) => j !== i).forEach((j) => dim(boxes[j], t));
        const it = items[i];
        if (it.icon === "battery") {
          const segs = boxes[i].querySelectorAll(".seg");
          gsap.set(segs, { opacity: 0 });
          tl.to(segs, { opacity: 1, duration: 0.2, ease: "power2.out", stagger: 0.22 }, T(it.fillCue, t + 0.4));
        }
      });
      els.push(...boxes);
      if (s.link && items.length > 1) {
        const n = items.length, gap = gapFor(n), t = Math.max(...order.map((o) => o[0]));
        for (let j = 0; j < n - 1; j++) {
          const a = 540 + (j - (n - 1) / 2) * gap, b = a + gap;
          const w0 = items[j].icon === "battery" ? 150 : 60 * k, w1 = items[j + 1].icon === "battery" ? 150 : 60 * k;
          const x0 = a + w0 + 24, x1 = b - w1 - 24, len = x1 - x0;
          let html;
          if (s.link === "vs") html = `<div class="wb-title" style="font-size:56px;color:${LINE};width:${len}px;text-align:center">vs</div>`;
          else
            html = `<svg width="${len}" height="30" viewBox="0 0 ${len} 30" fill="none" stroke="${LINE}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 15 H${len - 6}" stroke-dasharray="2 12"/>${s.link === "arrow" ? `<path d="M${len - 22} 5 L${len - 4} 15 L${len - 22} 25"/>` : ""}</svg>`;
          const lk = el(html, { left: x0 + "px", top: y + (s.link === "vs" ? 30 : 50) * k + "px" });
          gsap.set(lk, { clipPath: "inset(0 100% 0 0)" });
          tl.to(lk, { clipPath: "inset(0 0% 0 0)", duration: 0.4, ease: "power2.out" }, t + 0.2);
          els.push(lk);
        }
      }
      return extras(s, els, y + 120 * k + 150);
    },

    // two columns of bars, e.g. high vs low. cols: [{head, frac, red, cue, mark: "check"|"cross", markCue,
    // lines: [{text, cue}]}]. The first column dims when the second lands (dim: false keeps it).
    hilo(s) {
      const y = s.y || 440, els = [];
      const cols = s.cols.map((c, i) => {
        const cx = s.cols.length === 1 ? 540 : i ? 750 : 330, t = T(c.cue, s.at), col = c.red ? RED : INK;
        const h = title(c.head, y, 64);
        Object.assign(h.style, { left: cx - 200 + "px", width: "400px", color: col });
        const track = el("", { left: cx - 55 + "px", top: y + 160 + "px", width: "110px", height: "320px", borderRadius: "14px", background: TRACK });
        const fr = c.frac == null ? 0.5 : c.frac;
        const bar = el("", { left: cx - 55 + "px", top: y + 160 + 320 * (1 - fr) + "px", width: "110px", height: 320 * fr + "px", borderRadius: "14px", background: col });
        rise([h, track], t + 0.05, 0.1);
        grow(bar, t + 0.3);
        const mine = [h, track, bar];
        if (c.mark) {
          const m = el(iconSvg(c.mark, c.mark === "cross" ? "red" : "ink"), { left: cx - 30 + "px", top: y + 94 + "px", transform: "scale(0.5)", transformOrigin: "0 0" });
          rise(m, T(c.markCue, t + 0.6));
          mine.push(m);
        }
        (c.lines || []).forEach((ln, k) => {
          const l = label(ln.text, cx, y + 510 + k * 105, 30, 380, true);
          rise(l, T(ln.cue, t + 0.8 + k * 0.4));
          mine.push(l);
        });
        els.push(...mine);
        return { mine, t };
      });
      if (cols.length > 1 && s.dim !== false) dim(cols[0].mine, cols[1].t);
      return extras(s, els, y + 740);
    },

    // a 0-100% bar: dark fill to fill.to, then the zone up to band.to in red. fill: {to, cue}, band: {to, cue},
    // axis: "% of max\nheart rate", axisCue, check: true. x = bar centre (default 595), y = top of the scale.
    zone(s) {
      const H = 400, bw = 150, cx = s.x || 595, top = s.y || 830, base = top + H, bx = cx - bw / 2, ax = bx - 70;
      const yy = (p) => base - (H * p) / 100, els = [];
      const frame = [
        el("", { left: ax + "px", top: top - 20 + "px", width: "4px", height: H + 24 + "px", background: INK, borderRadius: "2px" }),
        el("", { left: ax + "px", top: base + "px", width: bw + 190 + "px", height: "4px", background: INK, borderRadius: "2px" }),
        el("", { left: bx + "px", top: top + "px", width: bw + "px", height: H + "px", background: TRACK, borderRadius: "12px 12px 0 0" }),
      ];
      [0, 20, 40, 60, 80, 100].forEach((v) => frame.push(el(v + "%", { left: ax - 84 + "px", top: yy(v) - 14 + "px" }, "wb-tick")));
      rise(frame, s.at);
      els.push(...frame);
      const f = s.fill || { to: 60 }, tf = T(f.cue, s.at + 0.3);
      const fill = el("", { left: bx + "px", top: yy(f.to) + "px", width: bw + "px", height: (H * f.to) / 100 + "px", background: INK });
      grow(fill, tf, 0.4);
      const dash = (p) => el("", { left: ax + 6 + "px", top: yy(p) + "px", width: bw + 150 + "px", borderTop: `3px dashed ${LINE}` });
      const df = dash(f.to), lf = label(`${f.to}%`, bx + bw + 100, yy(f.to) - 6, 28, 110, true);
      rise([df, lf], tf + 0.3);
      els.push(fill, df, lf);
      if (s.band) {
        const b = s.band, tb = T(b.cue, tf + 0.5);
        const band = el("", { left: bx + "px", top: yy(b.to) + "px", width: bw + "px", height: (H * (b.to - f.to)) / 100 + "px", background: RED });
        grow(band, tb, 0.3);
        const db = dash(b.to), lb = label(`*${b.to}%*`, bx + bw + 100, yy(b.to) - 34, 28, 110, true);
        rise([db, lb], tb + 0.1);
        els.push(band, db, lb);
        if (s.check) {
          const c = el(iconSvg("check"), { left: bx + bw + 150 + "px", top: yy(b.to) - 52 + "px", transform: "scale(0.5)", transformOrigin: "0 30px" });
          rise(c, tb + 0.35);
          els.push(c);
        }
      }
      if (s.axis) {
        const a = label(s.axis, cx, base + 24, 28, 360);
        rise(a, T(s.axisCue, tf + 0.8));
        els.push(a);
      }
      return extras(s, els, base + 120);
    },

    // one big red number with a unit under it. text: "45+", unit: "min", x, y
    bignum(s) {
      const cx = s.x || 540, y = s.y || 560;
      const big = title(`*${s.text}*`, y, s.size || 150);
      Object.assign(big.style, { left: cx - 260 + "px", width: "520px" });
      const els = [big];
      if (s.unit) els.push(label(s.unit, cx, y + (s.size || 150) * 1.05 + 6, 34, 300));
      rise(els, s.at, 0.1);
      return extras(s, els, y + 260);
    },

    // seven day boxes filling on cues. fills: [{days: [0, 2, 4], cue, red}], head: "*3-4x* a week", headCue
    week(s) {
      const y = s.y || 720, els = [];
      const days = "MTWTFSS".split("").map((ch, i) => {
        const x = 142 + i * 116;
        const box = el("", { left: x + "px", top: y + "px", width: "100px", height: "100px", borderRadius: "16px", background: TRACK });
        const lab = label(ch, x + 50, y + 125, 30, 100);
        rise([box, lab], s.at + 0.05 + i * 0.04);
        els.push(box, lab);
        return box;
      });
      (s.fills || []).forEach((f) =>
        f.days.forEach((d, k) => tl.to(days[d], { backgroundColor: f.red ? RED : INK, duration: 0.25, ease: "power2.out" }, T(f.cue, s.at + 0.5) + k * 0.12)));
      if (s.head) {
        const h = title(s.head, y - 250, 96);
        rise(h, T(s.headCue, T((s.fills || [{}])[0].cue, s.at)));
        els.push(h);
      }
      return extras(s, els, y + 200);
    },

    // a heartbeat line that draws itself; gaps: ["0.83 s", ...] label the spaces between beats on gapsCue
    heartbeat(s) {
      const base = s.y || 700, peaks = [180, 410, 680, 895], els = [];
      let d = `M60 ${base}`;
      peaks.forEach((x) => {
        d += ` L${x - 60} ${base} Q${x - 45} ${base - 20} ${x - 30} ${base} L${x - 12} ${base} L${x - 6} ${base + 20} L${x} ${base - 140} L${x + 8} ${base + 40} L${x + 16} ${base} L${x + 34} ${base} Q${x + 52} ${base - 30} ${x + 70} ${base}`;
      });
      d += ` L1020 ${base}`;
      const ecg = el(`<svg width="1080" height="${base + 60}" viewBox="0 0 1080 ${base + 60}" fill="none"><path d="${d}" stroke="${s.red ? RED : INK}" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/></svg>`,
        { left: "0px", top: "0px" });
      const p = ecg.querySelector("path"), L = p.getTotalLength();
      gsap.set(p, { strokeDasharray: L, strokeDashoffset: L });
      tl.to(p, { strokeDashoffset: 0, duration: 1.1, ease: "none" }, s.at + 0.3);
      els.push(ecg);
      (s.gaps || []).slice(0, 3).forEach((g, i) => {
        const a = peaks[i], b = peaks[i + 1];
        const m = el(`<svg width="${b - a}" height="24" viewBox="0 0 ${b - a} 24" fill="none" stroke="${LINE}" stroke-width="3" stroke-linecap="round"><path d="M2 2 V22 M${b - a - 2} 2 V22 M2 12 H${b - a - 2}"/></svg>`,
          { left: a + "px", top: base + 90 + "px" });
        const l = label(g, (a + b) / 2, base + 128, 30, 200, true);
        rise([m, l], T(s.gapsCue, s.at + 1.4) + i * 0.3);
        els.push(m, l);
      });
      return extras(s, els, base + 240);
    },

    // a list of lines; on redCue the "red" ones turn HP red and the rest dim (Tony's ingredient list).
    // lines: ["Protein", ...], red: [0, 3], redCue
    list(s) {
      const y = s.y || 460, els = s.lines.map((ln, i) => label(ln, 540, y + i * 72, 46, 900, true));
      rise(els, s.at, 0.08);
      if (s.red) {
        const t = T(s.redCue, s.at + 1);
        els.forEach((e, i) => tl.to(e, s.red.includes(i) ? { color: RED, duration: 0.3 } : { opacity: 0.3, duration: 0.3 }, t));
      }
      return extras(s, els, y + s.lines.length * 72 + 40);
    },

    // up to 6 bars side by side, each landing on its cue. bars: [{label, value 0-1, cue, red}]
    bars(s) {
      const y = s.y || 520, H = 420, n = s.bars.length, w = 110, gap = Math.min(150, 860 / n), els = [];
      const base = el("", { left: 540 - (n * gap) / 2 - 20 + "px", top: y + H + "px", width: n * gap + 40 + "px", height: "4px", background: INK, borderRadius: "2px" });
      rise(base, s.at);
      els.push(base);
      s.bars.forEach((b, i) => {
        const cx = 540 + (i - (n - 1) / 2) * gap, t = T(b.cue, s.at + 0.2 + i * 0.2);
        const bar = el("", { left: cx - w / 2 + "px", top: y + H * (1 - b.value) + "px", width: w + "px", height: H * b.value + "px", borderRadius: "12px 12px 0 0", background: b.red ? RED : INK });
        grow(bar, t);
        els.push(bar);
        if (b.label) {
          const l = label(b.label, cx, y + H + 22, 28, gap + 20);
          rise(l, t);
          els.push(l);
        }
      });
      return extras(s, els, y + H + 120);
    },

    // one bar split into parts, e.g. 90% easy / 10% hard. parts: [{label, pct, red, cue}]
    split(s) {
      const y = s.y || 640, W = 900, x0 = 90, els = [];
      const track = el("", { left: x0 + "px", top: y + "px", width: W + "px", height: "110px", borderRadius: "16px", background: TRACK, overflow: "hidden" });
      rise(track, s.at);
      els.push(track);
      let x = 0;
      s.parts.forEach((p, i) => {
        const w = (W * p.pct) / 100, t = T(p.cue, s.at + 0.3 + i * 0.6);
        const part = document.createElement("div");
        Object.assign(part.style, { position: "absolute", left: x + "px", top: "0", width: w + "px", height: "110px", background: p.red ? RED : INK });
        track.appendChild(part);
        gsap.set(part, { scaleX: 0, transformOrigin: "0 50%" });
        tl.to(part, { scaleX: 1, duration: 0.45, ease: "power2.out" }, t);
        const l = label(`${p.red ? "*" + p.pct + "%*" : p.pct + "%"}\n${p.label}`, x0 + x + w / 2, y + 135, 30, Math.max(w, 220), true);
        rise(l, t + 0.2);
        els.push(l);
        x += w;
      });
      return extras(s, els, y + 300);
    },

    // rows with a check or a cross landing on each cue. rows: [{text, mark: "check"|"cross", cue}]
    checks(s) {
      const y = s.y || 470, els = [];
      s.rows.forEach((r, i) => {
        const t = T(r.cue, s.at + i * 0.6), top = y + i * 125;
        const m = el(iconSvg(r.mark || "check", r.mark === "cross" ? "red" : "ink", 0.72), { left: (s.left || 190) + "px", top: top - 6 + "px" });
        const l = el(rich(r.text), { left: (s.left || 190) + 110 + "px", top: top + "px", width: "720px", fontSize: "60px", lineHeight: "1.2" }, "wb-title");
        rise([m, l], t, 0.08);
        els.push(m, l);
      });
      return extras(s, els, y + s.rows.length * 125 + 30);
    },
  };

  // Plays the scene list. A scene clears everything before it unless it has keep: "dim" (earlier pieces
  // dim) or keep: "full" (they stay as they are). A title stays up until a scene names a different one.
  // carry: "heart", carryTo: [centre x, top, scale] moves that icon from the scene before into this one
  // instead of clearing it (its label fades), so one point flows into the next.
  function play(list) {
    let stack = [], curTitle = null, titleEl = null;
    list.forEach((s) => {
      const t = s.at;
      let carried = null;
      if (s.carry) {
        carried = stack.find((e) => e.dataset && e.dataset.icon === s.carry) || null;
        if (carried) {
          stack = stack.filter((e) => e !== carried);
          const [cx, top, sc] = s.carryTo || [540, 600, 0.6];
          const lab = carried.querySelector(".wb-label");
          if (lab) tl.to(lab, { opacity: 0, duration: 0.2, ease: "power2.in" }, t - 0.1);
          gsap.set(carried, { transformOrigin: "50% 0" });
          tl.to(carried, { opacity: 1, x: cx - 540, y: top - parseFloat(carried.style.top), scale: sc, duration: 0.6, ease: "power2.inOut" }, t - 0.05);
        }
      }
      if (!s.keep) {
        if (stack.length) clear(stack, t - 0.1);
        stack = [];
      } else if (s.keep === "dim") dim(stack, t);
      if (s.title !== undefined && s.title !== curTitle) {
        // the old title is gone before the new one rises, so the two never overlap
        const had = !!titleEl;
        if (titleEl) clear(titleEl, t - 0.15);
        titleEl = s.title ? title(s.title, s.title.includes("\n") ? 250 : 280) : null;
        if (titleEl) rise(titleEl, t + (had ? 0.15 : 0.05));
        curTitle = s.title;
      }
      stack = stack.concat(SCENES[s.type](s));
      if (carried) stack.push(carried);
    });
  }

  return { init, play, rich, el, title, label, rise, dim, clear, iconSvg, ICONS, INK, RED, GRAY, LINE, TRACK };
})();
