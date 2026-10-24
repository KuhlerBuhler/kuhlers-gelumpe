/**
 * The Rettung page: Blechy asks what the device shows and walks through the documented way back, one question at a
 * time, with the answers as buttons. What is only to read follows by itself after a second; Blechy waits only where
 * the person has to do or answer something. Content: data/rescue.mjs.
 */
import { el } from "./fields.mjs";
import { FLOW, STATUS, LINKS, BUTTONS } from "../../data/rescue.mjs";
import { e2Art } from "./e2-art.mjs";

/** The pause before Blechy's next message when the one before only had something to read. */
const PAUSE_MS = 1000;

const BODY = { red: "var(--color-card-suit-red)", blue: "var(--color-chart-blue)", grey: "var(--color-text-muted)" };
const MOODS = { idle: "img/blechy/idle.png", happy: "img/blechy/happy.png", angry: "img/blechy/angry.png", wave: "img/blechy/wave.png", sad: "img/blechy/sad.png" };

const pill = status => {
  const p = el("span", { className: "cee-status", textContent: STATUS[status].text });
  p.dataset.tone = STATUS[status].tone;
  return p;
};

const link = (href, text) => el("a", { className: "cee-text-link", href, target: "_blank", rel: "noopener noreferrer", textContent: text });

/** A line of text: a string, or parts where { link, text } is a link to LINKS[link]; "issueNew" opens a new issue with `issue` filled in. */
const words = (line, issue = {}) => (Array.isArray(line)
  ? line.map(part => (typeof part === "string" ? part : link(part.link === "issueNew" ? `${LINKS.issues}/new?${new URLSearchParams(issue)}` : LINKS[part.link], part.text)))
  : [line]);

/** What Blechy says in one node: the lines, a path on the card, how sure it is, and behind a fold where that comes from. */
const say = (node, issue) => [
  ...node.say.map(line => (line.path ? el("code", { className: "cee-rescue-path", textContent: line.path }) : el("p", {}, words(line, issue)))),
  node.status ? el("div", { className: "cee-rescue-meta" }, [
    pill(node.status),
    node.note ? el("details", { className: "cee-rescue-note" }, [el("summary", { textContent: "Woher wir das wissen" }), el("p", {}, words(node.note))]) : null,
  ]) : null,
];

export function rescuePage(root) {
  const nodes = FLOW;
  const chat = el("ol", { className: "cee-rescue-chat", id: "cee-rescue-chat", "aria-live": "polite" });
  const answers = el("div", { className: "cee-rescue-answers", id: "cee-rescue-answers" });
  const back = el("button", { type: "button", className: "btn sm", id: "cee-rescue-back", textContent: BUTTONS.back });
  const again = el("button", { type: "button", className: "btn sm", id: "cee-rescue-again", textContent: BUTTONS.again });
  let path = ["start"];
  let picked = [];
  let timer = null;

  const blechy = (mood, parts) => el("li", { className: "cee-rescue-say" }, [
    el("img", { className: "cee-rescue-blechy", src: MOODS[mood], alt: "", width: 45, height: 55 }),
    el("div", { className: "cee-rescue-bubble" }, parts.filter(Boolean)),
  ]);
  const you = text => el("li", { className: "cee-rescue-you" }, [el("p", { className: "cee-rescue-bubble", textContent: text })]);

  /** A new issue that already says which way through the page the person took. */
  const issue = () => ({
    title: `Rettung: ${picked[0] ?? ""}`,
    body: `Meine Antworten in der Rettung:\n${picked.filter(Boolean).map(p => `- ${p}`).join("\n")}\n\nWas das Display zeigt und was ich zuletzt gemacht habe:\n\n(Foto vom Display hier hineinziehen)\n`,
  });

  function render() {
    chat.replaceChildren(...path.flatMap((id, i) => [blechy(nodes[id].mood, say(nodes[id], issue())), picked[i] ? you(picked[i]) : null].filter(Boolean)));
    const node = nodes[path.at(-1)];
    const choices = node.choices ?? [];
    answers.replaceChildren(...choices.map(c => {
      const b = el("button", { type: "button", className: `btn${c.art ? " cee-rescue-folder" : ""}`, onclick: () => choose(c) }, [
        c.art ? e2Art(BODY[c.art], c.label) : null,
        el("span", { className: "cee-rescue-answer", textContent: c.label }),
        c.hint ? el("span", { className: "cee-rescue-hint", textContent: c.hint }) : null,
      ]);
      if (c.id) b.id = `cee-rescue-case-${c.id}`;
      return b;
    }));
    answers.hidden = !choices.length;
    back.disabled = path.length < 2;
    chat.lastElementChild?.scrollIntoView?.({ block: "nearest" });
    clearTimeout(timer);
    // While Blechy still has something to say, the answers wait and tests can tell (data-waiting).
    answers.toggleAttribute("data-waiting", !!node.next);
    if (node.next) timer = setTimeout(() => { path = [...path, node.next]; render(); }, PAUSE_MS);
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
    do path = path.slice(0, -1); while (path.length > 1 && nodes[path.at(-1)].next);
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
