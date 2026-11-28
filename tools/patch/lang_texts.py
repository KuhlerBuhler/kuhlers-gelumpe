# SPDX-License-Identifier: GPL-2.0-only
"""Texts of the BLECH menu that the optional patch lang-de can replace (docs/firmware-sprache.md).

Every string in data/lang/de/blech.json with a `text`, and every table of string pointers holding one, gets a number.
Each `ldr rX, =label` of those is rewritten to load the label's address from the text table that LANG_TEXTS points at:
the runtime's own English table, or the German table of lang-de when its header at LANG matches this runtime.
"""

import hashlib
import json
import re
from pathlib import Path

BLECH_JSON = Path(__file__).resolve().parents[2] / 'data' / 'lang' / 'de' / 'blech.json'
LABEL = re.compile(r'^\s*([A-Za-z_]\w*):', re.M)
STRING = re.compile(r'^[ \t]*([A-Za-z_]\w*):[ \t]*(?:;[^\n]*)?(?:\n\s*)?\.asciz\s+"(.*)"', re.M)
LDR = re.compile(r'^(\s*)(ldr(?:eq|ne|cs|hs|cc|lo|mi|pl|vs|vc|hi|ls|ge|lt|gt|le|al)?)\s+(\w+)\s*,\s*=\s*([A-Za-z_]\w*)\s*$')


class LangError(ValueError):
    pass


def entries(path=BLECH_JSON):
    return json.loads(Path(path).read_text('utf8'))['texts']


def strings(source):
    """{label: text} of the labelled .asciz strings of a source."""
    return {m.group(1): m.group(2) for m in STRING.finditer(source)}


def tables(source, labels):
    """{label: [string labels]} of the labelled blocks that are only .word lines naming strings of `labels`."""
    out = {}
    own = strings(source)
    lines = source.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r'^\s*([A-Za-z_]\w*):\s*(.*)$', line.split(';')[0])
        if not m:
            continue
        names, rest, j = [], m.group(2).strip(), i
        while True:
            if rest:
                w = re.match(r'^\.word\s+(.*)$', rest)
                if not w:
                    break
                names += [n.strip() for n in w.group(1).split(',')]
            j += 1
            if j >= len(lines):
                break
            rest = lines[j].split(';')[0].strip()
            if not rest.startswith('.word'):
                break
        if names and any(n in labels for n in names) and all(n in own for n in names):
            out[m.group(1)] = names
    return out


def index(source, texts):
    """The numbered labels: the strings with a German text and the tables that hold one, sorted for stable numbers."""
    own = strings(source)
    missing = sorted(set(own) - set(texts))
    if missing:
        raise LangError(f'data/lang/de/blech.json lacks {len(missing)} label(s), each needs text or keep: {" ".join(missing)}')
    translated = {k for k in own if 'text' in texts[k]}
    return sorted(translated | set(tables(source, translated)))


def key(labels):
    """The word lang-de's header must carry for this numbering."""
    return int.from_bytes(hashlib.sha256('\n'.join(labels).encode()).digest()[:4], 'little')


def rewrite(source, labels):
    """`source` with each `ldr rX, =label` of `labels` loading through the text table. A .word naming one keeps the English
    address (the tables are numbered themselves); any other use is refused."""
    number = {name: n for n, name in enumerate(labels)}
    out = []
    for raw in source.splitlines():
        code = raw.split(';')[0]
        m = LDR.match(code)
        if m and m.group(4) in number:
            pad, op, reg, name = m.groups()
            out += [f'{pad}{op} {reg}, =LANG_TEXTS', f'{pad}{op} {reg}, [{reg}]', f'{pad}{op} {reg}, [{reg}, #{4 * number[name]}]']
            continue
        used = set(re.findall(r'[A-Za-z_]\w*', re.sub(r'"[^"]*"', '', code))) & set(number)
        label = LABEL.match(code)
        if label:
            used.discard(label.group(1))
        if used and not code.strip().startswith('.word'):
            raise LangError(f'{" ".join(sorted(used))} is used other than by ldr =label: {raw.strip()}')
        out.append(raw)
    return '\n'.join(out)


def runtime_source(labels):
    """The English text table, LANG_COUNT and LANG_KEY, and lang_arm, which points LANG_TEXTS at a table."""
    words = ''.join(f'\n    .word {name}' for name in labels)
    return f'''
.equ LANG_COUNT, {len(labels)}
.equ LANG_KEY, {key(labels):#x}
; Points LANG_TEXTS at the German table of lang-de when its header at LANG (table, count, key) matches this runtime,
; else at the English table. Clobbers r0 to r2.
lang_arm:
    ldr r0, =LANG
    ldr r1, [r0, #4]
    ldr r2, =LANG_COUNT
    cmp r1, r2
    ldreq r1, [r0, #8]
    ldreq r2, =LANG_KEY
    cmpeq r1, r2
    ldreq r1, [r0]
    ldrne r1, =lang_en_table
    ldr r0, =LANG_TEXTS
    str r1, [r0]
    bx lr
.pool
.align 4
lang_en_table:{words}
lang_end:
'''
