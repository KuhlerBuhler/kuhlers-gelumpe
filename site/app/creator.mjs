/**
 * "von <name>" on a card or a detail page, the name a link to the creator's profile when there is one: the piece's own
 * link (an own effect or plugin) or the catalog's (data/creators.mjs).
 */
import { el } from "./fields.mjs";
import { CREATORS } from "../../data/creators.mjs";
import { linkOk } from "../../src/fx-v2.mjs";

/** The creator's name, as a link to their profile when one is known; null without a name. */
export function creatorName(name, url = null) {
  if (!name) return null;
  const href = url && linkOk(url) ? url : CREATORS[name];
  if (!href) return document.createTextNode(name);
  // Above the button that covers a catalog card, so the name is its own target; the app opens it in the browser.
  return el("a", { className: "cee-text-link cee-creator-link", href, target: "_blank", rel: "noopener noreferrer", textContent: name });
}

/** The line at the bottom of a catalog card. */
export function creatorLine(name, url = null) {
  const who = creatorName(name, url);
  return who ? el("p", { className: "cee-catalog-creator muted" }, ["von ", who]) : null;
}

const LIMITS = { description: 300, creator: 40, creatorUrl: 200 };

/**
 * Beschreibung, Creator and Link of an own piece, edited in place. `target()` gives the object they are written to
 * (the open effect, modulation or plugin); `changed()` runs after each edit. `set(values)` fills them again.
 */
export function metaFields(prefix, target, changed = () => {}) {
  const field = (key, label, control, help = null) => {
    control.id = `${prefix}-${key}`;
    control.maxLength = LIMITS[key];
    control.addEventListener("input", () => {
      const into = target();
      if (!into) return;
      into[key] = control.value;
      if (key === "creatorUrl") control.setCustomValidity(control.value && !linkOk(control.value) ? "Bitte eine Adresse mit https://" : "");
      changed();
    });
    return el("div", { className: "ui-field" }, [
      el("label", { className: "ui-field-label", htmlFor: control.id, textContent: label }),
      control,
      help ? el("p", { className: "ui-field-help", textContent: help }) : null,
    ]);
  };
  const description = el("textarea", { className: "textarea", rows: 3, placeholder: "Was macht er, wofür ist er gut?" });
  const creator = el("input", { type: "text", className: "input", autocomplete: "nickname", placeholder: "Dein Name" });
  const creatorUrl = el("input", { type: "url", className: "input", inputMode: "url", placeholder: "https://www.instagram.com/…" });
  const node = el("div", { className: "cee-meta-fields", id: `${prefix}-meta` }, [
    field("description", "Beschreibung", description),
    el("div", { className: "cee-meta-who" }, [
      field("creator", "Creator", creator),
      field("creatorUrl", "Link zum Profil", creatorUrl, "Ein Klick auf deinen Namen führt dorthin."),
    ]),
  ]);
  return {
    node,
    set(values = {}) {
      description.value = values.description ?? "";
      creator.value = values.creator ?? "";
      creatorUrl.value = values.creatorUrl ?? "";
      creatorUrl.setCustomValidity("");
    },
  };
}

/** Why the words cannot be kept, or null: only the link can be wrong. */
export const metaProblem = values => (values?.creatorUrl && !linkOk(values.creatorUrl) ? "Der Link zum Profil muss mit https:// beginnen." : null);
