import { readFileSync } from "node:fs";
import { readPng } from "./blechy-png.mjs";

export const HEAD = readPng(readFileSync(new URL("../assets/blechy/head.png", import.meta.url)));

export function resizedHead(maxWidth, maxHeight) {
  const scale = Math.min(maxWidth / HEAD[0].length, maxHeight / HEAD.length);
  const width = Math.round(HEAD[0].length * scale);
  const height = Math.round(HEAD.length * scale);
  return Array.from({ length: height }, (_, y) => Array.from({ length: width }, (_, x) =>
    HEAD[Math.floor(y * HEAD.length / height)][Math.floor(x * HEAD[0].length / width)]).join(""));
}

export function pixelPath(rows) {
  let path = "";
  for (let y = 0; y < rows.length; y++) {
    for (let x = 0; x < rows[y].length;) {
      if (rows[y][x] !== "#") { x++; continue; }
      let end = x + 1;
      while (rows[y][end] === "#") end++;
      path += `M${x} ${y}h${end - x}v1h-${end - x}z`;
      x = end;
    }
  }
  return path;
}
