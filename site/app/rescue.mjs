/**
 * The Rettung page: Blechy asks what the device shows and walks through the documented way back, one question at a
 * time, with the answers as buttons. Every step says how sure it is. What is only to read follows by itself after a
 * short pause; a step that asks for something waits for the answer. Content: data/rescue.mjs.
 */
import { el } from "./fields.mjs";
import RESCUE, { STATUS, LINKS, TALK } from "../../data/rescue.mjs";
import { e2Art } from "./e2-art.mjs";

/** The pause before Blechy's next message when the one before only had something to read. */
const PAUSE_MS = 900;

const BODY = { red: "var(--color-card-suit-red)", blue: "var(--color-chart-blue)", grey: "var(--color-text-muted)" };
const MOODS = { idle: "img/blechy/idle.png", happy: "img/blechy/happy.png", angry: "img/blechy/angry.png", wave: "img/blechy/wave.png", sad: "img/blechy/sad.png" };

const pill = status => {
  const p = el("span", { className: "cee-status", textContent: STATUS[status].text });
  p.dataset.tone = STATUS[status].tone;
  return p;
};

const link = (href, text) => el("a", { className: "cee-text-link", href, target: "_blank", rel: "noopener noreferrer", textContent: text });

/** A line of text: a string, or parts where { link, text } is a link to LINKS[link]. */
const words = line => (Array.isArray(line) ? line.map(part => (typeof part === "string" ? part : link(LINKS[part.link], part.text))) : [line]);

/** What Blechy says for one step of a case: the step, how sure it is, and the note behind it. */
const stepSay = step => [
  el("p", { textContent: step.text }),
  el("p", { className: "cee-rescue-meta" }, [pill(step.status)]),
  step.note ? el("p", { className: "cee-rescue-note", textContent: step.note }) : null,
];

/**
 * The flow: each node is what Blechy says (`say`, DOM parts), his mood, and the answers that lead on, or `auto`, the
 * node that follows by itself. A case is its steps one after another, then its limit; "starts" asks before the file step which firmware runs, for the folder.
 */
function flow() {
  const nodes = {};
  const caseOf = id => RESCUE.cases.find(c => c.id === id);
  nodes.start = {
    mood: "idle",
    say: () => [el("p", { textContent: TALK.hello })],
    choices: RESCUE.cases.map(c => ({ label: c.label, hint: c.hint, to: `case:${c.id}:0`, id: c.id })),
  };
  for (const c of RESCUE.cases) {
    c.steps.forEach((step, i) => {
      const last = i === c.steps.length - 1;
      const next = last ? `limit:${c.id}` : `case:${c.id}:${i + 1}`;
      nodes[`case:${c.id}:${i}`] = {
        mood: c.id === "silent" ? "angry" : "idle",
        say: () => [
          ...(i === 0 && c.id === "silent" ? [el("p", { className: "cee-rescue-stop", id: "cee-rescue-stop" }, [el("strong", { textContent: `${RESCUE.stop.title}. ` }), ...words(RESCUE.stop.lines[1])])] : []),
          ...stepSay(step),
        ],
        choices: c.id === "starts" && i === 0
          ? [{ label: TALK.helped, to: "fixed" }, { label: TALK.notHelped, to: "before" }]
          : step.act ? [{ label: TALK.done, to: next }] : [],
        auto: c.id === "starts" || step.act ? null : next,
      };
    });
    nodes[`limit:${c.id}`] = {
      mood: c.id === "starts" ? "wave" : "sad",
      say: () => [el("p", { className: "cee-rescue-limit" }, [el("strong", { textContent: "Grenze: " }), c.limit]), el("p", { textContent: TALK.end })],
      choices: [],
    };
  }
  nodes.fixed = { mood: "happy", say: () => [el("p", { textContent: TALK.fixed })], choices: [] };
  nodes.before = {
    mood: "idle",
    say: () => [el("p", { textContent: TALK.before }), el("ul", { className: "cee-rescue-before" }, RESCUE.before.map(text => el("li", { textContent: text })))],
    choices: [{ label: TALK.ready, to: "which" }, { label: TALK.notReady, to: "nobackup" }],
  };
  nodes.nobackup = { mood: "angry", say: () => [el("p", { textContent: TALK.noBackup })], choices: [] };
  nodes.which = {
    mood: "idle",
    say: () => [el("p", { textContent: TALK.which })],
    choices: RESCUE.folders.map((f, i) => ({ label: f.title, to: `folder:${i}`, art: f })),
  };
  RESCUE.folders.forEach((f, i) => {
    nodes[`folder:${i}`] = {
      mood: "idle",
      say: () => [el("p", { textContent: TALK.folder }), el("code", { className: "cee-rescue-path", textContent: f.path }), ...stepSay(caseOf("starts").steps[1])],
      choices: [{ label: TALK.done, to: "case:starts:2" }],
    };
  });
  return nodes;
}

export function rescuePage(root) {
  const nodes = flow();
  const chat = el("ol", { className: "cee-rescue-chat", id: "cee-rescue-chat", "aria-live": "polite" });
  const answers = el("div", { className: "cee-rescue-answers", id: "cee-rescue-answers" });
  const back = el("button", { type: "button", className: "btn sm", id: "cee-rescue-back", textContent: TALK.back });
  const again = el("button", { type: "button", className: "btn sm", id: "cee-rescue-again", textContent: TALK.again });
  let path = ["start"];
  let picked = [];
  let timer = null;

  const blechy = (mood, parts) => el("li", { className: "cee-rescue-say" }, [
    el("img", { className: "cee-rescue-blechy", src: MOODS[mood], alt: "", width: 45, height: 55 }),
    el("div", { className: "cee-rescue-bubble" }, parts.filter(Boolean)),
  ]);
  const you = text => el("li", { className: "cee-rescue-you" }, [el("p", { className: "cee-rescue-bubble", textContent: text })]);

  function render() {
    chat.replaceChildren(...path.flatMap((id, i) => [blechy(nodes[id].mood, nodes[id].say()), picked[i] ? you(picked[i]) : null].filter(Boolean)));
    const node = nodes[path.at(-1)];
    answers.replaceChildren(...node.choices.map(c => {
      const b = el("button", { type: "button", className: `btn${c.art ? " cee-rescue-folder" : ""}`, onclick: () => choose(c) }, [
        c.art ? e2Art(BODY[c.art.body], c.art.title) : null,
        el("span", { className: "cee-rescue-answer", textContent: c.label }),
        c.hint ? el("span", { className: "cee-rescue-hint", textContent: c.hint }) : null,
      ]);
      if (c.id) b.id = `cee-rescue-case-${c.id}`;
      return b;
    }));
    answers.hidden = !node.choices.length;
    back.disabled = path.length < 2;
    chat.lastElementChild?.scrollIntoView?.({ block: "nearest" });
    clearTimeout(timer);
    // While Blechy still has something to say, the answers wait and tests can tell (data-waiting).
    answers.toggleAttribute("data-waiting", !!node.auto);
    if (node.auto) timer = setTimeout(() => { path = [...path, node.auto]; render(); }, PAUSE_MS);
  }
  function choose(c) {
    picked[path.length - 1] = c.label;
    path = [...path, c.to];
    render();
    answers.querySelector("button")?.focus({ preventScroll: true });
  }
  back.addEventListener("click", () => {
    if (path.length < 2) return;
    // Back to the last question, past what Blechy said by himself.
    do path = path.slice(0, -1); while (path.length > 1 && nodes[path.at(-1)].auto);
    picked = picked.slice(0, path.length - 1);
    render();
  });
  again.addEventListener("click", () => { path = ["start"]; picked = []; render(); });

  root.replaceChildren(el("div", { className: "cee-rescue" }, [
    el("h1", { className: "cee-rescue-title ui-sr-only", textContent: "Rettung" }),
    chat,
    answers,
    el("div", { className: "actions cee-rescue-nav" }, [back, again]),
  ]));
  render();
}
