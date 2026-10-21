// Taken from hardtekkhub (extensions/flarum-theme-hub/js/design-check/structureCheck.mjs).
// Verifies FORUM_COMPONENTS' `tree` contracts: a node is {tag?, classes, optional?, repeatable?,
// children?}, or an array of such nodes for a root with multiple legal shapes (NavCategory's
// link/toggle/toggleGroup variants). `children` matches direct children in order, skipping over
// elements the contract doesn't mention -- it checks nesting and order, not an exhaustive whitelist.

function describeNode(node) {
    const tag = node.tag ? `<${node.tag}>` : '<*>';
    const id = node.id ? `#${node.id}` : '';
    return `${tag}${id}.${node.classes.join('.')}`;
}

function classesMatch(actual, expected) {
    return expected.classes.every((className) => actual.classes.includes(className));
}

function tagMatches(actual, expected) {
    return !expected.tag || actual.tag === expected.tag.toLowerCase();
}

function idMatches(actual, expected) {
    return !expected.id || actual.id === expected.id;
}

function nodeMatches(actual, expected) {
    return !!actual && tagMatches(actual, expected) && idMatches(actual, expected) && classesMatch(actual, expected);
}

function matchChildren(actualChildren, expectedChildren, componentId, parentDescription) {
    let cursor = 0;

    for (const expected of expectedChildren) {
        let matchedOnce = false;

        if (expected.repeatable) {
            while (cursor < actualChildren.length && nodeMatches(actualChildren[cursor], expected)) {
                const nested = expected.children
                    ? matchChildren(actualChildren[cursor].children, expected.children, componentId, describeNode(expected))
                    : { ok: true };
                if (!nested.ok) return nested;
                cursor++;
                matchedOnce = true;
            }
            if (!matchedOnce && !expected.optional) {
                return { ok: false, reason: `${componentId}: expected at least one ${describeNode(expected)} inside ${parentDescription}, found none` };
            }
            continue;
        }

        const searchStart = cursor;
        while (cursor < actualChildren.length && !nodeMatches(actualChildren[cursor], expected)) cursor++;

        if (cursor >= actualChildren.length) {
            if (expected.optional) {
                cursor = searchStart;
                continue;
            }
            return { ok: false, reason: `${componentId}: expected direct child ${describeNode(expected)} inside ${parentDescription}, not found (or found out of order)` };
        }

        if (expected.children) {
            const nested = matchChildren(actualChildren[cursor].children, expected.children, componentId, describeNode(expected));
            if (!nested.ok) return nested;
        }
        cursor++;
    }

    return { ok: true };
}

function matchTree(actualRoot, expected, componentId) {
    if (!nodeMatches(actualRoot, expected)) {
        return { ok: false, reason: `${componentId}: root does not match ${describeNode(expected)} (got ${describeNode(actualRoot)})` };
    }
    if (!expected.children) return { ok: true };
    return matchChildren(actualRoot.children, expected.children, componentId, describeNode(expected));
}

export function matchComponentTree(actualRoot, expected, componentId) {
    const variants = Array.isArray(expected) ? expected : [expected];
    const failures = [];

    for (const variant of variants) {
        const result = matchTree(actualRoot, variant, componentId);
        if (result.ok) return result;
        failures.push(result.reason);
    }

    return { ok: false, reason: failures.length > 1 ? `${componentId}: matched none of ${failures.length} known variants (${failures.join(' | ')})` : failures[0] };
}

// Runs in the browser (via page.evaluate) to turn a live DOM subtree into the plain-object shape
// matchComponentTree expects. Exported as source text since page.evaluate can't import modules.
// Runs inside the page via elementHandle.evaluate -- must be a plain, self-contained function
// (no closures over outer scope) since Playwright serializes it to source and re-parses it there.
export function serializeSubtree(el, depth) {
    if (!el || depth < 0) return null;
    return {
        tag: el.tagName.toLowerCase(),
        id: el.id || '',
        classes: Array.from(el.classList),
        children: Array.from(el.children).map((c) => serializeSubtree(c, depth - 1)),
    };
}
