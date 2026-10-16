/**
 * Which URL path serves which directory. The local server and the Pages
 * build both read this, so the page sees the same layout in both.
 */
export const ROUTES = [
  ["/src/", "src/"],
  ["/data/", "data/"],
  ["/assets/blechy/", "assets/blechy/"],
  ["/docs/", "docs/"],
  ["/third_party/doom/", "third_party/doom/"],
  ["/", "site/"],
];
