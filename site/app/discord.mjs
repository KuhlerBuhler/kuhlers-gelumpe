/**
 * Discord: the project's server from Discord's widget API (who is online, the voice channels, the way in), drawn in
 * the page's own look instead of Discord's iframe. Without an answer the page keeps the link to the server.
 */
import { el } from "./fields.mjs";

const GUILD = "1563916590498447370";
const API = `https://discord.com/api/guilds/${GUILD}/widget.json`;
/** The way in when the widget names no invite (Server settings -> Widget -> invite channel). */
const INVITE = "https://discord.gg/J8qjKHYmP6";
const STATUS = { online: "online", idle: "abwesend", dnd: "beschäftigt" };
const TONE = { online: "ok", idle: "warn", dnd: "error" };

const link = (href, text, className = "cee-text-link") => el("a", { className, href, target: "_blank", rel: "noopener noreferrer", textContent: text });

function member(m) {
  const avatar = el("img", { className: "cee-discord-avatar", src: m.avatar_url, alt: "", width: 32, height: 32, loading: "lazy" });
  const status = el("span", { className: "cee-status", textContent: STATUS[m.status] ?? m.status });
  status.setAttribute("data-tone", TONE[m.status] ?? "warn");
  return el("li", { className: "cee-discord-member" }, [
    avatar,
    el("span", { className: "cee-discord-name" }, [
      el("strong", { textContent: m.username }),
      m.game?.name ? el("span", { className: "muted", textContent: m.game.name }) : null,
    ]),
    status,
  ]);
}

/** The page from one answer of the widget API. */
export function serverView(w, invite = INVITE) {
  const join = w.instant_invite || invite;
  const members = [...(w.members ?? [])];
  const channels = [...(w.channels ?? [])].sort((a, b) => a.position - b.position);
  return [
    el("header", { className: "cee-discord-head" }, [
      el("h2", { textContent: w.name }),
      el("p", { className: "muted", textContent: `${w.presence_count ?? members.length} online. Hier kommen auch die Ankündigungen neuer Versionen an.` }),
      join ? el("div", { className: "actions" }, [link(join, "Server beitreten", "btn cee-primary")]) : null,
    ]),
    channels.length ? el("section", {}, [
      el("h3", { textContent: "Sprachkanäle" }),
      el("ul", { className: "cee-discord-channels" }, channels.map(c => el("li", { textContent: c.name }))),
    ]) : null,
    el("section", {}, [
      el("h3", { textContent: "Gerade online" }),
      members.length
        ? el("ul", { className: "cee-discord-members" }, members.map(member))
        : el("p", { className: "muted", textContent: "Gerade ist niemand online." }),
    ]),
  ];
}

/**
 * @param {HTMLElement} root the page
 * @returns {{ opened(): void }} loads the server when the page is opened, again at most once a minute
 */
export function discordPage(root, fetchImpl = globalThis.fetch) {
  const body = el("div", { className: "cee-discord", "aria-live": "polite" }, [el("p", { className: "muted", textContent: "Lade den Discord-Server..." })]);
  root.append(el("h1", { className: "ui-sr-only", textContent: "Discord" }), body);
  let loaded = 0;
  async function load() {
    if (Date.now() - loaded < 60000) return;
    loaded = Date.now();
    try {
      const res = await fetchImpl(API);
      if (!res.ok) throw new Error(String(res.status));
      body.replaceChildren(...serverView(await res.json()).filter(Boolean));
    } catch {
      loaded = 0;
      body.replaceChildren(el("p", {}, ["Der Discord-Server ist gerade nicht erreichbar. ",
        INVITE ? link(INVITE, "Hier geht es direkt hin") : "Versuch es gleich noch einmal", "."]));
    }
  }
  return { opened: load };
}
