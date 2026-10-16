/** The Rettung page: a guide through the documented way back, with a stop sign. Content: data/rescue.mjs. */
import { el } from "./fields.mjs";
import RESCUE, { STATUS, LINKS } from "../../data/rescue.mjs";

const pill = status => {
  const p = el("span", { className: "cee-status", textContent: STATUS[status].text });
  p.dataset.tone = STATUS[status].tone;
  return p;
};

const source = path => el("span", { className: "cee-rescue-source" }, ["Beleg: ", el("code", { textContent: path })]);

const link = (href, text) => el("a", { className: "cee-text-link", href, target: "_blank", rel: "noopener noreferrer", textContent: text });

function stepItem(step) {
  return el("li", { className: "cee-rescue-step" }, [
    el("p", { textContent: step.text }),
    el("p", { className: "cee-rescue-meta" }, [pill(step.status), source(step.source)]),
    step.note ? el("p", { className: "muted", textContent: step.note }) : null,
  ]);
}

function caseBlock(c) {
  const body = el("div", { className: "ui-details-body" }, [
    el("ol", { className: "cee-rescue-steps" }, c.steps.map(stepItem)),
    el("p", { className: "cee-rescue-limit" }, [el("strong", { textContent: "Grenze: " }), c.limit, " ", source(c.limitSource)]),
  ]);
  const summary = el("summary", {}, [el("span", { textContent: c.label }), el("span", { className: "muted cee-rescue-hint", textContent: c.hint })]);
  return el("details", { className: "ui-details cee-rescue-case", id: `cee-rescue-case-${c.id}` }, [summary, body]);
}

export function rescuePage(root) {
  const stop = el("section", { className: "cee-rescue-stop", id: "cee-rescue-stop" }, [
    el("h2", { id: "cee-rescue-stop-title", textContent: RESCUE.stop.title }),
    ...RESCUE.stop.lines.map(text => el("p", { textContent: text })),
    el("p", { className: "cee-rescue-meta" }, [source(RESCUE.stop.source)]),
  ]);
  stop.setAttribute("role", "note");
  stop.setAttribute("aria-labelledby", "cee-rescue-stop-title");

  const folders = el("ul", { className: "cee-rescue-folders", id: "cee-rescue-folders" }, RESCUE.folders.map(f => el("li", {}, [
    el("strong", { textContent: `Läuft ${f.running}` }),
    el("code", { className: "cee-rescue-path", textContent: f.path }),
    el("p", { className: "cee-rescue-meta" }, [pill(f.status), source(f.source)]),
    el("p", { className: "muted", textContent: f.note }),
  ])));

  const legend = el("ul", { className: "cee-rescue-legend" }, Object.keys(STATUS).map(k => el("li", {}, [pill(k), el("span", { textContent: ` ${STATUS[k].meaning}` })])));

  root.replaceChildren(el("div", { className: "cee-rescue" }, [
    el("h1", { className: "cee-rescue-title", textContent: "Rettung" }),
    el("p", { className: "cee-rescue-lead", textContent: "Das Gerät startet nach einem Update oder Patch nicht mehr richtig? Hier steht der Weg zurück, soweit die Dokumentation ihn belegt. Jeder Schritt sagt dazu, wie sicher er ist. Lies erst alles, bevor du etwas tust." }),
    stop,
    el("section", { className: "cee-rescue-sec" }, [
      el("h2", { textContent: "Vorher" }),
      el("ul", {}, RESCUE.before.map(text => el("li", { textContent: text }))),
    ]),
    el("section", { className: "cee-rescue-sec" }, [
      el("h2", { textContent: "Welche Datei in welchen Ordner" }),
      el("p", { className: "muted", textContent: "Die Datei heißt immer SYSTEM.VSB. Der Ordner hängt von der Firmware ab, die gerade läuft." }),
      folders,
    ]),
    el("section", { className: "cee-rescue-sec" }, [
      el("h2", { textContent: "Was zeigt dein Gerät?" }),
      el("div", { className: "cee-rescue-cases" }, RESCUE.cases.map(caseBlock)),
    ]),
    el("section", { className: "cee-rescue-sec" }, [
      el("h2", { textContent: "Wie sicher ist ein Schritt?" }),
      legend,
    ]),
    el("p", { className: "muted" }, ["Die Anleitungen von Hacktribe, auf die sich die Seite stützt: ", link(LINKS.howTo, "How-To"), ", ", link(LINKS.debrick, "Debrick"), "."]),
  ]));
}
