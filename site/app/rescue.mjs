/**
 * The Rettung page: Blechy asks what the device shows and walks through the documented way back, one question at a
 * time, with the answers as buttons. What is only to read follows by itself after a second; Blechy waits only where
 * the person has to do or answer something. Content: data/rescue.mjs.
 */
import { el } from "./fields.mjs";
import { FLOW, LINKS, BUTTONS, FOLDERS } from "../../data/rescue.mjs";
import { e2Outline } from "./e2-art.mjs";
import { t, tNodes } from "./i18n.mjs";

/** The pause before Blechy's next message when the one before only had something to read. */
const PAUSE_MS = 1000;
/** How long a read of the app's own data may take before Blechy asks instead. */
const READ_MS = 4000;

const MOODS = { idle: "img/blechy/idle.png", happy: "img/blechy/happy.png", angry: "img/blechy/angry.png", wave: "img/blechy/wave.png", sad: "img/blechy/sad.png" };

const link = (href, text) => el("a", { className: "cee-text-link", href, ...(href.startsWith("#") ? {} : { target: "_blank", rel: "noopener noreferrer" }), textContent: text });

/** A link part { link, text }: a link to LINKS[link] with the text of that key; "issueNew" opens a new issue with `issue` filled in. */
const linkTo = (part, issue) => link(part.link === "issueNew" ? `${LINKS.issues}/new?${new URLSearchParams(issue)}` : LINKS[part.link], t(part.text));

/** A line of text: a key, a list of link parts, or { key, vars, links } where `{name}` in the text is the link `links.name`. */
const words = (line, issue = {}) => {
  if (Array.isArray(line)) return line.map(part => linkTo(part, issue));
  if (typeof line === "string") return [t(line)];
  const links = Object.fromEntries(Object.entries(line.links ?? {}).map(([name, part]) => [name, linkTo(part, issue)]));
  return tNodes(line.key, { ...line.vars, ...links });
};

const lines = (list, issue) => list.map(line => (line.path ? el("code", { className: "cee-rescue-path", textContent: line.path }) : el("p", {}, words(line, issue))));

/** What Blechy says in one node: the lines, a path on the card, what the app knows, and the official guide if there is one. */
const say = (node, issue, known) => [
  ...lines(node.say, issue),
  ...(known?.say ? lines(known.say, issue) : []),
  node.source ? el("p", { className: "cee-rescue-source" }, tNodes("rescue.source", { source: words(node.source) })) : null,
];

/** The Electribe of an answer as lines, like on the Features page, in the colour of its body. */
const art = c => {
  const svg = e2Outline(t(c.label));
  svg.dataset.device = c.art;
  return svg;
};

/**
 * What the app knows already, by the `known` of a node: what Blechy says about it and the value of the answer it fits.
 * Only what the app has read from the device or built itself; nothing is guessed.
 */
const KNOWN = {
  async hardware(context) {
    const colour = await context.hardware?.();
    if (colour !== "red" && colour !== "blue") return null;
    return { say: [colour === "blue" ? "rescue.known.blue" : "rescue.known.red"], value: colour };
  },
  async firmware(context) {
    return await context.firmware?.() === "blech" ? { say: ["rescue.known.blech"], value: FOLDERS.at(-1).path } : null;
  },
  /** The firmware that runs, else the folder the patcher named for its last copy. */
  async folder(context) {
    const running = await KNOWN.firmware(context);
    if (running) return running;
    const target = context.target?.();
    if (!target) return null;
    const path = `${target}SYSTEM.VSB`;
    return { say: ["rescue.known.target", { path }], value: FOLDERS.some(f => f.path === path) ? path : null };
  },
};

const within = (promise, ms) => Promise.race([promise, new Promise(resolve => setTimeout(() => resolve(null), ms))]);

/**
 * `context`: what the app knows, each optional. hardware() "red"/"blue" of the connected Electribe, firmware() "blech"
 * when a running BLECHTRIBE answers, target() the card folder of the patcher's last copy, read.midi() and read.version()
 * the result a `read` node goes on with.
 */
export function rescuePage(root, context = {}) {
  const nodes = FLOW;
  const chat = el("ol", { className: "cee-rescue-chat", id: "cee-rescue-chat", "aria-live": "polite" });
  const answers = el("div", { className: "cee-rescue-answers", id: "cee-rescue-answers" });
  const back = el("button", { type: "button", className: "btn sm", id: "cee-rescue-back", textContent: t(BUTTONS.back) });
  const again = el("button", { type: "button", className: "btn sm", id: "cee-rescue-again", textContent: t(BUTTONS.again) });
  let path = ["start"];
  let picked = [];
  let timer = null;
  // What the app knew at each step, by its place in the path, so going back and on asks again.
  let known = [];

  const blechy = (mood, parts) => el("li", { className: "cee-rescue-say" }, [
    el("img", { className: "cee-rescue-blechy", src: MOODS[mood], alt: "", width: 45, height: 55 }),
    el("div", { className: "cee-rescue-bubble" }, parts.filter(Boolean)),
  ]);
  const you = label => el("li", { className: "cee-rescue-you" }, [el("p", { className: "cee-rescue-bubble", textContent: t(label) })]);

  /** A new issue that already says which way through the page the person took. */
  const issue = () => ({
    title: t("rescue.issue.title", { answer: picked[0] ? t(picked[0]) : "" }),
    body: t("rescue.issue.body", { answers: picked.filter(Boolean).map(p => `- ${t(p)}`).join("\n") }),
  });

  /** Asks the app what it knows for the node at `at`, once, and shows it when the path is still there. */
  function learn(at, node) {
    if (!node.known || known[at] !== undefined) return;
    known[at] = null;
    const was = path;
    within(KNOWN[node.known](context).catch(() => null), READ_MS).then(found => {
      if (path !== was || !found) return;
      known[at] = found;
      render();
    });
  }

  /** The node a `read` goes on to: what the app reads, or `otherwise`. */
  async function follow(node) {
    let result = null;
    try { result = await within(Promise.resolve(context.read?.[node.read.from]?.()), READ_MS); } catch { result = null; }
    return node.read.to[result] ?? node.read.otherwise;
  }

  function render() {
    chat.replaceChildren(...path.flatMap((id, i) => [blechy(nodes[id].mood, say(nodes[id], issue(), known[i])), picked[i] ? you(picked[i]) : null].filter(Boolean)));
    const at = path.length - 1;
    const node = nodes[path[at]];
    const fits = known[at]?.value;
    const choices = node.choices ?? [];
    answers.replaceChildren(...choices.map(c => {
      const mark = fits != null && c.value === fits;
      const b = el("button", { type: "button", className: `btn${c.art ? " cee-rescue-folder" : ""}`, onclick: () => choose(c) }, [
        c.art ? art(c) : null,
        el("span", { className: "cee-rescue-answer", textContent: t(c.label) }),
        c.hint ? el("span", { className: "cee-rescue-hint", textContent: t(c.hint) }) : null,
        mark ? el("span", { className: "cee-rescue-hint cee-rescue-known", textContent: t("rescue.known.pick") }) : null,
      ]);
      if (c.id) b.id = `cee-rescue-case-${c.id}`;
      if (mark) b.dataset.known = "";
      return b;
    }));
    answers.hidden = !choices.length;
    back.disabled = path.length < 2;
    chat.lastElementChild?.scrollIntoView?.({ block: "nearest" });
    clearTimeout(timer);
    learn(at, node);
    // While Blechy still has something to say, the answers wait and tests can tell (data-waiting).
    answers.toggleAttribute("data-waiting", !!(node.next || node.read));
    const was = path;
    if (node.next) timer = setTimeout(() => { path = [...path, node.next]; render(); }, PAUSE_MS);
    else if (node.read) timer = setTimeout(async () => {
      const to = await follow(node);
      if (path !== was) return;
      path = [...path, to];
      render();
    }, PAUSE_MS);
  }
  function choose(c) {
    // the key: the answers read in the language of the moment, also in the issue
    picked[path.length - 1] = c.label;
    path = [...path, c.to];
    render();
    answers.querySelector("button")?.focus({ preventScroll: true });
  }
  back.addEventListener("click", () => {
    if (path.length < 2) return;
    // Back to the last question, past what Blechy said by himself.
    do path = path.slice(0, -1); while (path.length > 1 && (nodes[path.at(-1)].next || nodes[path.at(-1)].read));
    picked = picked.slice(0, path.length - 1);
    known = known.slice(0, path.length - 1);
    render();
  });
  again.addEventListener("click", () => { path = ["start"]; picked = []; known = []; render(); });

  root.replaceChildren(el("div", { className: "cee-rescue" }, [
    el("h1", { className: "cee-rescue-title ui-sr-only", textContent: t("nav.rescue") }),
    chat,
    answers,
    el("div", { className: "actions cee-rescue-nav" }, [back, again]),
  ]));
  render();
}
