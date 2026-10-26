/**
 * Discord: the project's server from Discord's widget API, drawn in the page's own look instead of Discord's iframe.
 * Everyone online is a Blechy on the floor of the page: online ones walk to and fro and now and then stop for his dance
 * from the device, away ones stand, busy ones stand with an angry face. The Blechys are solid, so on a full server the
 * front ones cover those behind instead of piling up, and the list of names below the floor keeps everyone readable. The way in is the invite the widget names (Server settings ->
 * Widget -> invite channel), so a deleted invite never sticks in the app.
 */
import { el } from "./fields.mjs";
import { maskOf } from "./support.mjs";
import { outlined } from "../../src/blechy-outline.mjs";
import { reducedMotion } from "./settings.mjs";
import { t } from "./i18n.mjs";

const GUILD = "1563916590498447370";
const API = `https://discord.com/api/guilds/${GUILD}/widget.json`;
const STATUS = { online: "discord.status.online", idle: "discord.status.idle", dnd: "discord.status.dnd" };
const TONE = { online: "ok", idle: "warn", dnd: "error" };
/**
 * The pictures of a Blechy: walking swaps idle and walk like his walk on the display, dancing shows the four terror
 * sprites of his dance on the device (assets/blechy/sprites/blechy-terror-1.png to -4.png, copied as dance-1 to dance-4).
 */
const POSES = {
  idle: "img/blechy/idle.png", walk: "img/blechy/walk.png", angry: "img/blechy/angry.png", sad: "img/blechy/sad.png",
  dance0: "img/blechy/dance-1.png", dance1: "img/blechy/dance-2.png", dance2: "img/blechy/dance-3.png", dance3: "img/blechy/dance-4.png",
};
const POSE_OF = { online: "idle", idle: "sad", dnd: "angry" };
/** The order of the dance frames, one per eighth, as in data/script/blechy-logic.mjs. */
const DANCE = [0, 2, 1, 3, 2, 0, 3, 1];
const SCALE = 2;
const WIDTH = 56 * SCALE;
/** Pixels per second and the time per step, about his pace on the display. */
const SPEED = 40;
const STEP_MS = 240;
/** One eighth at 120 BPM; a dance lasts two bars, and between two dances he walks for a while. */
const EIGHTH_MS = 250;
const DANCE_MS = 16 * EIGHTH_MS;
const walkFor = () => 6000 + Math.random() * 14000;
/** Blechys walk in this many rows, each a little higher and further back than the one in front (app.css). */
const ROWS = 3;
/** The list shows this many names until "more" is pressed. */
const LISTED = 24;

const link = (href, text, className = "cee-text-link") => el("a", { className, href, target: "_blank", rel: "noopener noreferrer", textContent: text });

/** Gaps in his outline up to twice this wide count as closed: his head is open at the side, behind the eye. */
const CLOSE = 3;

/** Every pixel within `r` of a set one, or with `grow` false, only those whose whole square of radius `r` is set. */
function spread(mask, r, grow) {
  return mask.map((row, y) => row.map((_, x) => {
    for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++) if ((mask[y + dy]?.[x + dx] ?? false) === grow) return grow;
    return !grow;
  }));
}

/**
 * His whole silhouette, head included: the sprite widened by CLOSE so the gaps in his outline shut, everything the open
 * space around it cannot reach, narrowed back by CLOSE. The sprite sits in a margin so the space reaches round him.
 */
function solid(mask) {
  const pad = CLOSE + 1;
  const w = mask[0].length + 2 * pad;
  const framed = Array.from({ length: mask.length + 2 * pad }, (_, y) => Array.from({ length: w }, (_, x) => mask[y - pad]?.[x - pad] ?? false));
  const wide = spread(framed, CLOSE, true);
  const outside = wide.map(row => row.map(() => false));
  const todo = [[0, 0]];
  while (todo.length) {
    const [x, y] = todo.pop();
    if (outside[y]?.[x] !== false || wide[y][x]) continue;
    outside[y][x] = true;
    todo.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
  }
  const inside = spread(outside.map(row => row.map(o => !o)), CLOSE, false);
  return mask.map((row, y) => row.map((set, x) => set || inside[y + pad][x + pad]));
}

let poses;
const loadPoses = () => (poses ??= Promise.all(Object.entries(POSES).map(async ([id, src]) => {
  const mask = await maskOf(src);
  return [id, { line: outlined(mask), body: solid(mask) }];
}))
  .then(Object.fromEntries)
  .catch(() => (poses = null)));

/** A pose drawn once: the body in the page's colour, so he covers whoever stands behind him, and his lines on top. */
function sprite({ line, body }, ink, fill) {
  const canvas = el("canvas", { width: WIDTH, height: WIDTH });
  const ctx = canvas.getContext("2d");
  for (const [mask, colour] of [[body, fill], [line, ink]]) {
    ctx.fillStyle = colour;
    mask.forEach((row, y) => row.forEach((set, x) => { if (set) ctx.fillRect(x * SCALE, canvas.height - (mask.length - y) * SCALE, SCALE, SCALE); }));
  }
  return canvas;
}

function paint(canvas, picture) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(picture, 0, 0);
}

/** The name of a member with picture, game and status dot, on the floor above a Blechy and in the list. */
function tag(m) {
  const dot = el("span", { className: "cee-discord-dot" });
  dot.setAttribute("data-tone", TONE[m.status] ?? "warn");
  return el("span", { className: "cee-discord-tag" }, [
    m.avatar_url ? el("img", { className: "cee-discord-avatar", src: m.avatar_url, alt: "", width: 20, height: 20, loading: "lazy" }) : null,
    el("strong", { textContent: m.username }),
    m.game?.name ? el("span", { className: "cee-discord-game muted", textContent: m.game.name }) : null,
    dot,
  ]);
}

/** One member as a Blechy; his name shows while the pointer is on him. `walks` tells the floor whether he moves. */
function blechy(m) {
  const canvas = el("canvas", { className: "cee-discord-blechy-art", width: WIDTH, height: WIDTH });
  const node = el("li", { className: "cee-discord-blechy" }, [tag(m), canvas]);
  return { node, canvas, pose: POSE_OF[m.status] ?? "idle", walks: m.status === "online", x: 0, dir: 1, speed: SPEED, shown: "", dancing: false, until: 0 };
}

/** Everyone online as names, the first LISTED of them until the button shows the rest. */
function people(members) {
  const items = members.map(m => {
    const status = STATUS[m.status] ? t(STATUS[m.status]) : m.status;
    const item = el("li", {}, [tag(m)]);
    item.setAttribute("aria-label", `${m.username}, ${status}${m.game?.name ? `, ${m.game.name}` : ""}`);
    return item;
  });
  items.slice(LISTED).forEach(item => { item.hidden = true; });
  const list = el("ul", { className: "cee-discord-people" }, items);
  list.setAttribute("aria-label", t("discord.online"));
  if (items.length <= LISTED) return [list];
  const more = el("button", { type: "button", className: "cee-text-link cee-discord-more", textContent: t("discord.more", { count: items.length - LISTED }) });
  more.onclick = () => { items.forEach(item => { item.hidden = false; }); more.remove(); };
  return [list, more];
}

/**
 * The floor with everyone online, in ROWS rows, the front row lowest and on top. Returns the element and `start()`,
 * which runs the walk in one animation loop for all of them; now and then each one stops and dances. On another tab
 * the frames only check and skip, and the walk ends when a new answer replaces the floor.
 */
function floor(members) {
  const figures = members.map(blechy);
  figures.forEach((f, i) => { f.node.dataset.row = String(i % ROWS); });
  const list = el("ul", { className: "cee-discord-floor" }, figures.map(f => f.node));
  list.setAttribute("aria-hidden", "true");
  let running = false;
  let room = -1;
  /** Everyone spread out evenly over the width. */
  function place(width) {
    room = width;
    figures.forEach((f, i) => {
      f.x = ((i + 0.5) / figures.length) * Math.max(0, width - WIDTH);
      f.node.style.transform = `translateX(${f.x}px)`;
    });
  }
  function show(f, pose, art) {
    if (f.shown !== pose) { f.shown = pose; paint(f.canvas, art[pose]); }
  }
  async function start() {
    const loaded = await loadPoses();
    if (!loaded || running) return;
    const ink = getComputedStyle(list).color;
    const fill = getComputedStyle(list).getPropertyValue("--color-bg-page").trim();
    const art = Object.fromEntries(Object.entries(loaded).map(([id, pose]) => [id, sprite(pose, ink, fill)]));
    place(list.clientWidth);
    const begin = performance.now();
    figures.forEach((f, i) => {
      f.dir = i % 2 ? -1 : 1;
      f.speed = SPEED * (0.75 + Math.random() * 0.5);
      f.dancing = false;
      f.until = begin + 2000 + Math.random() * 12000;
      f.shown = "";
      f.canvas.style.transform = f.walks && f.dir < 0 && !reducedMotion() ? "scaleX(-1)" : "";
      show(f, f.pose, art);
    });
    if (reducedMotion()) return;
    running = true;
    let last = begin;
    const tick = now => {
      if (!list.isConnected) { running = false; return; }
      const dt = Math.min(now - last, 100) / 1000;
      last = now;
      if (list.offsetParent === null) return requestAnimationFrame(tick);
      if (list.clientWidth !== room) place(list.clientWidth);
      const max = Math.max(0, room - WIDTH);
      const step = Math.floor(now / STEP_MS) % 2;
      const eighth = Math.floor(now / EIGHTH_MS);
      for (const f of figures) {
        if (!f.walks) continue;
        if (now >= f.until) {
          f.dancing = !f.dancing;
          f.until = now + (f.dancing ? DANCE_MS : walkFor());
          f.node.dataset.move = f.dancing ? "dance" : "walk";
          f.canvas.style.transform = !f.dancing && f.dir < 0 ? "scaleX(-1)" : "";
        }
        if (f.dancing) { show(f, `dance${DANCE[eighth % DANCE.length]}`, art); continue; }
        f.x += f.dir * f.speed * dt;
        if (f.x <= 0 || f.x >= max) {
          f.x = Math.min(Math.max(f.x, 0), max);
          f.dir = -f.dir;
          f.canvas.style.transform = f.dir < 0 ? "scaleX(-1)" : "";
        }
        show(f, step ? "walk" : f.pose, art);
        f.node.style.transform = `translateX(${f.x}px)`;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
  return { list, start };
}

/** The page from one answer of the widget API: the elements and the floor's start. */
export function serverView(w) {
  const join = w.instant_invite;
  const members = [...(w.members ?? [])];
  const channels = [...(w.channels ?? [])].sort((a, b) => a.position - b.position);
  const room = members.length ? floor(members) : null;
  const nodes = [
    el("header", { className: "cee-discord-head" }, [
      el("h2", { textContent: w.name }),
      el("p", { className: "muted", textContent: t("discord.count", { count: w.presence_count ?? members.length }) }),
      join ? el("div", { className: "actions" }, [link(join, t("discord.join"), "btn cee-primary")]) : null,
    ]),
    el("section", {}, [
      el("h3", { textContent: t("discord.online") }),
      ...(room ? [room.list, ...people(members)] : [el("p", { className: "muted", textContent: t("discord.nobody") })]),
    ]),
    channels.length ? el("section", {}, [
      el("h3", { textContent: t("discord.voice") }),
      el("ul", { className: "cee-discord-channels" }, channels.map(c => el("li", { textContent: c.name }))),
    ]) : null,
  ].filter(Boolean);
  return { nodes, start: room ? room.start : () => {} };
}

/**
 * @param {HTMLElement} root the page
 * @returns {{ opened(): void }} loads the server when the page is opened, again at most once a minute
 */
export function discordPage(root, fetchImpl = globalThis.fetch) {
  const body = el("div", { className: "cee-discord", "aria-live": "polite" }, [el("p", { className: "muted", textContent: t("discord.loading") })]);
  root.append(el("h1", { className: "ui-sr-only", textContent: t("nav.discord") }), body);
  let loaded = 0;
  let start = () => {};
  async function load() {
    if (Date.now() - loaded < 60000) return start();
    loaded = Date.now();
    try {
      const res = await fetchImpl(API);
      if (!res.ok) throw new Error(String(res.status));
      const view = serverView(await res.json());
      body.replaceChildren(...view.nodes);
      start = view.start;
      start();
    } catch {
      loaded = 0;
      start = () => {};
      body.replaceChildren(el("p", { textContent: t("discord.offline") }));
    }
  }
  return { opened: load };
}
