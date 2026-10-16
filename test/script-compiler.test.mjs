import { test } from "node:test";
import assert from "node:assert/strict";
import { compile, formatError } from "../src/script/compiler.mjs";
import { tokenize } from "../src/script/parser.mjs";
import { decodeBlob, disassemble } from "../src/script/blob.mjs";
import { verify } from "../src/script/verifier.mjs";
import { ScriptRuntime } from "../src/script/runtime.mjs";
import { LIMITS, BUDGET, EVENT_BY_NAME, API } from "../data/script/contract.mjs";

/** Compile, run the body, and give back what the script left in its globals. */
function run(src, { name = "t" } = {}) {
  const r = compile(src, { name });
  assert.ok(r.ok, r.errors?.map(formatError).join("\n"));
  const rt = new ScriptRuntime({ now: () => 0 });
  const a = rt.add(r.blob);
  assert.ok(a.ok, a.error?.message);
  const slot = n => r.info.symbols[n].slot;
  return {
    r,
    script: a.script,
    v: n => a.script.vars[slot(n)],
    arr: n => Array.from(a.script.vars.slice(slot(n), slot(n) + r.info.symbols[n].length)),
  };
}

const fails = (src, line, column, pattern, options) => {
  const r = compile(src, options);
  assert.equal(r.ok, false, `compiled but should not have: ${JSON.stringify(src)}`);
  const e = r.errors[0];
  assert.equal(r.errors.length, 1);
  assert.deepEqual([e.line, e.column], [line, column], `${formatError(e)}`);
  assert.match(e.message, pattern);
  return e;
};

test("a script compiles to a blob that decodes, verifies and names its handlers", () => {
  const r = compile("let n = 0;\nkorg.onEvent(\"knob\", (i, v) => { n = v; });\nkorg.onEvent(\"ready\", () => { n = 1; });\n", { name: "demo" });
  assert.ok(r.ok);
  const d = decodeBlob(r.blob);
  assert.ok(d.ok);
  assert.equal(d.header.name, "demo");
  assert.equal(d.header.apiVersion, 1);
  assert.deepEqual(r.info.handlers.map(h => [h.event, h.argc]), [["knob", 2], ["ready", 0]]);
  assert.deepEqual(d.handlers.map(h => [h.event, h.argc]), [[EVENT_BY_NAME.get("knob").id, 2], [EVENT_BY_NAME.get("ready").id, 0]]);
  assert.ok(verify(r.blob).ok);
  assert.equal(r.info.size, r.blob.length);
  assert.match(disassemble(d), /^start:\n {2}0000 {2}PUSHB/);
});

test("the same source gives the same bytes, a long name is cut to the header's 15 characters", () => {
  const src = "let a = 1;\nkorg.onEvent(\"frame\", () => { a += 1; });\n";
  assert.deepEqual(compile(src, { name: "x" }).blob, compile(src, { name: "x" }).blob);
  assert.equal(compile(src, { name: "a-very-long-script-name" }).info.name, "a-very-long-scr");
});

test("arithmetic: precedence, truncating division, sign of the remainder, 32-bit wrap", () => {
  const t = run(`
    let a = 7; let b = -2; let z = 0; let big = 2147483647;
    let sum = a + b * 3;
    let div = a / b;
    let mod = a % b;
    let neg = -a;
    let wrap = big + 1;
    let mul = 65536 * 65536;
    let bits = (a & 3) | (a ^ 1) << 4;
    let shr = -16 >> 2;
    let shl = a << 33;
    let inv = ~a;
    let cmp = (a > b) + (a < b) * 10 + (a == 7) * 100 + (a != 7) * 1000 + (a >= 7) * 10000 + (a <= 6) * 100000;
    let same = a === 7;
    let diff = a !== 7;
    let hex = 0xFF;
    let allOnes = 0xFFFFFFFF;
  `);
  assert.deepEqual(
    ["sum", "div", "mod", "neg", "wrap", "mul", "bits", "shr", "shl", "inv", "cmp", "same", "diff", "hex", "allOnes"].map(n => t.v(n)),
    [1, -3, 1, -7, -2147483648, 0, 99, -4, 14, -8, 10101, 1, 0, 255, -1],
  );
});

test("constant expressions fold: the compiler gives the same answer the VM would", () => {
  const folded = run("let r = (7 + 3) * 4 - 10 / 3 + 7 % 4 + (1 << 4) + (-8 >> 1) + (5 > 3 ? 100 : 200);\nlet s = 65536 * 65536 + 2147483647 + 1;\n");
  const live = run("let a = 7; let b = 3; let c = 4; let t = 10; let u = 1; let d = -8; let e = 5;\nlet r = (a + b) * c - t / b + a % c + (u << c) + (d >> u) + (e > b ? 100 : 200);\nlet big = 2147483647; let s = 65536 * 65536 + big + 1;\n");
  assert.equal(folded.v("r"), live.v("r"));
  assert.equal(folded.v("s"), live.v("s"));
  assert.equal(folded.v("r"), 40 - 3 + 3 + 16 - 4 + 100);
});

test("&& and || return an operand like JavaScript and skip the right side when they can", () => {
  const t = run(`
    let hits = 0;
    function bump() { hits += 1; return 1; }
    let a = 7; let b = -2; let z = 0;
    let and1 = a && b;
    let and0 = z && a;
    let or1 = z || b;
    let or0 = z || z;
    let not1 = !z;
    let not0 = !a;
    let s1 = z && bump();
    let s2 = a || bump();
    let after = hits;
    let s3 = a && bump();
    let s4 = z || bump();
  `);
  assert.deepEqual(["and1", "and0", "or1", "or0", "not1", "not0", "s1", "s2", "after", "hits"].map(n => t.v(n)), [-2, 0, -2, 0, 1, 0, 0, 7, 0, 2]);
});

test("loops: while, for, break, continue, nested; assignment operators", () => {
  const t = run(`
    let total = 0;
    for (let i = 0; i < 10; i++) {
      if (i == 3) continue;
      if (i == 8) break;
      total += i;
    }
    let w = 0; let k = 0;
    while (k < 5) { w += k * k; k++; }
    let nest = 0;
    for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) { if (j > i) break; nest += 1; }
    let c = 100;
    c += 5; c -= 3; c *= 2; c /= 4; c %= 20; c <<= 3; c >>= 1; c &= 0x3c; c |= 1; c ^= 8;
    let d = 3; d--; --d; ++d;
    let down = 10;
    for (let i = 10; i > 0; i -= 3) down = i;
  `);
  assert.deepEqual(["total", "w", "k", "nest"].map(n => t.v(n)), [0 + 1 + 2 + 4 + 5 + 6 + 7, 0 + 1 + 4 + 9 + 16, 5, 10]);
  let c = 100;
  c += 5; c -= 3; c *= 2; c = (c / 4) | 0; c %= 20; c <<= 3; c >>= 1; c &= 0x3c; c |= 1; c ^= 8;
  assert.equal(t.v("c"), c);
  assert.equal(t.v("d"), 2);
  assert.equal(t.v("down"), 1);
});

test("functions: arguments, results, early return, falling off the end, calls before the declaration", () => {
  const t = run(`
    let g = 10;
    let first = twice(add(3, 4));
    let early = pick(5);
    let late = pick(-5);
    let none = nothing();
    let usesGlobal = readG() + 1;
    function add(a, b) { return a + b; }
    function twice(x) { return add(x, x); }
    function pick(x) { if (x > 0) { return 1; } return 2; }
    function nothing() { let q = 3; }
    function readG() { return g; }
  `);
  assert.deepEqual(["first", "early", "late", "none", "usesGlobal"].map(n => t.v(n)), [14, 1, 2, 0, 11]);
});

test("functions do not share locals, and a block's variables are scoped and reuse slots", () => {
  const t = run(`
    function a() { let x = 1; return x + b(); }
    function b() { let x = 20; return x; }
    let r = a();
    let outer = 1;
    { let outer2 = 5; outer = outer2; }
    { let other = 7; outer += other; }
    for (let i = 0; i < 2; i++) { let tmp = i * 10; outer += tmp; }
    let shadow = 3;
    function sh() { let shadow = 99; return shadow; }
    let s = sh();
  `);
  assert.deepEqual(["r", "outer", "shadow", "s"].map(n => t.v(n)), [21, 5 + 7 + 10, 3, 99]);
  assert.ok(t.r.info.vars < 16, `slots are reused: ${t.r.info.vars}`);
});

test("constants: compile-time values in array sizes, .length, no slot of their own", () => {
  const t = run("const W = 4;\nconst N = W * W + 1;\nconst data = new Array(N);\nlet len = data.length;\nconst text = \"hi\";\nlet last = data.length - 1;\n");
  assert.equal(t.v("len"), 17);
  assert.equal(t.v("last"), 16);
  assert.equal(t.r.info.symbols.W, undefined);
  assert.equal(t.r.info.symbols.data.length, 17);
});

test("arrays: size, literal, element read and write, compound assignment, bounds", () => {
  const t = run(`
    const sq = [0, 1, 4, 9, 16];
    let buf = new Array(6);
    let sum = 0;
    for (let i = 0; i < sq.length; i++) { buf[i] = sq[i] * 2; sum += buf[i]; }
    buf[5] += 7;
    buf[1]++;
    buf[2]--;
    buf[0] -= 3;
    let idx = 3;
    buf[idx] *= 2;
  `);
  assert.deepEqual(t.arr("sq"), [0, 1, 4, 9, 16]);
  assert.deepEqual(t.arr("buf"), [-3, 3, 7, 36, 32, 7]);
  assert.equal(t.v("sum"), 60);
  const rt = new ScriptRuntime({ now: () => 0 });
  const out = rt.add(compile("let a = new Array(4);\nlet i = 4;\nlet x = a[i];\n").blob);
  assert.equal(out.ok, false);
  assert.equal(out.error.name, "BOUNDS");
  assert.equal(out.error.line, 3);
});

test("text: a literal or a variable, compared with == and handed to the API, never joined", () => {
  const t = run("let s = \"abc\";\nlet same = s == \"abc\";\nlet diff = s != \"abc\";\nconst T = \"abc\";\nlet viaConst = s == T;\nlet pick = same ? \"yes\" : \"no\";\nlet isYes = pick == \"yes\";\n");
  assert.deepEqual(["same", "diff", "viaConst", "isYes"].map(n => t.v(n)), [1, 0, 1, 1]);
  assert.equal(t.r.info.symbols.s.type, "str");
});

test("a text goes to the API as text, a number as number", () => {
  const calls = [];
  const r = compile("korg.app(\"Text\", \"TOOLS\");\nconst label = \"Klicks\";\nlet n = 5;\nkorg.onEvent(\"ready\", () => { korg.display.text(label, 1, 2); korg.display.number(n, 3, 4); });\n");
  assert.ok(r.ok, r.errors?.map(formatError).join());
  const rt = new ScriptRuntime({ now: () => 0, api: { "korg.display.text": (...a) => calls.push(["text", ...a]), "korg.display.number": (...a) => calls.push(["number", ...a]) } });
  rt.add(r.blob);
  assert.ok(rt.openApp(0), "drawing is taken from an open app only");
  rt.frame();
  assert.deepEqual(calls, [["text", "Klicks", 1, 2], ["number", 5, 3, 4]]);
});

test("top-level control flow and a function name as a handler", () => {
  const t = run(`
    let total = 0;
    for (let i = 0; i < 3; i++) { total += i; }
    if (total == 3) { total += 100; } else { total = -1; }
    function onKey(key) { total += key; }
    korg.onEvent("buttonPress", onKey);
  `);
  assert.equal(t.v("total"), 103);
  t.script.dispatch("buttonPress", [5]);
  assert.equal(t.v("total"), 108);
  assert.deepEqual(t.r.info.handlers.map(h => h.event), ["buttonPress"]);
});

test("a handler may take fewer values than its event delivers", () => {
  const t = run("let last = 0;\nkorg.onEvent(\"knob\", (index) => { last = index; });\n");
  t.script.dispatch("knob", [7, 900]);
  assert.equal(t.v("last"), 7);
});

test("the API version in the header is the newest entry the script uses", () => {
  assert.equal(compile("let a = 1;\n").info.apiVersion, 1);
  assert.equal(compile("korg.onEvent(\"frame\", () => { korg.led(1, 1); });\n").info.apiVersion, 1);
  assert.ok(API.every(a => a.since >= 1));
});

// ---- compile errors: line, column, German message ----

test("errors name line and column and say what to do", () => {
  fails("let a = 1;\nb = 2;", 2, 1, /„b“ ist nicht deklariert/);
  fails("const c = 1;\nc = 2;", 2, 1, /const und lässt sich nicht ändern/);
  fails("let a = 1;\nlet a = 2;", 2, 5, /schon deklariert/);
  fails("function f(x) { return x; }\nf(1, 2);", 2, 1, /nimmt 1 Argument, hier sind 2/);
  fails("korg.led(1);", 1, 1, /nimmt 2 Argumente \(index, level\), hier sind 1/);
  fails("korg.display.text(5, 0, 0);", 1, 19, /„text“ von korg.display.text muss ein Text sein/);
  fails("korg.display.text(\"a\", \"b\", 0);", 1, 24, /muss eine Zahl sein/);
  fails("korg.nope(1);", 1, 1, /Die Funktion „korg.nope“ gibt es nicht/);
  fails("let a = korg.led(1, 1);", 1, 9, /gibt keinen Wert zurück/);
  fails("let a = 1 / 0;", 1, 9, /Teilen durch null/);
  fails("let a = 5;\nlet b = a ? 1 : \"x\";", 2, 9, /dieselbe Art Wert/);
  fails("let a = 1;\na[0] = 1;", 2, 1, /„a“ ist kein Feld/);
  fails("let a = 1;\nlet b = a.length;", 2, 9, /nur bei einem Feld/);
  fails("let a = x;\nlet x = 1;", 1, 9, /bevor es weiter unten deklariert/);
  fails("function f() {}\nfunction f() {}", 2, 1, /schon deklariert/);
  fails("let korg = 1;", 1, 5, /„korg“ ist der Name/);
});

test("types: a text is not a number", () => {
  fails("let a = \"x\" + \"y\";", 1, 9, /Text lässt sich nicht mit \+ verbinden/);
  fails("let t = \"x\";\nlet n = t * 2;", 2, 9, /nicht rechnen/);
  fails("let t = \"x\";\nt = 5;", 2, 5, /„t“ ist ein Text, der Wert ist aber eine Zahl/);
  fails("let n = 1;\nn = \"x\";", 2, 5, /„n“ ist eine Zahl/);
  fails("let t = \"x\";\nt += 1;", 2, 1, /nicht rechnen/);
  fails("let a = 1;\nif (\"x\") { a = 2; }", 2, 5, /Hier wird eine Zahl erwartet, das ist aber ein Text/);
  fails("let t = \"x\";\nlet u = t == 1;", 2, 9, /nur mit einem Text vergleichen/);
});

test("recursion is refused, directly and through other functions", () => {
  fails("function f() { f(); }\nf();", 1, 16, /Rekursion ist nicht erlaubt/);
  fails("function f() { g(); }\nfunction g() { f(); }\nf();", 2, 16, /Rekursion ist nicht erlaubt: „g“ ruft „f“/);
  assert.ok(compile("function f() {}\nfunction g() { f(); }\nfunction h() { f(); g(); }\nh();\n").ok, "a diamond of calls is not a cycle");
});

test("an API call outside the events it is meant for is refused at compile time, also through a function", () => {
  fails("korg.led(1, 1);", 1, 1, /„korg.led“ darf im Ereignis „start“ nicht benutzt werden/);
  fails("function f() { korg.display.clear(); }\nf();", 1, 16, /im Ereignis „start“.*\(f\)/);
  fails("function f() { korg.led(1, 1); }\nkorg.onEvent(\"ready\", () => f());\nkorg.onEvent(\"save\", () => f());", 1, 16, /im Ereignis „save“/);
  assert.ok(compile("korg.onEvent(\"ready\", () => korg.led(1, 1));\nkorg.onEvent(\"frame\", () => { korg.display.clear(); });\nlet t = korg.millis();\n").ok, "millis works everywhere");
});

test("korg.onEvent: known events, one handler each, only at the top", () => {
  fails("korg.onEvent(\"nope\", () => {});", 1, 14, /Das Ereignis „nope“ gibt es nicht.*frame/);
  fails("korg.onEvent(\"frame\", () => {});\nkorg.onEvent(\"frame\", () => {});", 2, 14, /schon einen Handler/);
  fails("korg.onEvent(\"start\", () => {});", 1, 14, /Plugin-Rumpf selbst/);
  fails("korg.onEvent(\"buttonPress\", (a, b) => {});", 1, 29, /liefert 1 Wert \(key\), der Handler nimmt 2/);
  fails("function f() { korg.onEvent(\"frame\", () => {}); }", 1, 16, /ganz oben im Plugin-Code/);
  fails("if (1) { korg.onEvent(\"frame\", () => {}); }", 1, 10, /ganz oben im Plugin-Code/);
  fails("let a = korg.onEvent(\"frame\", () => {});", 1, 9, /eigene Anweisung/);
  fails("korg.onEvent(\"frame\", handlerThatIsMissing);", 1, 23, /Als Handler geht eine Funktion/);
  fails("korg.onEvent(frame, () => {});", 1, 14, /Text in Anführungszeichen/);
  fails("korg.onEvent(\"frame\");", 1, 1, /nimmt zwei Argumente/);
  fails("korg.onEvent(\"frame\", () => { return 1; });", 1, 31, /gibt nichts zurück/);
});

test("syntax that is not in the subset says what to use instead", () => {
  fails("var a = 1;", 1, 1, /nimm „let“/);
  fails("switch (1) {}", 1, 1, /„if“ und „else if“/);
  fails("let a = `x`;", 1, 9, /Textvorlagen/);
  fails("class A {}", 1, 1, /Klassen/);
  fails("do { } while (1);", 1, 1, /nimm „while“/);
  fails("try { } catch (e) { }", 1, 1, /Ausnahmen/);
  fails("let a = null;", 1, 9, /kein „null“/);
  fails("let a = 1.5;", 1, 9, /nur ganze Zahlen/);
  fails("let a = 2147483648;", 1, 9, /zu groß/);
  fails("let a = 1;\nlet f = () => {};", 2, 9, /Eine Funktion als Wert gibt es nur in korg.onEvent/);
  fails("let a = 1;\na = a++ + 1;", 2, 6, /nur als eigene Anweisung/);
  fails("if (1) { function g() {} }", 1, 10, /nur ganz oben/);
  fails("let a = 2 ** 3;", 1, 11, /„\*\*“ gibt es nicht/);
  fails("let a = \"é\";", 1, 10, /ASCII/);
  fails("let a = \"x\\ny\";", 1, 11, /geht nur/);
  fails("let a = 1; /* never closed", 1, 12, /nie mit \*\/ geschlossen/);
  fails("let a = 5 @ 3;", 1, 11, /Zeichen „@“/);
});

test("missing pieces point at the right place", () => {
  fails("let a = 1\nlet b = 2;", 1, 10, /Hier fehlt „;“ am Ende/);
  fails("let a = 1;\nif (a = 2) {}", 2, 7, /meinst du „==“/);
  fails("let q = (1 + ;", 1, 14, /Hier wird ein Wert erwartet/);
  fails("while (1) {", 1, 11, /nie mit } geschlossen/);
  fails("let a = 1;\nelse { }", 2, 1, /„else“ ohne ein „if“/);
  fails("break;", 1, 1, /nur in einer Schleife/);
  fails("return 1;", 1, 1, /kein „return“/);
  fails("let n = 3;\nn + 1;", 2, 1, /keine Anweisung/);
  fails("let a;\nconst b;", 2, 7, /braucht einen Wert/);
  fails("function f(a, ) {}", 1, 15, /Parametername/);
  fails("let a = 1;\na = b = 2;", 2, 7, /Hier fehlt „;“/);
  fails("1 = 2;", 1, 1, /muss eine Variable oder ein Feldelement/);
});

test("arrays: only at the top, with a fixed size, never reassigned or used as a value", () => {
  fails("function f() { let a = new Array(4); }", 1, 24, /nur ganz oben im Plugin-Code/);
  fails("let n = 3;\nlet a = new Array(n);", 2, 19, /Die Größe eines Felds muss eine feste Zahl sein/);
  fails("let a = new Array(0);", 1, 9, /1 bis 65535/);
  fails("let a = new Array(65536);", 1, 9, /1 bis 65535/);
  fails("const arr = [1, 2];\narr = 3;", 2, 1, /Feld und lässt sich nicht neu zuweisen/);
  fails("const arr = new Array(2);\nlet q = arr;", 2, 9, /ist ein Feld/);
  fails("let arr = new Array(2);\nlet q = arr[\"a\"];", 2, 13, /Zahl erwartet/);
  fails("let arr = [1, x];", 1, 15, /Die Werte eines Felds müssen feste Zahlen sein/);
  fails("let arr = new Array(2);\nlet i = 0;\narr[i++] += 1;", 3, 6, /nur als eigene Anweisung/);
  fails("function f() { return 1; }\nlet arr = new Array(2);\narr[f()] += 1;", 3, 5, /keinen Funktionsaufruf/);
});

test("limits are reported where the script crosses them", () => {
  const room = BUDGET.variableSlots;
  fails(`const big = new Array(${room + 1});`, 1, 7, /braucht mindestens 32769 Variablenplätze.*Variablen-Vorabprüfung.*für dieses Plugin noch 32768.*128 KiB für Blöcke, Variablen und Einträge.*beim Laden/);
  assert.ok(compile(`const big = new Array(${room});`).ok);
  fails(`const big = new Array(${room});\nlet one = 1;`, 2, 5, /Variablenplätze/);
  fails("const a = new Array(100);\nconst b = new Array(100);", 2, 7, /braucht mindestens 200 Variablenplätze.*für dieses Plugin noch 150/, { slotsAvailable: 150 });
  const mine = compile("const a = new Array(100);\nconst b = new Array(100);", { slotsAvailable: 200 });
  assert.ok(mine.ok, "the caller sets the preliminary variable limit");
  assert.equal(compile("const a = new Array(100);\nconst b = new Array(101);", { slotsAvailable: 200 }).ok, false);
  fails("let a = 1;\nlet b = 2;", 2, 5, /noch 1/, { slotsAvailable: 1 });
  const huge = compile(`const big = new Array(${LIMITS.arrayLength});\nlet one = 1;\nlet two = 2;`, { slotsAvailable: 100000 });
  assert.equal(huge.ok, false);
  assert.match(huge.errors[0].message, /höchstens 65536 je Plugin/);
  assert.equal(compile(`const big = new Array(${LIMITS.arrayLength});\nlet one = 1;`, { slotsAvailable: 100000 }).ok, true, "65535 + 1 is the whole variable area");
  const strings = Array.from({ length: LIMITS.strings + 1 }, (_, i) => `const s${i} = "t${i}";\nlet u${i} = s${i} == "t${i}";`).join("\n");
  const e = compile(strings);
  assert.equal(e.ok, false);
  assert.match(e.errors[0].message, /Zu viele verschiedene Texte/);
  const big = `let x = 0;\n${Array.from({ length: LIMITS.consts + 1 }, (_, i) => `x = ${100000 + i};`).join("\n")}`;
  const c = compile(big);
  assert.equal(c.ok, false);
  assert.match(c.errors[0].message, /Zu viele verschiedene große oder negative Zahlen/);
  fails(`let s = "${"x".repeat(32)}";`, 1, 9, /zu lang \(32 Zeichen, höchstens 31\)/);
  assert.ok(compile(`let s = "${"x".repeat(31)}";`).ok);
  const deep = `let a = 1;\nlet r = ${"a + (".repeat(LIMITS.stack + 2)}a${")".repeat(LIMITS.stack + 2)};`;
  const d = compile(deep);
  assert.equal(d.ok, false);
  assert.match(d.errors[0].message, /Stapel/);
  const chain = Array.from({ length: LIMITS.callDepth + 1 }, (_, i) => `function f${i}() { ${i + 1 <= LIMITS.callDepth ? `return f${i + 1}();` : "return 0;"} }`).join("\n") + "\nlet r = f0();";
  const cd = compile(chain);
  assert.equal(cd.ok, false);
  assert.match(cd.errors[0].message, /Aufrufe zu tief/);
  const code = `let x = 0;\n${"x = x * 3 + 7 / (x + 1);\n".repeat(1200)}`;
  const big2 = compile(code);
  assert.equal(big2.ok, false);
  assert.match(big2.errors[0].message, /zu groß/);
});

test("a successful variable precheck does not promise room for the blob and entry", () => {
  const r = compile(`const big = new Array(${BUDGET.variableSlots});`);
  assert.ok(r.ok, r.errors?.map(formatError).join("\n"));
  assert.equal(r.info.vars, BUDGET.scriptBytes / 4);
  const rt = new ScriptRuntime({ now: () => 0 });
  const loaded = rt.add(r.blob);
  assert.equal(loaded.ok, false);
  assert.equal(loaded.error.name, "POOL_BUDGET");
  assert.equal(rt.bytesUsed, 0);
});

test("tokens carry their lengths and positions", () => {
  const t = tokenize("let ab = \"x y\";\n  7");
  assert.deepEqual(t.map(x => [x.v, x.line, x.col, x.len]), [["let", 1, 1, 3], ["ab", 1, 5, 2], ["=", 1, 8, 1], ["x y", 1, 10, 5], [";", 1, 15, 1], [7, 2, 3, 1], ["", 2, 4, undefined]]);
});

test("the line table gives every statement its line", () => {
  const r = compile("let a = 1;\n\nfunction f() {\n  a += 1;\n  a += 2;\n}\n\nkorg.onEvent(\"frame\", () => {\n  f();\n});\n");
  assert.ok(r.ok);
  assert.deepEqual(r.info.lines.slice().sort((x, y) => x - y), [1, 4, 5, 8, 9]);
});
