/**
 * Discord: the project's server from Discord's widget API, drawn in the page's own look instead of Discord's iframe.
 * Everyone online is a Blechy on the floor of the page: online ones walk to and fro and now and then stop for his dance
 * from the device, away ones stand, busy ones stand with an angry face. The Blechys are solid, so on a full server the
 * front ones cover those behind instead of piling up, and the list of names below the floor keeps everyone readable.
 * While the page is open the server is asked again every minute: newcomers walk in from a side, those gone walk out. The way in is the invite the widget names (Server settings ->
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
/**
 * One eighth at 120 BPM. Each Blechy keeps his own time: his steps and dance frames run on his own phase, a dance
 * lasts one to three bars and between two dances he walks for 10 to 40 s, so they seldom dance together.
 */
const EIGHTH_MS = 250;
const danceFor = () => (8 + Math.floor(Math.random() * 17)) * EIGHTH_MS;
const walkFor = () => 10000 + Math.random() * 30000;
/** How often the open page asks the server again. */
const REFRESH_MS = 60000;
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
  node.dataset.id = String(m.id);
  return {
    node, canvas, status: m.status, pose: POSE_OF[m.status] ?? "idle", walks: m.status === "online", x: 0, dir: 1, move: "",
    speed: SPEED * (0.75 + Math.random() * 0.5), phase: Math.random() * 8 * EIGHTH_MS, shown: "", dancing: false,
    until: performance.now() + 2000 + Math.random() * 25000,
  };
}

/** Everyone online as names, the first LISTED of them until the button shows the rest; `update` takes a new answer. */
function people() {
  const list = el("ul", { className: "cee-discord-people" });
  list.setAttribute("aria-label", t("discord.online"));
  const more = el("button", { type: "button", className: "cee-text-link cee-discord-more" });
  let open = false;
  let shown = [];
  function update(members) {
    shown = members;
    list.replaceChildren(...members.map((m, i) => {
      const status = STATUS[m.status] ? t(STATUS[m.status]) : m.status;
      const item = el("li", {}, [tag(m)]);
      item.setAttribute("aria-label", `${m.username}, ${status}${m.game?.name ? `, ${m.game.name}` : ""}`);
      item.hidden = !open && i >= LISTED;
      return item;
    }));
    more.hidden = open || members.length <= LISTED;
    more.textContent = t("discord.more", { count: Math.max(0, members.length - LISTED) });
  }
  more.onclick = () => { open = true; update(shown); };
  return { nodes: [list, more], update };
}

/**
 * The floor with everyone online, in ROWS rows, the front row lowest and on top. Returns the element, `start()`, which
 * runs the walk in one animation loop for all of them (now and then each one stops and dances; on another tab the
 * frames only check and skip, and the walk ends when the page is replaced), and `update()`, which takes a new answer:
 * whoever stays keeps his place, newcomers walk in from a side and those gone walk out.
 */
function floor() {
  const list = el("ul", { className: "cee-discord-floor" });
  list.setAttribute("aria-hidden", "true");
  const figures = new Map();
  let rows = 0;
  let art = null;
  let running = false;
  let room = -1;
  const max = () => Math.max(0, room - WIDTH);
  const flip = f => { f.canvas.style.transform = (f.walks || f.move) && !f.dancing && f.dir < 0 ? "scaleX(-1)" : ""; };
  const mark = f => { f.node.dataset.move = f.move || (f.dancing ? "dance" : "walk"); };
  function show(f, pose) {
    if (art && f.shown !== pose) { f.shown = pose; paint(f.canvas, art[pose]); }
  }
  function enter(m) {
    const f = blechy(m);
    f.node.dataset.row = String(rows++ % ROWS);
    figures.set(f.node.dataset.id, f);
    list.append(f.node);
    if (running) {
      f.dir = Math.random() < 0.5 ? 1 : -1;
      f.x = f.dir > 0 ? -WIDTH : room;
      f.move = "enter";
    } else if (room >= 0) {
      f.x = Math.random() * max();
    }
    f.node.style.transform = `translateX(${f.x}px)`;
    mark(f);
    flip(f);
    show(f, f.move ? "walk" : f.pose);
  }
  function leave(f) {
    if (!running) {
      f.node.remove();
      figures.delete(f.node.dataset.id);
      return;
    }
    f.move = "leave";
    f.dancing = false;
    f.dir = f.x < max() / 2 ? -1 : 1;
    mark(f);
    flip(f);
  }
  function update(members) {
    const ids = new Set(members.map(m => String(m.id)));
    for (const f of figures.values()) if (!ids.has(f.node.dataset.id) && f.move !== "leave") leave(f);
    for (const m of members) {
      const f = figures.get(String(m.id));
      if (!f || f.move === "leave") {
        if (f) { f.node.remove(); figures.delete(f.node.dataset.id); }
        enter(m);
        continue;
      }
      f.node.replaceChild(tag(m), f.node.firstChild);
      if (f.status === m.status) continue;
      f.status = m.status;
      f.pose = POSE_OF[m.status] ?? "idle";
      f.walks = m.status === "online";
      if (!f.walks) f.dancing = false;
      mark(f);
      flip(f);
      show(f, f.pose);
    }
  }
  async function start() {
    const loaded = await loadPoses();
    if (!loaded || running) return;
    const ink = getComputedStyle(list).color;
    const fill = getComputedStyle(list).getPropertyValue("--color-bg-page").trim();
    art ??= Object.fromEntries(Object.entries(loaded).map(([id, pose]) => [id, sprite(pose, ink, fill)]));
    if (room < 0) {
      room = list.clientWidth;
      [...figures.values()].forEach((f, i, all) => {
        f.x = ((i + 0.5) / all.length) * max();
        f.dir = i % 2 ? -1 : 1;
        f.node.style.transform = `translateX(${f.x}px)`;
      });
    }
    for (const f of figures.values()) { flip(f); show(f, f.pose); }
    if (reducedMotion()) return;
    running = true;
    let last = performance.now();
    const tick = now => {
      if (!list.isConnected) { running = false; return; }
      const dt = Math.min(now - last, 100) / 1000;
      last = now;
      if (list.offsetParent === null) return requestAnimationFrame(tick);
      if (list.clientWidth !== room) {
        room = list.clientWidth;
        for (const f of figures.values()) if (!f.move) { f.x = Math.min(f.x, max()); f.node.style.transform = `translateX(${f.x}px)`; }
      }
      for (const f of figures.values()) {
        if (!f.move && !f.walks) continue;
        if (!f.move && now >= f.until) {
          f.dancing = !f.dancing;
          f.until = now + (f.dancing ? danceFor() : walkFor());
          mark(f);
          flip(f);
        }
        if (f.dancing) { show(f, `dance${DANCE[Math.floor((now + f.phase) / EIGHTH_MS) % DANCE.length]}`); continue; }
        f.x += f.dir * f.speed * dt;
        if (f.move === "leave") {
          if (f.x < -WIDTH || f.x > room) { f.node.remove(); figures.delete(f.node.dataset.id); continue; }
        } else if (f.move === "enter") {
          if (f.x >= 0 && f.x <= max()) {
            f.move = "";
            mark(f);
            flip(f);
            if (!f.walks) { show(f, f.pose); f.node.style.transform = `translateX(${f.x}px)`; continue; }
          }
        } else if (f.x <= 0 || f.x >= max()) {
          f.x = Math.min(Math.max(f.x, 0), max());
          f.dir = -f.dir;
          flip(f);
        }
        show(f, Math.floor((now + f.phase) / STEP_MS) % 2 ? "walk" : f.pose);
        f.node.style.transform = `translateX(${f.x}px)`;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
  return { list, start, update };
}

/** The page from one answer of the widget API: the elements, the floor's start, and `update` for a later answer. */
export function serverView(w) {
  const join = w.instant_invite;
  const count = el("p", { className: "muted" });
  const nobody = el("p", { className: "muted", textContent: t("discord.nobody") });
  const room = floor();
  const names = people();
  function update(w) {
    const members = [...(w.members ?? [])];
    count.textContent = t("discord.count", { count: w.presence_count ?? members.length });
    nobody.hidden = members.length > 0;
    room.list.hidden = !members.length;
    room.update(members);
    names.update(members);
  }
  update(w);
  const nodes = [
    el("header", { className: "cee-discord-head" }, [
      el("h2", { textContent: w.name }),
      count,
      join ? el("div", { className: "actions" }, [link(join, t("discord.join"), "btn cee-primary")]) : null,
    ]),
    el("section", {}, [el("h3", { textContent: t("discord.online") }), room.list, ...names.nodes, nobody]),
  ].filter(Boolean);
  return { nodes, start: room.start, update };
}

/**
 * @param {HTMLElement} root the page
 * @returns {{ opened(): void }} loads the server when the page is opened and again every minute while it is open and the
 * window is in view; a later answer updates the page in place
 */
export function discordPage(root, fetchImpl = globalThis.fetch) {
  const body = el("div", { className: "cee-discord", "aria-live": "polite" }, [el("p", { className: "muted", textContent: t("discord.loading") })]);
  root.append(el("h1", { className: "ui-sr-only", textContent: t("nav.discord") }), body);
  let loaded = 0;
  let view = null;
  let timer = 0;
  async function load() {
    loaded = Date.now();
    try {
      const res = await fetchImpl(API);
      if (!res.ok) throw new Error(String(res.status));
      const w = await res.json();
      if (view) return view.update(w);
      view = serverView(w);
      // The list changes every minute; only the first answer, or the failure, is read out.
      body.removeAttribute("aria-live");
      body.replaceChildren(...view.nodes);
      view.start();
    } catch {
      loaded = 0;
      if (view) return;
      body.setAttribute("aria-live", "polite");
      body.replaceChildren(el("p", { textContent: t("discord.offline") }));
    }
  }
  // One timer for the page: it asks again while the page is open and the window in view, and stops once the page is
  // left; opening it again starts it anew.
  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      if (!body.isConnected || body.offsetParent === null) { timer = 0; return; }
      if (!document.hidden) await load();
      schedule();
    }, REFRESH_MS);
  }
  async function opened() {
    if (Date.now() - loaded >= REFRESH_MS) await load();
    else view?.start();
    if (!timer) schedule();
  }
  return { opened };
}
