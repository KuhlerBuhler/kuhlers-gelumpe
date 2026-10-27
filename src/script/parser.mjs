/**
 * Lexer and parser for the script language, a small subset of JavaScript.
 * Every error is a CompileError with a line, a column and a message for the
 * editor, a text of the table (src/text.mjs). The parser stops at the first one.
 */
import { LIMITS } from "../../data/script/contract.mjs";
import { UMLAUTS } from "../../data/script/font.mjs";
import { TextError, text } from "../text.mjs";

/** `message` is a text (src/text.mjs); a plain string is shown as it is. */
export class CompileError extends TextError {
  constructor(message, line = 1, column = 1) {
    super(typeof message === "string" ? message : message.key, typeof message === "string" ? undefined : message.vars);
    this.line = line;
    this.column = column;
  }
}

const KEYWORDS = new Set(["let", "const", "function", "if", "else", "while", "for", "break", "continue", "return", "true", "false", "new"]);

/** JavaScript words the language does not have, with the key of what to say instead; `{word}` is the word. */
const NOT_HERE = {
  var: "compile.notHere.var",
  class: "compile.notHere.class",
  switch: "compile.notHere.switch",
  case: "compile.notHere.switch",
  default: "compile.notHere.switch",
  do: "compile.notHere.do",
  try: "compile.notHere.exceptions",
  catch: "compile.notHere.exceptions",
  throw: "compile.notHere.exceptions",
  typeof: "compile.notHere.typeof",
  null: "compile.notHere.empty",
  undefined: "compile.notHere.empty",
  this: "compile.notHere.word",
  import: "compile.notHere.modules",
  export: "compile.notHere.modules",
  async: "compile.notHere.word",
  await: "compile.notHere.word",
  in: "compile.notHere.word",
  of: "compile.notHere.of",
  delete: "compile.notHere.word",
  void: "compile.notHere.word",
  yield: "compile.notHere.word",
  with: "compile.notHere.word",
  instanceof: "compile.notHere.word",
};

const PUNCT = [
  "<<=", ">>=", "===", "!==", ">>>", "**",
  "==", "!=", "<=", ">=", "&&", "||", "<<", ">>", "++", "--", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "=>",
  "+", "-", "*", "/", "%", "=", "<", ">", "!", "~", "&", "|", "^", "?", ":", ";", ",", ".", "(", ")", "{", "}", "[", "]",
];

const ASSIGN_OPS = new Set(["=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="]);

const BINARY_PRECEDENCE = {
  "||": 1, "&&": 2, "|": 3, "^": 4, "&": 5,
  "==": 6, "!=": 6, "===": 6, "!==": 6,
  "<": 7, ">": 7, "<=": 7, ">=": 7,
  "<<": 8, ">>": 8, "+": 9, "-": 9, "*": 10, "/": 10, "%": 10,
};

const isDigit = c => c >= "0" && c <= "9";
const isIdStart = c => /[A-Za-z_$]/.test(c);
const isIdPart = c => /[A-Za-z0-9_$]/.test(c);

export function tokenize(src) {
  const tokens = [];
  let i = 0;
  let line = 1;
  let col = 1;
  const adv = (n = 1) => {
    for (let k = 0; k < n; k++) {
      if (src[i] === "\n") { line += 1; col = 1; } else col += 1;
      i += 1;
    }
  };
  while (i < src.length) {
    const c = src[i];
    if (c === " " || c === "\t" || c === "\r" || c === "\n") { adv(); continue; }
    if (c === "/" && src[i + 1] === "/") { while (i < src.length && src[i] !== "\n") adv(); continue; }
    if (c === "/" && src[i + 1] === "*") {
      const l0 = line;
      const c0 = col;
      adv(2);
      while (i < src.length && !(src[i] === "*" && src[i + 1] === "/")) adv();
      if (i >= src.length) throw new CompileError(text("compile.comment.open"), l0, c0);
      adv(2);
      continue;
    }
    const at = { line, col };
    if (isDigit(c)) {
      let j = i;
      let value;
      if (c === "0" && (src[i + 1] === "x" || src[i + 1] === "X")) {
        j = i + 2;
        while (/[0-9a-fA-F]/.test(src[j] ?? "")) j += 1;
        if (j === i + 2) throw new CompileError(text("compile.number.hexEmpty"), at.line, at.col);
        value = parseInt(src.slice(i + 2, j), 16);
        if (value > 0xffffffff) throw new CompileError(text("compile.number.tooBigHex"), at.line, at.col);
        value |= 0;
      } else {
        while (isDigit(src[j] ?? "")) j += 1;
        value = Number(src.slice(i, j));
        if (value > 2147483647) throw new CompileError(text("compile.number.tooBig"), at.line, at.col);
      }
      if (src[j] === "." || src[j] === "e" || src[j] === "E") throw new CompileError(text("compile.number.fraction"), at.line, at.col);
      if (isIdStart(src[j] ?? "")) throw new CompileError(text("compile.number.letter"), at.line, at.col);
      tokens.push({ t: "num", v: value, len: j - i, ...at });
      adv(j - i);
      continue;
    }
    if (isIdStart(c)) {
      let j = i;
      while (isIdPart(src[j] ?? "")) j += 1;
      const word = src.slice(i, j);
      if (NOT_HERE[word]) throw new CompileError(text(NOT_HERE[word], { word }), at.line, at.col);
      tokens.push({ t: KEYWORDS.has(word) ? "kw" : "id", v: word, len: word.length, ...at });
      adv(j - i);
      continue;
    }
    if (c === '"' || c === "'") {
      let value = "";
      let j = i + 1;
      for (;;) {
        const d = src[j];
        if (d === undefined || d === "\n") throw new CompileError(text("compile.string.open"), at.line, at.col);
        if (d === c) break;
        if (d === "\\") {
          const e = src[j + 1];
          if (e !== "\\" && e !== '"' && e !== "'") throw new CompileError(text("compile.string.escape"), at.line, at.col + (j - i));
          value += e;
          j += 2;
          continue;
        }
        if ((d < " " || d > "~") && !(d in UMLAUTS)) throw new CompileError(text("compile.string.ascii"), at.line, at.col + (j - i));
        value += d;
        j += 1;
      }
      if (value.length > LIMITS.stringLength) throw new CompileError(text("compile.string.long", { length: value.length, max: LIMITS.stringLength }), at.line, at.col);
      tokens.push({ t: "str", v: value, len: j + 1 - i, ...at });
      adv(j + 1 - i);
      continue;
    }
    if (c === "`") throw new CompileError(text("compile.string.template"), at.line, at.col);
    const p = PUNCT.find(x => src.startsWith(x, i));
    if (!p) throw new CompileError(text("compile.char", { char: c }), at.line, at.col);
    if (p === ">>>" || p === "**") throw new CompileError(text("compile.notHere.word", { word: p }), at.line, at.col);
    tokens.push({ t: "p", v: p, len: p.length, ...at });
    adv(p.length);
  }
  tokens.push({ t: "eof", v: "", line, col });
  return tokens;
}

const describe = tok => (tok.t === "eof" ? text("compile.token.end") : text("compile.token.quoted", { token: tok.v }));

class Parser {
  constructor(tokens) {
    this.tokens = tokens;
    this.pos = 0;
  }

  get tok() { return this.tokens[this.pos]; }

  peek(k = 1) { return this.tokens[Math.min(this.pos + k, this.tokens.length - 1)]; }

  next() { return this.tokens[this.pos++]; }

  is(v) { return (this.tok.t === "p" || this.tok.t === "kw") && this.tok.v === v; }

  eat(v) {
    if (!this.is(v)) return false;
    this.pos += 1;
    return true;
  }

  fail(message, tok = this.tok) { throw new CompileError(message, tok.line, tok.col); }

  expect(v) {
    if (this.is(v)) return this.next();
    const hint = this.is("=") ? text("compile.expect.assignHint") : "";
    if (this.is("++") || this.is("--")) return this.fail(text("compile.incDec.expression"));
    const prev = this.tokens[this.pos - 1];
    if (v === ";" && prev && prev.line < this.tok.line) return this.fail(text("compile.expect.semicolon"), { line: prev.line, col: prev.col + prev.len });
    return this.fail(text("compile.expect.missing", { token: v, found: describe(this.tok), hint }));
  }

  ident(what = text("compile.expect.name")) {
    if (this.tok.t !== "id") this.fail(text("compile.expect.wanted", { what, found: describe(this.tok) }));
    return this.next();
  }

  program() {
    const body = [];
    while (this.tok.t !== "eof") body.push(this.statement(true));
    return { type: "Program", body };
  }

  block() {
    const open = this.expect("{");
    const body = [];
    while (!this.is("}")) {
      if (this.tok.t === "eof") this.fail(text("compile.block.open"), open);
      body.push(this.statement(false));
    }
    this.next();
    return { type: "Block", body, line: open.line, col: open.col };
  }

  statement(top) {
    const t = this.tok;
    const at = { line: t.line, col: t.col };
    if (t.t === "kw") {
      switch (t.v) {
        case "function": {
          if (!top) this.fail(text("compile.func.nested"));
          this.next();
          const name = this.ident(text("compile.expect.funcName"));
          return { type: "Func", name: name.v, params: this.params(), body: this.block(), ...at };
        }
        case "let": case "const": {
          const s = this.declaration();
          this.expect(";");
          return s;
        }
        case "if": {
          this.next();
          this.expect("(");
          const cond = this.expression();
          this.expect(")");
          const then = this.statement(false);
          const other = this.eat("else") ? this.statement(false) : null;
          return { type: "If", cond, then, other, ...at };
        }
        case "while": {
          this.next();
          this.expect("(");
          const cond = this.expression();
          this.expect(")");
          return { type: "While", cond, body: this.statement(false), ...at };
        }
        case "for": return this.forStatement(at);
        case "break": case "continue": {
          this.next();
          this.expect(";");
          return { type: t.v === "break" ? "Break" : "Continue", ...at };
        }
        case "return": {
          this.next();
          const value = this.is(";") ? null : this.expression();
          this.expect(";");
          return { type: "Return", value, ...at };
        }
        case "else": return this.fail(text("compile.else"));
        default: break;
      }
    }
    if (this.is("{")) return this.block();
    if (this.eat(";")) return { type: "Block", body: [], ...at };
    const s = this.simple();
    this.expect(";");
    return s;
  }

  params() {
    this.expect("(");
    const list = [];
    if (!this.is(")")) {
      do {
        const p = this.ident(text("compile.expect.param"));
        list.push({ name: p.v, line: p.line, col: p.col });
      } while (this.eat(","));
    }
    this.expect(")");
    return list;
  }

  declaration() {
    const kw = this.next();
    const decls = [];
    do {
      const name = this.ident();
      let init = null;
      if (this.eat("=")) init = this.expression();
      else if (kw.v === "const") this.fail(text("compile.const.value", { name: name.v }), name);
      decls.push({ name: name.v, init, line: name.line, col: name.col });
    } while (this.eat(","));
    return { type: "Let", kind: kw.v, decls, line: kw.line, col: kw.col };
  }

  forStatement(at) {
    this.next();
    this.expect("(");
    let init = null;
    if (this.is("let") || this.is("const")) init = this.declaration();
    else if (!this.is(";")) init = this.simple();
    this.expect(";");
    const cond = this.is(";") ? null : this.expression();
    this.expect(";");
    const update = this.is(")") ? null : this.simple();
    this.expect(")");
    return { type: "For", init, cond, update, body: this.statement(false), ...at };
  }

  /** An assignment, an increment or a call, without its closing semicolon. */
  simple() {
    const t = this.tok;
    const at = { line: t.line, col: t.col };
    if (this.is("++") || this.is("--")) {
      this.next();
      const target = this.postfix();
      this.checkTarget(target);
      return { type: "IncDec", op: t.v, target, ...at };
    }
    const e = this.expression();
    if (this.tok.t === "p" && ASSIGN_OPS.has(this.tok.v)) {
      const op = this.next().v;
      this.checkTarget(e, text("compile.assign.target", { op }));
      return { type: "Assign", op, target: e, value: this.expression(), ...at };
    }
    if (this.is("++") || this.is("--")) {
      const op = this.next().v;
      this.checkTarget(e);
      return { type: "IncDec", op, target: e, ...at };
    }
    if (e.type !== "Call") throw new CompileError(text("compile.statement"), e.line, e.col);
    return { type: "ExprStmt", expr: e, ...at };
  }

  checkTarget(e, message = text("compile.incDec.target")) {
    if (e.type !== "Ident" && e.type !== "Index" && e.type !== "Member") throw new CompileError(message, e.line, e.col);
  }

  expression() { return this.ternary(); }

  ternary() {
    const test = this.binary(1);
    if (!this.is("?")) return test;
    this.next();
    const a = this.ternary();
    this.expect(":");
    const b = this.ternary();
    return { type: "Cond", test, a, b, line: test.line, col: test.col };
  }

  binary(min) {
    let left = this.unary();
    for (;;) {
      const op = this.tok.t === "p" ? this.tok.v : null;
      const prec = op ? BINARY_PRECEDENCE[op] : undefined;
      if (prec === undefined || prec < min) return left;
      this.next();
      const right = this.binary(prec + 1);
      left = { type: op === "&&" || op === "||" ? "Logical" : "Binary", op, left, right, line: left.line, col: left.col };
    }
  }

  unary() {
    const t = this.tok;
    if (t.t === "p" && (t.v === "-" || t.v === "!" || t.v === "~")) {
      this.next();
      return { type: "Unary", op: t.v, arg: this.unary(), line: t.line, col: t.col };
    }
    if (t.t === "p" && (t.v === "++" || t.v === "--")) this.fail(text("compile.incDec.expression"));
    if (t.t === "p" && t.v === "+") this.fail(text("compile.plus"));
    return this.postfix();
  }

  postfix() {
    let e = this.primary();
    for (;;) {
      if (this.is(".")) {
        this.next();
        const name = this.ident(text("compile.expect.member"));
        e = { type: "Member", object: e, name: name.v, line: e.line, col: e.col };
      } else if (this.is("[")) {
        this.next();
        const index = this.expression();
        this.expect("]");
        e = { type: "Index", object: e, index, line: e.line, col: e.col };
      } else if (this.is("(")) {
        this.next();
        const args = [];
        if (!this.is(")")) {
          do args.push(this.expression()); while (this.eat(","));
        }
        this.expect(")");
        e = { type: "Call", callee: e, args, line: e.line, col: e.col };
      } else return e;
    }
  }

  arrowAhead() {
    if (this.tok.t === "id" && this.peek().v === "=>" && this.peek().t === "p") return true;
    if (!this.is("(")) return false;
    let depth = 0;
    for (let k = this.pos; k < this.tokens.length; k++) {
      const x = this.tokens[k];
      if (x.t === "p" && x.v === "(") depth += 1;
      if (x.t === "p" && x.v === ")") {
        depth -= 1;
        if (depth === 0) return this.tokens[k + 1].t === "p" && this.tokens[k + 1].v === "=>";
      }
    }
    return false;
  }

  primary() {
    const t = this.tok;
    const at = { line: t.line, col: t.col };
    if (t.t === "num") { this.next(); return { type: "Num", value: t.v, ...at }; }
    if (t.t === "str") { this.next(); return { type: "Str", value: t.v, ...at }; }
    if (t.t === "kw" && (t.v === "true" || t.v === "false")) { this.next(); return { type: "Num", value: t.v === "true" ? 1 : 0, ...at }; }
    if (t.t === "kw" && t.v === "function") {
      this.next();
      return { type: "FuncExpr", params: this.params(), body: this.block(), ...at };
    }
    if (this.arrowAhead()) {
      let params = null;
      if (this.tok.t === "id") { params = [{ name: t.v, line: t.line, col: t.col }]; this.next(); } else params = this.params();
      this.expect("=>");
      if (this.is("{")) return { type: "FuncExpr", params, body: this.block(), ...at };
      const body = this.expression();
      if (body.type !== "Call") throw new CompileError(text("compile.arrow.body"), body.line, body.col);
      return { type: "FuncExpr", params, body: { type: "Block", body: [{ type: "ExprStmt", expr: body, line: body.line, col: body.col }], line: body.line, col: body.col }, ...at };
    }
    if (t.t === "kw" && t.v === "new") {
      this.next();
      const cls = this.ident(text("compile.expect.array"));
      if (cls.v !== "Array") this.fail(text("compile.new"), cls);
      this.expect("(");
      const size = this.expression();
      this.expect(")");
      return { type: "NewArray", size, ...at };
    }
    if (t.t === "id") { this.next(); return { type: "Ident", name: t.v, ...at }; }
    if (this.is("(")) {
      this.next();
      const e = this.expression();
      this.expect(")");
      return e;
    }
    if (this.is("[")) {
      this.next();
      const items = [];
      if (!this.is("]")) {
        do items.push(this.expression()); while (this.eat(","));
      }
      this.expect("]");
      return { type: "ArrayLit", items, ...at };
    }
    return this.fail(text("compile.expect.value", { found: describe(t) }));
  }
}

export function parse(source) {
  return new Parser(tokenize(source)).program();
}
