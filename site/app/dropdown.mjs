/**
 * A menu button: the design system has no dropdown yet, so this is an own
 * building block (cee-mode). Arrow keys walk the items, Escape and a click
 * outside close it, and the focus goes back to the button.
 */
export function dropdown(button, menu, { onPick }) {
  const items = () => [...menu.querySelectorAll("[role^=menuitem]")];
  const isOpen = () => !menu.hidden;

  function open(focusItem = null) {
    menu.hidden = false;
    button.setAttribute("aria-expanded", "true");
    const list = items();
    const target = focusItem === "last" ? list.at(-1) : focusItem === "first" ? list[0] : null;
    target?.focus();
  }

  function close(refocus = false) {
    if (!isOpen()) return;
    menu.hidden = true;
    button.setAttribute("aria-expanded", "false");
    if (refocus) button.focus();
  }

  button.addEventListener("click", () => (isOpen() ? close() : open("first")));
  button.addEventListener("keydown", e => {
    if (e.key === "ArrowDown") { e.preventDefault(); open("first"); }
    if (e.key === "ArrowUp") { e.preventDefault(); open("last"); }
  });

  menu.addEventListener("keydown", e => {
    const list = items();
    const at = list.indexOf(document.activeElement);
    const to = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: list.length - 1 }[e.key];
    if (to !== undefined) { e.preventDefault(); list[(to + list.length) % list.length].focus(); return; }
    if (e.key === "Escape") { e.preventDefault(); close(true); }
    if (e.key === "Tab") close();
  });

  menu.addEventListener("click", e => {
    const item = e.target.closest("[role^=menuitem]");
    if (!item) return;
    close(true);
    onPick(item.dataset.value);
  });

  document.addEventListener("pointerdown", e => {
    if (isOpen() && !menu.contains(e.target) && !button.contains(e.target)) close();
  });

  return { close, isOpen };
}
