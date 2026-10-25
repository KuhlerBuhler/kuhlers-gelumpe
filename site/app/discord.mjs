/**
 * Discord: the project's server from Discord's widget API, drawn in the page's own look instead of Discord's iframe.
 * Everyone online is a Blechy on the floor of the page: online ones walk to and fro, away ones stand, busy ones stand
 * with an angry face. The way in is the invite the widget names (Server settings -> Widget -> invite channel), so a
 * deleted invite never sticks in the app.
 */
import { el } from "./fields.mjs";
import { maskOf } from "./support.mjs";
import { outlined } from "../../src/blechy-outline.mjs";
import { reducedMotion } from "./settings.mjs";

const GUILD = "1563916590498447370";
const API = `https://discord.com/api/guilds/${GUILD}/widget.json`;
const STATUS = { online: "online", idle: "abwesend", dnd: "beschäftigt" };
const TONE = { online: "ok", idle: "warn", dnd: "error" };
/** The pictures of a Blechy: walking swaps idle and walk like his walk on the display. */
const POSES = { idle: "img/blechy/idle.png", walk: "img/blechy/walk.png", angry: "img/blechy/angry.png", sad: "img/blechy/sad.png" };
const POSE_OF = { online: "idle", idle: "sad", dnd: "angry" };
const SCALE = 2;
/** Pixels per second and the time per step, about his pace on the display. */
const SPEED = 40;
const STEP_MS = 240;

const link = (href, text, className = "cee-text-link") => el("a", { className, href, target: "_blank", rel: "noopener noreferrer", textContent: text });

let poses;
const loadPoses = () => (poses ??= Promise.all(Object.entries(POSES).map(async ([id, src]) => [id, outlined(await maskOf(src))]))
  .then(Object.fromEntries)
  .catch(() => (poses = null)));

function paint(canvas, mask, ink) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = ink;
  mask.forEach((row, y) => row.forEach((set, x) => { if (set) ctx.fillRect(x * SCALE, canvas.height - (mask.length - y) * SCALE, SCALE, SCALE); }));
}

/** One member as a Blechy with the name above him; `walks` tells the floor whether he moves. */
function blechy(m) {
  const status = STATUS[m.status] ?? m.status;
  const canvas = el("canvas", { className: "cee-discord-blechy-art", width: 56 * SCALE, height: 56 * SCALE });
  const dot = el("span", { className: "cee-discord-dot" });
  dot.setAttribute("data-tone", TONE[m.status] ?? "warn");
  const node = el("li", { className: "cee-discord-blechy" }, [
    el("span", { className: "cee-discord-tag" }, [
      m.avatar_url ? el("img", { className: "cee-discord-avatar", src: m.avatar_url, alt: "", width: 20, height: 20, loading: "lazy" }) : null,
      el("strong", { textContent: m.username }),
      dot,
    ]),
    m.game?.name ? el("span", { className: "cee-discord-game muted", textContent: m.game.name }) : null,
    canvas,
  ].filter(Boolean));
  node.setAttribute("aria-label", `${m.username}, ${status}${m.game?.name ? `, ${m.game.name}` : ""}`);
  return { node, canvas, pose: POSE_OF[m.status] ?? "idle", walks: m.status === "online", x: 0, dir: 1, step: 0 };
}

/**
 * The floor with everyone online. Returns the element and `start()`, which runs the walk; on another tab the frames
 * only check and skip, and the walk ends when a new answer replaces the floor.
 */
function floor(members) {
  const figures = members.map(blechy);
  const list = el("ul", { className: "cee-discord-floor", "aria-label": "Gerade online" }, figures.map(f => f.node));
  let running = false;
  async function start() {
    const art = await loadPoses();
    if (!art || running) return;
    const ink = getComputedStyle(list).color;
    const width = list.clientWidth;
    figures.forEach((f, i) => {
      f.x = ((i + 0.5) / figures.length) * Math.max(0, width - f.node.offsetWidth);
      f.dir = i % 2 ? -1 : 1;
      paint(f.canvas, art[f.pose], ink);
      f.node.style.transform = `translateX(${f.x}px)`;
    });
    if (reducedMotion()) return;
    running = true;
    let last = performance.now();
    const tick = now => {
      if (!list.isConnected) { running = false; return; }
      const dt = Math.min(now - last, 100) / 1000;
      last = now;
      if (list.offsetParent === null) return requestAnimationFrame(tick);
      const room = list.clientWidth;
      for (const f of figures.filter(g => g.walks)) {
        const max = Math.max(0, room - f.node.offsetWidth);
        f.x += f.dir * SPEED * dt;
        if (f.x <= 0 || f.x >= max) { f.x = Math.min(Math.max(f.x, 0), max); f.dir = -f.dir; }
        const step = Math.floor(now / STEP_MS) % 2;
        if (step !== f.step) { f.step = step; paint(f.canvas, art[step ? "walk" : f.pose], ink); }
        f.node.style.transform = `translateX(${f.x}px)`;
        f.canvas.style.transform = f.dir < 0 ? "scaleX(-1)" : "";
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
      el("p", { className: "muted", textContent: `${w.presence_count ?? members.length} online. Hier kommen auch die Ankündigungen neuer Versionen an.` }),
      join ? el("div", { className: "actions" }, [link(join, "Server beitreten", "btn cee-primary")]) : null,
    ]),
    el("section", {}, [
      el("h3", { textContent: "Gerade online" }),
      room ? room.list : el("p", { className: "muted", textContent: "Gerade ist niemand online." }),
    ]),
    channels.length ? el("section", {}, [
      el("h3", { textContent: "Sprachkanäle" }),
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
  const body = el("div", { className: "cee-discord", "aria-live": "polite" }, [el("p", { className: "muted", textContent: "Lade den Discord-Server..." })]);
  root.append(el("h1", { className: "ui-sr-only", textContent: "Discord" }), body);
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
      body.replaceChildren(el("p", { textContent: "Der Discord-Server ist gerade nicht erreichbar. Versuch es gleich noch einmal." }));
    }
  }
  return { opened: load };
}
