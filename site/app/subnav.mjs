/**
 * The options of a page as sub-items of its sidebar entry: each one a folding
 * block under the entry, shown only while that page is open. A page without
 * options adds nothing and its entry stays a single line.
 */
import { el } from "./fields.mjs";
import { icon } from "./icons.mjs";
import { t } from "./i18n.mjs";

export function subnav() {
  let current = null;
  const hosts = new Map();
  // A tablist holds tabs only: the group headings and the options sit beside it in the same flex column and take
  // their place by order, a heading above the entry it names in data-before, the options under their entry.
  const tabs = [...document.querySelectorAll("#cee-areas [role=tab]")];
  const slot = tab => 3 * tabs.indexOf(tab);
  tabs.forEach(t => { t.style.order = String(slot(t) + 1); });
  for (const g of document.querySelectorAll(".cee-nav-group")) g.style.order = String(slot(document.getElementById(`cee-tab-${g.dataset.before}`)));

  const host = tab => {
    if (hosts.has(tab)) return hosts.get(tab);
    const entry = document.getElementById(`cee-tab-${tab}`);
    const node = el("div", { className: "cee-nav-sub", id: `cee-sub-${tab}`, role: "group", hidden: true });
    node.setAttribute("aria-label", t("nav.options", { area: entry.textContent }));
    node.style.order = String(slot(entry) + 2);
    entry.closest(".cee-nav").append(node);
    hosts.set(tab, node);
    return node;
  };

  const show = () => { for (const [tab, node] of hosts) node.hidden = tab !== current; };

  return {
    /** Adds a block under the entry of `tab`; its content goes into `body`. */
    add(tab, { id, title, open = false }) {
      const body = el("div", { className: "ui-details-body" });
      // Open or closed is kept per block (by its id, never by the address: the emulator port changes each start).
      const key = `cee.sub.${id}`;
      let saved = null;
      try { saved = localStorage.getItem(key); } catch {}
      const details = el("details", { className: "ui-details", id, open: saved === null ? open : saved === "1" }, [el("summary", { textContent: title }), body]);
      details.addEventListener("toggle", () => { try { localStorage.setItem(key, details.open ? "1" : "0"); } catch {} });
      host(tab).append(details);
      show();
      return { details, body };
    },
    /**
     * Sub-pages of the entry of `tab`: one button each under the entry, shown while that page is open. `pick(id)` runs
     * on a click, `select(id)` marks the page that is open.
     */
    pages(tab, { id, label, items, pick }) {
      const list = el("div", { className: "cee-nav-pages", id, role: "group" });
      list.setAttribute("aria-label", label);
      const buttons = items.map(item => {
        const button = el("button", { type: "button", className: "cee-nav-subitem", id: `cee-${tab}-page-${item.id}` }, [item.icon ? icon(item.icon) : null, el("span", { textContent: item.title })]);
        button.dataset.page = item.id;
        button.addEventListener("click", () => pick(item.id));
        return button;
      });
      list.append(...buttons);
      host(tab).append(list);
      show();
      return {
        select(open) { for (const b of buttons) b.toggleAttribute("aria-current", b.dataset.page === open); },
      };
    },
    /** The page that is open now. */
    page(id) { current = id; show(); },
  };
}
