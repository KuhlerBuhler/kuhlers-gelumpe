/**
 * The Blechy page (#rescue): Blechy asks what the device shows and walks through the documented way back, one question
 * at a time, with the answers as buttons; the first answer is typed, and the cases that fit come up above the field. What is only to read follows by itself after a second; Blechy waits only where
 * the person has to do or answer something. Content: data/rescue.mjs.
 */
import { el } from "./fields.mjs";
import { dropzoneClear } from "./dropzone-clear.mjs";
import { FLOW, LINKS, BUTTONS, FOLDERS, CASES, FIRST_CASES, MAX_SHOWN, destOf, passSteps } from "../../data/rescue.mjs";
import { makeMatcher, casePhrases } from "../../src/blechy-match.mjs";
import { checkName, korgBlueForSampler } from "../../src/patcher.mjs";
import { saveFile } from "./save-file.mjs";
import { toast } from "./toast.mjs";
import { e2Outline, e2Keys } from "./e2-art.mjs";
import { t, tNodes, locale, language } from "./i18n.mjs";
import { pickCard } from "./card-access.mjs";
import { identify, planCard, applyPlan } from "../../src/card-check.mjs";
import { VSB_SIZE } from "../../src/patcher.mjs";

/** The pause before Blechy's next message when the one before only had something to read. */
const PAUSE_MS = 1000;
/** How long a read of the app's own data may take before Blechy asks instead. */
const READ_MS = 4000;

const MOODS = { idle: "img/blechy/idle.png", happy: "img/blechy/happy.png", angry: "img/blechy/angry.png", wave: "img/blechy/wave.png", sad: "img/blechy/sad.png" };

const link = (href, text) => el("a", { className: "cee-text-link", href, ...(href.startsWith("#") ? {} : { target: "_blank", rel: "noopener noreferrer" }), textContent: text });

/** A link part { link, text }: a link to LINKS[link] with the text of that key; "issueNew" opens a new issue with `issue` filled in. */
const linkTo = (part, issue) => link(part.link === "issueNew" ? `${LINKS.issues}/new?${new URLSearchParams(issue)}` : LINKS[part.link], t(part.text));

/**
 * A line of text: a key, a list of link parts, or { key, vars, links, code } where `{name}` in the text is the link
 * `links.name`, or `code.name` as a path on the card.
 */
const words = (line, issue = {}) => {
  if (Array.isArray(line)) return line.map(part => linkTo(part, issue));
  if (typeof line === "string") return [t(line)];
  const links = Object.fromEntries(Object.entries(line.links ?? {}).map(([name, part]) => [name, linkTo(part, issue)]));
  const code = Object.fromEntries(Object.entries(line.code ?? {}).map(([name, path]) => [name, el("code", { className: "cee-rescue-path", textContent: path })]));
  return tNodes(line.key, { ...line.vars, ...links, ...code });
};

/** A path as code that wraps only at the slashes, so a name never breaks in the middle. */
const pathCode = path => el("code", { className: "cee-rescue-path" }, path.split("/").flatMap((part, i) => (i ? ["/", el("wbr"), part] : [part])));

/** A path on the card as the folders to open, one inside the other, with the plain path under it to copy. */
function folderTree(path) {
  const names = path.split("/");
  const root = el("ul", { className: "cee-rescue-tree" });
  let list = root;
  names.forEach((name, i) => {
    const item = el("li", { className: i === names.length - 1 ? "cee-rescue-leaf" : "cee-rescue-dir" }, [el("span", { textContent: name })]);
    list.append(item);
    if (i < names.length - 1) item.append(list = el("ul"));
  });
  return el("div", { className: "cee-rescue-treebox" }, [root, pathCode(path)]);
}

/** The keys a step presses, drawn on the device: `press` filled, `near` outlined, with a line under the drawing. */
const KEY_ART = {
  enter: { press: ["menu"], caption: ["rescue.keys.enter"] },
  menu: { press: ["menu"], near: ["editLeft", "editRight"], caption: ["rescue.keys.menu", "rescue.keys.legend"] },
};
const keysFigure = name => {
  const { caption, ...keys } = KEY_ART[name];
  return el("figure", { className: "cee-rescue-figure cee-rescue-keys" }, [e2Keys(t("rescue.keys.alt"), keys), el("figcaption", { textContent: caption.map(k => t(k)).join(" ") })]);
};

/** A picture of a page outside the app, as it looked when it was taken, with what to click on it. */
const shotFigure = src => el("figure", { className: "cee-rescue-figure cee-rescue-shot" }, [
  el("img", { src, alt: t("rescue.shot.alt"), width: 1200, height: 345, loading: "lazy", decoding: "async" }),
  el("figcaption", { textContent: t("rescue.shot.caption") }),
]);

/** `quote` is the error the app reported, for a { quote: true } line; without one that line is left out. */
const lines = (list, issue, quote) => list.map(line => (line.path ? pathCode(line.path)
  : line.tree ? folderTree(line.tree)
  : line.keys ? keysFigure(line.keys)
  : line.shot ? shotFigure(line.shot)
  : line.quote ? (quote ? el("blockquote", { className: "cee-rescue-quote", id: "cee-rescue-quote", textContent: quote }) : null)
    : el("p", {}, words(line, issue))));

/** What Blechy says in one node: the lines, a path on the card, what the app knows, and the official guide if there is one. */
const say = (node, issue, known, quote) => [
  ...lines(node.say, issue, quote),
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
    // a blue running Hacktribe may report itself as red (docs/rettung.md), so only a blue is taken without asking
    return { say: [colour === "blue" ? "rescue.known.blue" : "rescue.known.red"], value: colour, auto: colour === "blue" };
  },
  /** The firmware that runs, else the folder the patcher named for its last copy (a hint, the person still answers). */
  async firmware(context) {
    if (await context.firmware?.() === "blech") return { say: ["rescue.known.blech"], value: "blech", auto: true };
    const target = context.target?.();
    if (!target) return null;
    const path = `${target}SYSTEM.VSB`;
    const folder = FOLDERS.find(f => f.path === path);
    return { say: ["rescue.known.target", { path }], value: !folder ? null : folder.path === FOLDERS[2].path ? "hacktribe" : folder.path === FOLDERS[3].path ? "blech" : "korg" };
  },
  /** The last red test of the patcher (testFailure in data/rescue.mjs): its check in words and its group. */
  async test(context) {
    const failure = context.test?.();
    if (!failure?.group) return null;
    const check = failure.area ? t(failure.area) : failure.id ? t(checkName(failure.id)) : null;
    return { say: [check ? { key: "rescue.known.test", vars: { check } } : failure.group === "patch" ? "rescue.known.testPatch" : "rescue.known.testRun"], value: failure.group };
  },
};

/** The file steps of a node (`file`): the user's own file in, the file for the card out. */
const FILES = {
  korgBlueHead: async bytes => {
    const res = await korgBlueForSampler(bytes);
    if (!res.ok) { toast(t(res.why === "size" ? "rescue.file.size" : "rescue.file.notKorgBlue"), "error"); return false; }
    saveFile(res.bytes, "SYSTEM.VSB", { note: t("rescue.file.saved") });
    return true;
  },
};

/** The matcher, made again when the language changes so the texts as shown count too. */
let matcher = null;
const matchCases = query => {
  if (matcher?.lang !== language()) {
    matcher = { lang: language(), match: makeMatcher(casePhrases(Object.fromEntries(CASES.map(c => [c.id, [t(c.label), t(c.hint)]])))) };
  }
  return matcher.match(query, { limit: 5 }).map(r => r.id);
};

const within = (promise, ms) => Promise.race([promise, new Promise(resolve => setTimeout(() => resolve(null), ms))]);

/** The event an error toast sends to open the page at Blechy with that error (site/app/toast.mjs). */
export const RESCUE_EVENT = "cee-rescue";

/** What Blechy says about one file on the card: what it is, then what is wrong with it for the place. */
const WHAT = { stock: "rescue.card.what.stock", synth: "rescue.card.what.synth", hacktribe: "rescue.card.what.hacktribe", hacktribeBlue: "rescue.card.what.hacktribeBlue" };
const PROBLEM = { unknown: "rescue.card.problem.unknown", other: "rescue.card.problem.other", folder: "rescue.card.problem.folder", name: "rescue.card.problem.name", case: "rescue.card.problem.case" };
function fileLines(f) {
  const what = f.known ? WHAT[f.known] : f.head ? "rescue.card.what.patched" : null;
  const said = f.problems.map(p => (p === "size"
    ? { key: "rescue.card.problem.size", vars: { size: f.size.toLocaleString(locale()), expected: VSB_SIZE.toLocaleString(locale()) } }
    : PROBLEM[p]));
  return [{ path: f.path }, ...(what ? [what] : []), ...(said.length ? said : ["rescue.card.problem.none"])];
}

const STEP = { aside: "rescue.card.step.aside", move: "rescue.card.step.move", rename: "rescue.card.step.rename" };
const stepLine = s => ({ key: STEP[s.op], code: { from: s.from, to: s.to } });

/**
 * `context`: what the app knows, each optional. hardware() "red"/"blue" of the connected Electribe, firmware() "blech"
 * when a running BLECHTRIBE answers, target() the card folder of the patcher's last copy, test() the patcher's last red
 * test ({ group, id, area }), read.midi() and read.version() the result a `read` node goes on with.
 * An RESCUE_EVENT on window with { message, to } starts the conversation anew at the node `error`: Blechy quotes the
 * message and goes on with the node `to` (a node of FLOW, else the question what in the app sticks).
 */
export function rescuePage(root, context = {}) {
  // the nodes of the flow, and those Blechy makes while he looks at a card (`card#n:...`)
  let extra = {};
  let looks = 0;
  let picking = false;
  const nodes = new Proxy(FLOW, { get: (flow, id) => flow[id] ?? extra[id] });
  const chat = el("ol", { className: "cee-rescue-chat", id: "cee-rescue-chat", "aria-live": "polite" });
  const answers = el("div", { className: "cee-rescue-answers", id: "cee-rescue-answers" });
  const back = el("button", { type: "button", className: "btn sm", id: "cee-rescue-back", textContent: t(BUTTONS.back) });
  const again = el("button", { type: "button", className: "btn sm", id: "cee-rescue-again", textContent: t(BUTTONS.again) });
  const nav = el("div", { className: "actions cee-rescue-nav", id: "cee-rescue-nav" }, [back, again]);
  const input = el("input", { type: "file", id: "cee-rescue-input", className: "ui-dropzone-input", accept: ".VSB,.vsb" });
  const fileInfo = el("span", { className: "ui-dropzone-files", id: "cee-rescue-file-info" });
  let path = ["start"];
  let picked = [];
  let timer = null;
  // What the answers so far say (color, firmware, ...), by the step that gave it, so back takes an answer out again.
  let facts = {};
  let factsBy = [];
  // The answer a step had before back came to it, shown as the one that was chosen, and the steps the app may not answer alone.
  let previous = {};
  let noAuto = new Set();
  // What the app knew at each step, by its place in the path, so going back and on asks again.
  let known = [];
  // The error the app reported when it opened the page, quoted by the node `error`.
  let reported = null;

  const blechy = (mood, parts) => el("li", { className: "cee-rescue-say" }, [
    el("img", { className: "cee-rescue-blechy", src: MOODS[mood], alt: "", width: 45, height: 55 }),
    el("div", { className: "cee-rescue-bubble" }, parts.filter(Boolean)),
  ]);
  const you = label => el("li", { className: "cee-rescue-you" }, [el("p", { className: "cee-rescue-bubble", textContent: t(label) })]);

  /** A new issue that already says which way through the page the person took. */
  const issue = () => ({
    title: t("rescue.issue.title", { answer: picked[0] ? t(picked[0]) : reported ?? "" }),
    body: t("rescue.issue.body", { answers: [...(reported ? [`- ${reported}`] : []), ...picked.filter(Boolean).map(p => `- ${t(p)}`)].join("\n") }),
  });

  /** Asks the app what it knows for the node at `at`, once, and shows it when the path is still there. */
  function learn(at, node) {
    if (!node.known || known[at] !== undefined) return;
    known[at] = null;
    const was = path;
    within(KNOWN[node.known](context).catch(() => null), READ_MS).then(found => {
      if (path !== was || !found) return;
      known[at] = found;
      // What the app knows answers the question about the file put on last: on to the folder question, which shows it.
      if (node.passTo) path = [...path.slice(0, -1), node.passTo];
      render();
      const now = path;
      const step = nodes[path[at]];
      // What the app was told by the device itself needs no question; back brings the question.
      const fits = found.auto && !noAuto.has(at) && facts[step.ask] == null && step.choices?.find(c => c.value === found.value);
      if (fits) timer = setTimeout(() => { if (path === now) choose(fits); }, PAUSE_MS);
    });
  }

  const dest = c => destOf(c, facts);

  /** A step that asks for a fact already known is passed on the answer that fits, so nothing is asked twice. */
  function skip() {
    const passed = passSteps(path.at(-1), facts, nodes);
    facts = passed.facts;
    // the path is replaced only when a step was passed: timers and reads compare it by identity
    if (passed.id !== path.at(-1)) path = [...path.slice(0, -1), passed.id];
  }

  /** The node a `read` goes on to: what the app reads, or `otherwise`. */
  async function follow(node) {
    let result = null;
    try { result = await within(Promise.resolve(context.read?.[node.read.from]?.()), READ_MS); } catch { result = null; }
    return node.read.to[result] ?? node.read.otherwise;
  }

  /** The file step: a drop zone like the patcher's, naming the file it takes; the node goes on at `node.done` once the file is made. */
  function dropZone(node, at) {
    const was = path;
    fileInfo.textContent = "";
    const zone = el("label", { className: "ui-dropzone cee-rescue-drop", id: "cee-rescue-drop" }, [
      input,
      el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: t("rescue.drop.drag") }), t("common.pick")]),
      el("span", { className: "ui-dropzone-hint", textContent: t("rescue.drop.hint") }),
      fileInfo,
    ]);
    const wrapped = dropzoneClear(input).node;
    input.onchange = async () => {
      const file = input.files?.[0];
      input.value = "";
      if (!file || path !== was) return;
      zone.removeAttribute("data-invalid");
      fileInfo.textContent = file.name;
      if (!await FILES[node.file](new Uint8Array(await file.arrayBuffer()))) {
        zone.setAttribute("data-invalid", "");
        return;
      }
      if (path !== was) return;
      picked[at] = "rescue.answer.fileGiven";
      factsBy[at] = facts;
      path = [...path, node.done];
      render();
    };
    return wrapped;
  }

  function render() {
    skip();
    chat.replaceChildren(...path.flatMap((id, i) => [blechy(nodes[id].mood, say(nodes[id], issue(), known[i], reported)), picked[i] ? you(picked[i]) : null].filter(Boolean)));
    const at = path.length - 1;
    const node = nodes[path[at]];
    // the file put on last marks what likely runs; what the app read itself comes first
    const last = node.ask === "firmware" && facts.last !== "unknown" ? facts.last : null;
    const fits = known[at]?.value ?? last;
    const choices = node.choices ?? [];
    const pick = node.file ? [dropZone(node, at)] : [];
    if (node.search) answers.replaceChildren(askBox(choices, at));
    else answers.replaceChildren(...pick, ...choices.map(c => {
      const mark = fits != null && c.value === fits;
      const chosenBefore = previous[at] != null && c.label === previous[at];
      if (c.pick) return pickBox(c);
      const b = el("button", { type: "button", className: `btn${c.art ? " cee-rescue-folder" : ""}`, onclick: () => choose(c) }, [
        c.art ? art(c) : null,
        el("span", { className: "cee-rescue-answer", textContent: t(c.label) }),
        c.hint ? el("span", { className: "cee-rescue-hint", textContent: t(c.hint) }) : null,
        mark ? el("span", { className: "cee-rescue-hint cee-rescue-known", textContent: t(known[at]?.value != null ? "rescue.known.pick" : "rescue.known.last") }) : null,
        chosenBefore ? el("span", { className: "cee-rescue-hint cee-rescue-known", textContent: t("rescue.known.before") }) : null,
      ]);
      if (c.id) b.id = `cee-rescue-case-${c.id}`;
      if (mark) b.dataset.known = "";
      if (chosenBefore) b.dataset.before = "";
      return b;
    }));
    answers.hidden = !choices.length && !pick.length;
    answers.classList.toggle("cee-rescue-answers-ask", !!node.search);
    back.disabled = path.length < 2;
    // On the start page there is nothing to go back to and nothing to start over.
    nav.hidden = path.length < 2;
    showNewest();
    clearTimeout(timer);
    learn(at, node);
    // While Blechy still has something to say, the answers wait and tests can tell (data-waiting).
    answers.toggleAttribute("data-waiting", !!(node.next || node.read || node.busy));
    const was = path;
    if (node.next) timer = setTimeout(() => { path = [...path, node.next]; render(); }, PAUSE_MS);
    else if (node.read) timer = setTimeout(async () => {
      const to = await follow(node);
      if (path !== was) return;
      path = [...path, to];
      render();
    }, PAUSE_MS);
  }
  /**
   * The first question as a message field: what is typed brings up the cases that fit above it, as a combobox with a
   * listbox (arrow keys move, Enter picks, Escape clears). Empty, it offers FIRST_CASES and the way to all of them; never more than MAX_SHOWN unless all are asked for.
   */
  function askBox(choices, at) {
    const byId = Object.fromEntries(choices.map(c => [c.id, c]));
    const field = el("input", {
      type: "text", className: "input cee-rescue-field", id: "cee-rescue-search", autocomplete: "off", spellcheck: false,
      placeholder: t("rescue.search.placeholder"), role: "combobox",
    });
    field.setAttribute("aria-autocomplete", "list");
    field.setAttribute("aria-controls", "cee-rescue-suggest");
    const list = el("ul", { className: "cee-rescue-suggest", id: "cee-rescue-suggest", role: "listbox" });
    list.setAttribute("aria-label", t("rescue.search.list"));
    const status = el("p", { className: "ui-sr-only", id: "cee-rescue-search-status", role: "status" });
    const none = el("p", { className: "cee-rescue-hint", id: "cee-rescue-search-none", textContent: t("rescue.search.none"), hidden: true });
    const all = el("button", { type: "button", className: "btn sm", id: "cee-rescue-search-all", textContent: t("rescue.search.all") });
    let shown = [];
    let active = -1;
    let everything = false;

    const mark = () => {
      [...list.children].forEach((li, i) => li.setAttribute("aria-selected", String(i === active)));
      if (active >= 0) {
        field.setAttribute("aria-activedescendant", list.children[active].id);
        list.children[active].scrollIntoView?.({ block: "nearest" });
      } else field.removeAttribute("aria-activedescendant");
    };
    const option = c => {
      const li = el("li", { className: "cee-rescue-option", id: `cee-rescue-case-${c.id}`, role: "option" }, [
        el("span", { className: "cee-rescue-answer", textContent: t(c.label) }),
        c.hint ? el("span", { className: "cee-rescue-hint", textContent: t(c.hint) }) : null,
        previous[at] === c.label ? el("span", { className: "cee-rescue-hint cee-rescue-known", textContent: t("rescue.known.before") }) : null,
      ]);
      if (previous[at] === c.label) li.dataset.before = "";
      // the field keeps the focus, so the list stays and a screen reader stays in the field
      li.addEventListener("mousedown", e => e.preventDefault());
      li.addEventListener("click", () => choose(c));
      return li;
    };
    function update() {
      const query = field.value.trim();
      if (query) everything = false;
      const before = previous[at] ? choices.find(c => c.label === previous[at])?.id : null;
      const ids = query ? matchCases(query) : everything ? choices.map(c => c.id) : [...new Set([before, ...FIRST_CASES].filter(Boolean))];
      shown = ids.map(id => byId[id]).filter(Boolean).slice(0, everything && !query ? Infinity : MAX_SHOWN);
      active = query && shown.length ? 0 : -1;
      list.replaceChildren(...shown.map(option));
      list.hidden = !shown.length;
      field.setAttribute("aria-expanded", String(shown.length > 0));
      none.hidden = !query || shown.length > 0;
      all.hidden = everything && !query;
      status.textContent = query ? (shown.length ? t("rescue.search.count", { count: shown.length }) : t("rescue.search.none")) : "";
      mark();
    }
    field.addEventListener("input", update);
    field.addEventListener("keydown", e => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        if (!shown.length) return;
        e.preventDefault();
        const step = e.key === "ArrowDown" ? 1 : -1;
        active = active < 0 ? (step > 0 ? 0 : shown.length - 1) : (active + step + shown.length) % shown.length;
        mark();
      } else if (e.key === "Enter") {
        const c = shown[active < 0 ? 0 : active];
        if (!c || (active < 0 && !field.value.trim())) return;
        e.preventDefault();
        choose(c);
      } else if (e.key === "Escape" && (field.value || active >= 0)) {
        e.preventDefault();
        field.value = "";
        update();
      }
    });
    all.addEventListener("click", () => {
      everything = true;
      field.value = "";
      update();
      field.focus({ preventScroll: true });
    });
    update();
    return el("div", { className: "cee-rescue-ask", id: "cee-rescue-ask" }, [
      list,
      none,
      el("label", { className: "ui-sr-only", htmlFor: "cee-rescue-search", textContent: t("rescue.search.label") }),
      field,
      el("div", { className: "cee-rescue-ask-more" }, [all]),
      status,
    ]);
  }

  /**
   * Scrolls down to Blechy's newest message and the answers under it, as far as both fit; the top of the message never goes
   * under the bar at the top (the page's scroll-padding). Smooth unless the person asked for less motion; never scrolls up.
   */
  function showNewest() {
    const newest = chat.lastElementChild;
    if (!newest?.getBoundingClientRect || !root.isConnected || !globalThis.scrollBy) return;
    const style = getComputedStyle(document.documentElement);
    const top = parseFloat(style.scrollPaddingTop) || 0;
    const gap = parseFloat(getComputedStyle(chat).rowGap) || 0;
    const end = (answers.hidden ? newest : answers).getBoundingClientRect().bottom + gap;
    const by = Math.min(end - innerHeight, newest.getBoundingClientRect().top - top);
    if (by <= 0) return;
    const calm = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    scrollBy({ top: by, behavior: calm ? "auto" : "smooth" });
  }
  /** The card step as a box of its own, so it does not read like one more answer; on a phone there is no card to pick. */
  function pickBox(c) {
    if (globalThis.matchMedia?.("(pointer: coarse)").matches) return el("p", { className: "cee-rescue-hint" }, t("rescue.card.phone"));
    const b = el("button", { type: "button", className: "cee-rescue-pickbox", onclick: () => choose(c) }, [
      el("span", { className: "ui-dropzone-title", textContent: t(c.label) }),
      c.hint ? el("span", { className: "ui-dropzone-hint", textContent: t(c.hint) }) : null,
    ]);
    if (c.id) b.id = `cee-rescue-case-${c.id}`;
    return b;
  }

  /** Goes on with Blechy's own node `node` under the id `id`. */
  function add(id, node) {
    extra[id] = node;
    path = [...path, id];
    render();
  }

  /**
   * Blechy's look at the card for `target` ({path, heads}), from the answer `c`: the person picks the card, Blechy lists
   * every .VSB on it with what is wrong, and offers the moves; the talk goes on at `c.to`. The dialog opens first, still
   * inside the click.
   */
  async function look(c, target, label = c.label) {
    const at = path.length - 1;
    const was = path;
    // one dialog at a time: a second click while it is open does nothing
    if (picking) return;
    picking = true;
    let card;
    try { card = await (context.pickCard ?? pickCard)(); } catch (e) { card = { error: e?.message ?? String(e) }; } finally { picking = false; }
    if (!card) { if (path === was) toast(t("rescue.card.cancelled"), "info"); return; }
    if (path !== was) return;
    picked[at] = label;
    const id = `card#${++looks}`;
    if (card.error) return add(`${id}:failed`, failed(c, target, card.error));
    add(`${id}:read`, { mood: "idle", say: [{ key: "rescue.card.reading", code: { name: card.name ?? "" } }], busy: true });
    const reading = path;
    let plan;
    try {
      // the folder of a running BLECH takes the head of its build: on a red that is only the Sampler's
      const colour = target.heads.length > 1 ? await within(Promise.resolve(context.hardware?.()).catch(() => null), READ_MS) : null;
      const heads = colour === "red" ? ["sampler"] : target.heads;
      const files = [];
      for (const entry of await card.list()) files.push(await identify(entry, card.read));
      plan = planCard(files, { path: target.path, heads });
    } catch (e) {
      plan = { error: e?.message ?? String(e) };
    }
    if (path !== reading) return;
    add(`${id}:report`, report(id, c, target, card, plan));
  }

  const pickAgain = (c, target) => ({ label: "rescue.answer.cardAgain", run: () => look(c, target, "rescue.answer.cardAgain") });
  const failed = (c, target, error) => ({ mood: "sad", say: [{ key: "rescue.card.failed", vars: { error } }], choices: [pickAgain(c, target), { label: "rescue.answer.onCard", to: dest(c) }] });

  function report(id, c, target, card, plan) {
    if (plan.error) return failed(c, target, plan.error);
    const found = plan.files.length ? ["rescue.card.found", ...plan.files.flatMap(fileLines)] : [];
    const to = dest(c);
    if (plan.verdict === "empty") return { mood: "idle", say: ["rescue.card.empty"], choices: [pickAgain(c, target), { label: "rescue.answer.onCard", to }] };
    if (plan.verdict === "wrong") return { mood: "sad", say: [...found, "rescue.card.none"], choices: [pickAgain(c, target), { label: "rescue.answer.onCard", to }] };
    if (plan.verdict === "ok") return { mood: "happy", say: [...found, "rescue.card.ok"], choices: [{ label: "rescue.answer.goOn", to }] };
    const steps = plan.steps.map(stepLine);
    if (!card.writable) return { mood: "idle", say: [...found, "rescue.card.readonly", ...steps], choices: [pickAgain(c, target), { label: "rescue.answer.onCard", to }] };
    return {
      mood: "idle",
      say: [...found, "rescue.card.plan", ...steps],
      choices: [{ label: "rescue.answer.fixCard", id: "card-fix", run: () => fix(id, c, target, card, plan) }, { label: "rescue.answer.fixSelf", to }],
    };
  }

  /** Runs the moves of the plan after the click, then says where everything is and goes on at `c.to`. */
  async function fix(id, c, target, card, plan) {
    picked[path.length - 1] = "rescue.answer.fixCard";
    add(`${id}:fixing`, { mood: "idle", say: ["rescue.card.fixing"], busy: true });
    const fixing = path;
    let done;
    try { done = await applyPlan(card, plan.steps); } catch (e) { done = { error: e?.message ?? String(e) }; }
    if (path !== fixing) return;
    if (done.error) return add(`${id}:failed`, failed(c, target, done.error));
    const aside = done.find(s => s.op === "aside");
    add(`${id}:done`, {
      mood: "happy",
      say: [
        "rescue.card.done", { path: target.path },
        ...(aside ? [{ key: "rescue.card.aside", code: { name: aside.to } }] : []),
        ...(done.some(s => s.how === "copied") ? ["rescue.card.copied"] : []),
        "rescue.card.eject",
      ],
      next: dest(c),
    });
  }

  function choose(c) {
    if (c.run) return c.run();
    if (c.pick) return look(c, nodes[path.at(-1)].card);
    const at = path.length - 1;
    // the key: the answers read in the language of the moment, also in the issue
    picked[at] = c.label;
    factsBy[at] = facts;
    delete previous[at];
    const to = dest(c);
    facts = { ...facts, ...c.set };
    path = [...path, to];
    render();
    answers.querySelector("#cee-rescue-search, button")?.focus({ preventScroll: true });
  }
  back.addEventListener("click", () => {
    if (path.length < 2) return;
    // Back to the last question, past what Blechy said by himself.
    do path = path.slice(0, -1); while (path.length > 1 && (nodes[path.at(-1)].next || nodes[path.at(-1)].read));
    const at = path.length - 1;
    previous = { [at]: picked[at] };
    picked = picked.slice(0, at);
    known = known.slice(0, at);
    facts = factsBy[at] ?? {};
    factsBy = factsBy.slice(0, at);
    noAuto.add(at);
    render();
    answers.querySelector("#cee-rescue-search")?.focus({ preventScroll: true });
  });
  const reset = () => { path = ["start"]; picked = []; known = []; facts = {}; factsBy = []; previous = {}; noAuto = new Set(); extra = {}; };
  again.addEventListener("click", () => { reset(); reported = null; render(); answers.querySelector("#cee-rescue-search")?.focus({ preventScroll: true }); });
  window.addEventListener(RESCUE_EVENT, e => {
    const { message = "", to = null } = e.detail ?? {};
    reported = String(message) || null;
    reset();
    // the error first, then its topic right away: the person came here to read what it means
    path = ["error", nodes[to] && to !== "error" ? to : nodes.error.next];
    render();
  });

  root.replaceChildren(el("div", { className: "cee-rescue" }, [
    el("h1", { className: "cee-rescue-title ui-sr-only", textContent: t("nav.rescue") }),
    chat,
    answers,
    nav,
  ]));
  render();
}
