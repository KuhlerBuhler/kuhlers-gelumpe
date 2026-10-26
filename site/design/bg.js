// BLECH-style page background: a calm star field on a fixed 1-bit cell grid, drawn like the
// README banner (square pixels, no anti-aliasing, dither on a 2 cell pitch), and now and then a
// pair of Blechy's eyes that blinks up out of the dither. Included on every page (canvas + this script).
// Self-initialising; does nothing without a #bg-canvas.
//
// One canvas pixel is one cell, the canvas is scaled up with image-rendering: pixelated, so the
// edges stay hard at every zoom level and the frame is a few thousand pixels, not a full-size bitmap.
// Colours, cell size and opacities come from the --cee-bg-* tokens on the canvas (app.css).
//
// Switches (all optional):
//   data-variant="dust" | "bands"   or ?bg=dust | bands | off   dust (default): stars, dither bands at the
//                                   sides and faint dithered clouds drifting over the page; bands: no clouds
//   data-eyes="off"                 or ?bg-eyes=off | now        the eyes can be turned off; "now" shows them
//                                   after a second (for screenshots and tests)
//
// prefers-reduced-motion draws one static frame (no drift, no twinkle, no eyes). Drawing runs at a
// low frame rate and stops while the tab is hidden or the window is in the background. A machine that
// cannot keep up gets the static frame too: when frames come late again and again, drawing stops until
// the next load, and the canvas says so in data-still="stalled".
(function () {
    const bg = document.getElementById('bg-canvas');
    if (!bg) return;
    const ctx = bg.getContext('2d');
    if (!ctx) return;

    const query = new URLSearchParams(location.search);
    const variant = ['bands', 'dust', 'off'].includes(query.get('bg')) ? query.get('bg') : (bg.dataset.variant || 'dust');
    const eyesMode = query.get('bg-eyes') || bg.dataset.eyes || 'on';
    if (variant === 'off') { bg.hidden = true; return; }

    const FPS = 12;
    const FRAME_MS = 1000 / FPS;
    // A frame this much later than planned counts as late; this many late frames within the window stop drawing.
    const LATE_MS = 250, LATE_COUNT = 3, LATE_WINDOW_MS = 10000;
    const motionQuery = matchMedia('(prefers-reduced-motion: reduce)');
    let reduceMotion = motionQuery.matches;

    // ---------- tokens ----------
    const css = getComputedStyle(bg);
    const num = (name, fallback) => {
        const v = parseFloat(css.getPropertyValue(name));
        return Number.isFinite(v) ? v : fallback;
    };
    // Resolve any CSS colour to packed ABGR (little-endian RGBA) with the given opacity.
    const probe = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
    const packed = (name, opacity) => {
        probe.clearRect(0, 0, 1, 1);
        probe.fillStyle = css.getPropertyValue(name).trim() || '#ffffff';
        probe.fillRect(0, 0, 1, 1);
        const [r, g, b] = probe.getImageData(0, 0, 1, 1).data;
        return (Math.round(opacity * 255) << 24 | b << 16 | g << 8 | r) >>> 0;
    };
    const INK = {
        dust: packed('--cee-bg-ink', num('--cee-bg-dust', 0.07)),
        band: packed('--cee-bg-ink', num('--cee-bg-band', 0.14)),
        starDim: packed('--cee-bg-ink', num('--cee-bg-star-dim', 0.28)),
        star: packed('--cee-bg-ink', num('--cee-bg-star', 0.55)),
        eye: packed('--cee-bg-eye', num('--cee-bg-eye-opacity', 0.26)),
    };
    const CELL_CSS = num('--cee-bg-cell', 4);

    // ---------- grid ----------
    const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map(v => (v + 0.5) / 16);
    const bayer = (x, y) => BAYER[(y & 3) * 4 + (x & 3)];

    let cols = 0, rows = 0, cellCss = CELL_CSS;
    let image = null, frame = null, base = null;
    let stars = [];
    const mouse = { x: -9999, y: -9999 };

    // Deterministic noise for the clouds, so the page looks the same on every load.
    function rng(seed) {
        let s = seed >>> 0;
        return () => (s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296;
    }

    // ---------- dust: tileable two octave value noise, shaped so large parts stay empty ----------
    const TILE = 128;
    const dustTile = (() => {
        const rand = rng(7);
        const octave = (n) => {
            const g = Float32Array.from({ length: n * n }, rand);
            const step = TILE / n;
            const smooth = (t) => t * t * (3 - 2 * t);
            const out = new Float32Array(TILE * TILE);
            for (let y = 0; y < TILE; y++) {
                const gy = y / step, y0 = Math.floor(gy), fy = smooth(gy - y0);
                for (let x = 0; x < TILE; x++) {
                    const gx = x / step, x0 = Math.floor(gx), fx = smooth(gx - x0);
                    const at = (i, j) => g[(j % n) * n + (i % n)];
                    const top = at(x0, y0) * (1 - fx) + at(x0 + 1, y0) * fx;
                    const bottom = at(x0, y0 + 1) * (1 - fx) + at(x0 + 1, y0 + 1) * fx;
                    out[y * TILE + x] = top * (1 - fy) + bottom * fy;
                }
            }
            return out;
        };
        const a = octave(8), b = octave(16);
        const out = new Float32Array(TILE * TILE);
        for (let i = 0; i < out.length; i++) out[i] = Math.min(1, Math.max(0, (0.65 * a[i] + 0.35 * b[i] - 0.42) * 2.4));
        return out;
    })();
    let dustX = 0, dustY = 0;

    // ---------- base layer: bands (and dust), rebuilt only when the size or the dust offset changes ----------
    function bandDensity(x) {
        const width = Math.min(44, Math.max(14, Math.round(cols * 0.09)));
        const edge = Math.min(x, cols - 1 - x);
        return edge >= width ? 0 : Math.pow(1 - edge / width, 1.4) * 0.9;
    }

    function buildBase() {
        base.fill(0);
        for (let j = 0; j < rows; j += 2) {
            for (let i = 0; i < cols; i += 2) {
                const t = bayer(i >> 1, j >> 1);
                const at = j * cols + i;
                if (variant === 'dust') {
                    const d = dustTile[(((j - dustY) % TILE + TILE) % TILE) * TILE + (((i - dustX) % TILE + TILE) % TILE)];
                    if (d * 0.55 > t) base[at] = INK.dust;
                }
                if (bandDensity(i) > t) base[at] = INK.band;
            }
        }
    }

    // ---------- stars: one cell each, three depths, drifting down in whole cells ----------
    function initStars() {
        const count = Math.min(240, Math.floor(cols * rows / 650));
        const rand = rng(23);
        stars = Array.from({ length: count }, () => {
            const z = rand();
            const layer = z < 0.45 ? 0 : z < 0.85 ? 1 : 2;
            return {
                x: Math.floor(rand() * cols), y: rand() * rows, layer,
                vy: [0.5, 1.2, 2.2][layer] * (0.8 + rand() * 0.4), // cells per second
                period: 4 + rand() * 6, phase: rand(),               // seconds per twinkle
                plus: layer === 2 && rand() < 0.12,
            };
        });
    }

    function drawStars(t) {
        const px = ((mouse.x < 0 ? innerWidth / 2 : mouse.x) - innerWidth / 2) / cellCss;
        const py = ((mouse.y < 0 ? innerHeight / 2 : mouse.y) - innerHeight / 2) / cellCss;
        const set = (x, y, v) => { if (x >= 0 && y >= 0 && x < cols && y < rows) frame[y * cols + x] = v; };
        for (const s of stars) {
            // a star goes dark for a moment now and then, off or on, never half
            if (!reduceMotion && ((t / s.period + s.phase) % 1) > 0.9) continue;
            const depth = [0.3, 0.6, 1][s.layer] * 0.02;
            const x = s.x + Math.round(px * depth), y = Math.floor(s.y) + Math.round(py * depth);
            const v = s.layer === 0 ? INK.starDim : INK.star;
            set(x, y, v);
            if (s.layer === 2) set(x + 1, y, v);       // near stars are two cells wide like the banner's
            if (s.plus) { set(x, y - 1, v); set(x + 1, y + 1, v); set(x, y + 2, INK.starDim); set(x - 1, y, INK.starDim); set(x + 2, y, INK.starDim); }
        }
    }

    function stepStars(dt) {
        for (const s of stars) {
            s.y += s.vy * dt;
            if (s.y >= rows) { s.y -= rows; s.x = Math.floor(Math.random() * cols); }
        }
    }

    // ---------- eyes: Blechy's, small, dithering in and out ----------
    // Cut from his calm sprite (assets/blechy/sprites/blechy-calm.png): brows, rings, the double bags under
    // them; the pupils are drawn on their own so they can glance and blink.
    const BLECHY_EYES = [
        '............####.....',
        '...###.........###...',
        '.##...##.....##...##.',
        '.#.....#.....#.....#.',
        '#.......#...#.......#',
        '#.......#...#.......#',
        '#.......#...#.......#',
        '.#.....#.....#.....#.',
        '.##...##.....##...##.',
        '...###.........###...',
        '.#.....#.....#.....#.',
        '..#...#.......#...#..',
        '.#.###.#.....#.###.#.',
    ];
    const PUPILS = { at: [[3, 4], [15, 4]], size: 3 };
    const EYE_SCALE = 2;   // two cells per pixel of the sprite, so his face reads at the size of the old eyes

    let eye = null;       // the running appearance, or null
    let eyeTimer = 0;     // seconds until the next one
    const EYE = { dither: 0.9, hold: 3.2, blinkAt: 2.2, blinkFor: 0.17, glanceAt: 0.9 };
    const eyeLife = EYE.dither * 2 + EYE.hold;

    function scheduleEye(first) {
        if (eyesMode === 'now') eyeTimer = first ? 1 : 12;
        else eyeTimer = first ? 25 + Math.random() * 35 : 50 + Math.random() * 70;
    }

    function startEye() {
        if (cols < 160 || rows < 40) return; // on a phone the pair would sit behind the text
        const width = BLECHY_EYES[0].length * EYE_SCALE;
        const fromLeft = Math.random() < 0.5;
        const bandWidth = Math.min(44, Math.max(14, Math.round(cols * 0.09)));
        const reach = Math.max(2, bandWidth - Math.round(width / 2));
        const cx = fromLeft ? Math.round(width / 2) + 2 + Math.floor(Math.random() * reach) : cols - Math.round(width / 2) - 2 - Math.floor(Math.random() * reach);
        const y = Math.floor(rows * (0.12 + Math.random() * 0.62));
        eye = { x: cx - Math.round(width / 2), y, look: fromLeft ? 1 : -1, age: 0 };
    }

    function drawEye(dt) {
        eye.age += dt;
        if (eye.age >= eyeLife) { eye = null; scheduleEye(false); return; }
        // progress 0..1..0: a cell shows while its Bayer threshold lies below it
        const p = eye.age < EYE.dither ? eye.age / EYE.dither
            : eye.age > eyeLife - EYE.dither ? (eyeLife - eye.age) / EYE.dither : 1;
        const t = eye.age - EYE.dither;
        const blink = t > EYE.blinkAt && t < EYE.blinkAt + EYE.blinkFor;
        const look = t > EYE.glanceAt ? eye.look : 0;
        const cell = (x, y, v) => { if (x >= 0 && y >= 0 && x < cols && y < rows && (p >= 1 || bayer(x, y) < p)) frame[y * cols + x] = v; };
        const set = (i, j, v) => { for (let b = 0; b < EYE_SCALE; b++) for (let a = 0; a < EYE_SCALE; a++) cell(eye.x + i * EYE_SCALE + a, eye.y + j * EYE_SCALE + b, v); };
        BLECHY_EYES.forEach((line, j) => {
            for (let i = 0; i < line.length; i++) set(i, j, line[i] === '#' ? INK.eye : 0);
        });
        if (blink) return;
        for (const [px, py] of PUPILS.at)
            for (let j = 0; j < PUPILS.size; j++)
                for (let i = 0; i < PUPILS.size; i++) set(px + look + i, py + j, INK.eye);
    }

    // ---------- loop ----------
    function draw(t, dt) {
        frame.set(base);
        drawStars(t);
        if (eye) drawEye(dt);
        ctx.putImageData(image, 0, 0);
    }

    let timer = 0, last = 0, clock = 0, dustClock = 0;
    let late = [], stalled = false, away = false;
    function tick() {
        timer = 0;
        if (document.hidden || reduceMotion || away) return;
        const now = performance.now();
        if (now - last > FRAME_MS + LATE_MS) {
            late = late.filter(at => now - at < LATE_WINDOW_MS);
            late.push(now);
            if (late.length >= LATE_COUNT) {
                stalled = true;
                bg.dataset.still = 'stalled';
                eye = null;
                draw(clock, 0);
                return;
            }
        }
        const dt = Math.min(0.25, (now - last) / 1000);
        last = now;
        clock += dt;
        stepStars(dt);
        if (variant === 'dust') {
            dustClock += dt;
            if (dustClock >= 0.7) { dustClock = 0; dustY++; if (dustY % 2) dustX++; buildBase(); }
        }
        if (eyesMode !== 'off') {
            if (!eye && (eyeTimer -= dt) <= 0) startEye();
        }
        draw(clock, dt);
        timer = setTimeout(tick, FRAME_MS);
    }

    function start() {
        if (timer || document.hidden || reduceMotion || stalled || away) return;
        last = performance.now();
        timer = setTimeout(tick, FRAME_MS);
    }

    function stop() { clearTimeout(timer); timer = 0; }

    // The cell is a whole number of device pixels so every cell has the same size on screen.
    function resize() {
        const dpr = window.devicePixelRatio || 1;
        cellCss = Math.max(2, Math.round(CELL_CSS * dpr)) / dpr;
        const oldCols = cols, oldRows = rows;
        cols = Math.ceil(innerWidth / cellCss);
        rows = Math.ceil(innerHeight / cellCss);
        bg.width = cols;
        bg.height = rows;
        bg.style.width = cols * cellCss + 'px';
        bg.style.height = rows * cellCss + 'px';
        image = ctx.createImageData(cols, rows);
        frame = new Uint32Array(image.data.buffer);
        base = new Uint32Array(cols * rows);
        // Only the height changed (address bar on a phone): keep the stars and stretch them.
        if (oldCols !== cols || !stars.length) initStars();
        else if (oldRows) for (const s of stars) s.y *= rows / oldRows;
        eye = null;
        buildBase();
        draw(clock, 0);
    }

    addEventListener('resize', resize);
    document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));
    // Another window in front (the desktop app or the browser switched away): nothing to look at, nothing to draw.
    addEventListener('blur', () => { away = true; stop(); });
    addEventListener('focus', () => { away = false; start(); });
    motionQuery.addEventListener?.('change', () => {
        reduceMotion = motionQuery.matches;
        if (reduceMotion) { stop(); eye = null; draw(0, 0); } else start();
    });
    document.addEventListener('mousemove', (e) => { mouse.x = e.clientX; mouse.y = e.clientY; });
    document.addEventListener('mouseleave', () => { mouse.x = -9999; mouse.y = -9999; });

    scheduleEye(true);
    resize();
    start();
})();
