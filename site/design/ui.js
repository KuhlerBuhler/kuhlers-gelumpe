// Verhalten der geteilten ui-*-Komponenten (root.min.css). Global per replyToReq eingebunden.
// Nur ueber window.ui ansprechen: einige Apps haben ein eigenes, gleichnamiges `ui`.
// Beim Laden nur delegierte Listener und die Startwerte vorhandener Slider. Referenz: /designsystem.
(function () {
    const api = (window.ui = window.ui || {});
    if (api.__init) return;
    api.__init = true;

    // ---------- Laufender Knopf ----------
    // aria-busy zeigt den Kreis aus root.min.css, disabled verhindert den zweiten Klick.
    api.busy = function (el, on = true) {
        if (!el) return;
        if (on) el.setAttribute('aria-busy', 'true');
        else el.removeAttribute('aria-busy');
        if ('disabled' in el) el.disabled = !!on;
    };

    // ---------- Einblenden beim Scrollen ----------
    // Bloecke, die beim Hinzufuegen unterhalb des Sichtbereichs liegen, warten unsichtbar und
    // blenden ein, sobald sie hineinlaufen. Sichtbares bleibt unmarkiert: neu gerenderte Listen
    // (Polling) flackern dadurch nicht.
    const REVEAL = ':where(.ui-page) > *, :where(.ui-section) > :not(.ui-section-head), :where(.ui-list) > li, :where(.grid) > *';
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    let revealObserver = null;

    function revealIn(el, delay) {
        el.style.setProperty('--reveal-delay', `${delay}ms`);
        el.dataset.uiReveal = 'in';
        const done = () => {
            el.removeAttribute('data-ui-reveal');
            el.style.removeProperty('--reveal-delay');
        };
        el.addEventListener('transitionend', done, { once: true });
        setTimeout(done, 1000);
    }

    // Erst alle Positionen lesen, dann markieren: abwechselnd lesen und schreiben wuerde bei
    // langen Listen fuer jede Zeile ein neues Layout erzwingen.
    function scanReveal(root) {
        if (!revealObserver || root.nodeType !== 1) return;
        const found = root.matches(REVEAL) ? [root] : [];
        found.push(...root.querySelectorAll(REVEAL));
        const below = found.filter((el) => {
            if (el.dataset.uiReveal || el.closest('dialog, [data-no-reveal]')) return false;
            const box = el.getBoundingClientRect();
            return box.height > 0 && box.top >= window.innerHeight;
        });
        for (const el of below) {
            el.dataset.uiReveal = 'wait';
            revealObserver.observe(el);
        }
    }

    function initReveal() {
        if (!('IntersectionObserver' in window) || reduceMotion?.matches) return;
        const page = document.querySelector('main.ui-page');
        if (!page) return;
        revealObserver = new IntersectionObserver((entries) => {
            const incoming = entries.filter((e) => e.isIntersecting).map((e) => e.target);
            incoming.forEach((el, i) => {
                revealObserver.unobserve(el);
                revealIn(el, Math.min(i, 5) * 40);
            });
        }, { rootMargin: '0px 0px -8% 0px' });
        scanReveal(page);
        new MutationObserver((records) => {
            for (const r of records) r.addedNodes.forEach(scanReveal);
        }).observe(page, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initReveal, { once: true });
    else initReveal();

    // ---------- Split: Seitenleiste mobil auf- und zuklappen ----------
    document.addEventListener('click', (e) => {
        const toggle = e.target.closest('.ui-split-toggle');
        const split = toggle?.closest('.ui-split');
        if (!split) return;
        const open = !split.hasAttribute('data-open');
        split.toggleAttribute('data-open', open);
        toggle.setAttribute('aria-expanded', String(open));
    });

    // ---------- Dialog ----------
    const openers = new WeakMap();

    function restoreFocus(dialog) {
        const opener = openers.get(dialog);
        openers.delete(dialog);
        const target = opener?.isConnected ? opener : document.querySelector('main, [role="main"]') || document.body;
        if (target !== opener && !target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
        target.focus?.({ preventScroll: true });
    }

    api.openDialog = function (dialog) {
        if (typeof dialog === 'string') dialog = document.getElementById(dialog);
        if (!dialog || dialog.open) return dialog;
        openers.set(dialog, document.activeElement);
        dialog.returnValue = '';
        dialog.showModal();
        document.documentElement.classList.add('ui-dialog-lock');
        return dialog;
    };

    api.closeDialog = function (dialog, value = '') {
        if (typeof dialog === 'string') dialog = document.getElementById(dialog);
        if (dialog?.open) dialog.close(value);
    };

    // close feuert fuer close(), Escape und <form method="dialog"> gleichermassen.
    document.addEventListener('close', (e) => {
        const dialog = e.target;
        if (!(dialog instanceof HTMLDialogElement) || !dialog.classList.contains('ui-dialog')) return;
        if (!document.querySelector('dialog.ui-dialog[open]')) document.documentElement.classList.remove('ui-dialog-lock');
        restoreFocus(dialog);
    }, true);

    // Klick auf den Hintergrund landet auf dem <dialog> selbst. Nur schliessen, wenn auch der
    // Druck dort begann: sonst schliesst Text-Markieren mit Loslassen ausserhalb den Dialog.
    let downOnBackdrop = false;
    document.addEventListener('pointerdown', (e) => {
        downOnBackdrop = e.target instanceof HTMLDialogElement && e.target.classList.contains('ui-dialog');
    }, true);
    document.addEventListener('click', (e) => {
        const dialog = e.target;
        if (downOnBackdrop && dialog instanceof HTMLDialogElement && dialog.classList.contains('ui-dialog')
            && dialog.open && !dialog.hasAttribute('data-ui-static')) {
            dialog.close('cancel');
        }
        downOnBackdrop = false;
    });

    document.addEventListener('click', (e) => {
        const open = e.target.closest('[data-ui-dialog-open]');
        if (open) { e.preventDefault(); api.openDialog(open.getAttribute('data-ui-dialog-open')); return; }
        const close = e.target.closest('[data-ui-dialog-close]');
        if (close) { e.preventDefault(); api.closeDialog(close.closest('dialog'), close.value || 'cancel'); }
    });

    let seq = 0;
    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    function buildDialog({ title, text, danger, confirmLabel, cancelLabel, field }) {
        const id = `ui-dlg-${++seq}`;
        const dialog = document.createElement('dialog');
        dialog.className = 'ui-dialog ui-dialog-narrow';
        dialog.setAttribute('aria-labelledby', `${id}-title`);
        if (text) dialog.setAttribute('aria-describedby', `${id}-text`);
        // Bei gefaehrlichen Aktionen bekommt Abbrechen den ersten Fokus, damit Enter nichts loescht.
        const cancelFocus = danger && !field ? ' autofocus' : '';
        const confirmFocus = !danger && !field ? ' autofocus' : '';
        dialog.innerHTML = `
            <form method="dialog" class="ui-dialog-box">
                <header class="ui-dialog-head"><h2 class="ui-dialog-title" id="${id}-title">${esc(title)}</h2></header>
                <div class="ui-dialog-body">
                    ${text ? `<p class="ui-dialog-text" id="${id}-text">${esc(text)}</p>` : ''}
                    ${field ? `<div class="ui-field">
                        ${field.label ? `<label class="ui-field-label" for="${id}-input">${esc(field.label)}</label>` : ''}
                        <input class="input" id="${id}-input" name="value" autocomplete="off" autofocus
                            value="${esc(field.value)}" placeholder="${esc(field.placeholder)}"${field.label ? '' : ` aria-label="${esc(title)}"`}>
                    </div>` : ''}
                </div>
                <footer class="ui-dialog-foot">
                    <button type="submit" class="btn" value="cancel" formnovalidate${cancelFocus}>${esc(cancelLabel)}</button>
                    <button type="submit" class="btn ${danger ? 'danger' : 'primary'}" value="ok"${confirmFocus}>${esc(confirmLabel)}</button>
                </footer>
            </form>`;
        // Enter wuerde sonst den ersten Knopf im Formular ausloesen, und das ist Abbrechen.
        dialog.querySelector('input')?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); dialog.close('ok'); }
        });
        document.body.appendChild(dialog);
        return dialog;
    }

    function ask(opts, read) {
        return new Promise((resolve) => {
            const dialog = buildDialog(opts);
            let settled = false;
            dialog.addEventListener('close', () => {
                if (settled) return;
                settled = true;
                resolve(read(dialog));
                setTimeout(() => dialog.remove(), 0);
            }, { once: true });
            api.openDialog(dialog);
        });
    }

    // Ersatz fuer confirm(): liefert true nur bei Bestaetigen, false bei Abbrechen, Escape, Hintergrund.
    api.confirm = (opts = {}) => ask({
        title: opts.title || 'Sicher?',
        text: opts.text,
        danger: !!opts.danger,
        confirmLabel: opts.confirmLabel || (opts.danger ? 'Löschen' : 'Bestätigen'),
        cancelLabel: opts.cancelLabel || 'Abbrechen',
    }, (d) => d.returnValue === 'ok');

    // Ersatz fuer prompt(): liefert den Text bei Bestaetigen, sonst null.
    api.prompt = (opts = {}) => ask({
        title: opts.title || 'Eingabe',
        text: opts.text,
        confirmLabel: opts.confirmLabel || 'Übernehmen',
        cancelLabel: opts.cancelLabel || 'Abbrechen',
        field: { label: opts.label, value: opts.value ?? '', placeholder: opts.placeholder ?? '' },
    }, (d) => (d.returnValue === 'ok' ? d.querySelector('input').value : null));

    // ---------- Zustaende ----------
    // Fuellt container mit Leer-, Lade- oder Fehlerzustand. action: { label, onClick } oder bei
    // Fehlern retry: fn (ergibt "Erneut versuchen"). Liefert das erzeugte Element.
    // toggleAttribute setzte aria-busy="", und leer zaehlt als false: der Ladezustand wurde nie angesagt.
    const setBusy = (el, busy) => (busy ? el.setAttribute('aria-busy', 'true') : el.removeAttribute('aria-busy'));

    api.state = function (container, { kind = 'empty', text = '', icon, action, retry, rows = 3, silent = false } = {}) {
        if (typeof container === 'string') container = document.getElementById(container);
        if (!container) return null;
        const box = document.createElement('div');
        box.className = 'ui-state';
        box.dataset.kind = kind;
        setBusy(container, kind === 'loading');
        const hadFocus = container.contains(document.activeElement);
        if (kind === 'loading') {
            if (!silent) box.setAttribute('role', 'status');
            box.appendChild(Object.assign(document.createElement('span'), { className: 'ui-sr-only', textContent: text || 'Lädt …' }));
            for (let i = 0; i < rows; i++) box.appendChild(Object.assign(document.createElement('span'), { className: 'ui-skeleton', ariaHidden: 'true' }));
        } else {
            if (kind === 'error' && !silent) box.setAttribute('role', 'alert');
            if (icon) {
                const i = document.createElement('i');
                i.className = 'ui-state-icon';
                i.setAttribute('data-lucide', icon);
                box.appendChild(i);
            }
            box.appendChild(Object.assign(document.createElement('p'), { className: 'ui-state-text', textContent: text }));
            const act = retry ? { label: 'Erneut versuchen', onClick: retry } : action;
            if (act) {
                const wrap = document.createElement('div');
                wrap.className = 'ui-state-actions';
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'btn sm';
                btn.textContent = act.label;
                btn.addEventListener('click', act.onClick);
                wrap.appendChild(btn);
                box.appendChild(wrap);
            }
        }
        container.replaceChildren(box);
        if (icon) window.lucide?.createIcons?.();
        // Der fokussierte Knopf (z. B. "Erneut versuchen") ist weg: Fokus auf den neuen Knopf oder die
        // Ueberschrift des Abschnitts, nicht auf <body>.
        if (hadFocus && !container.contains(document.activeElement)) {
            const target = box.querySelector('button')
                || container.closest('section, .ui-section, .panel')?.querySelector('h1, h2, h3, .ui-section-title');
            if (target) { if (!target.matches('button')) target.tabIndex = -1; target.focus({ preventScroll: true }); }
        }
        return box;
    };

    // ---------- Diagramme ----------
    // Legt Leer-, Lade- oder Fehlerzustand ueber die Flaeche einer .ui-chart; null blendet ihn aus.
    // Gleiche Optionen wie ui.state. Der aktuelle Zustand steht in .ui-chart-body[data-state].
    api.chartState = function (chart, opts) {
        if (typeof chart === 'string') chart = document.getElementById(chart);
        const body = chart?.querySelector('.ui-chart-body');
        if (!body) return null;
        let layer = body.querySelector(':scope > .ui-chart-state');
        if (!layer) {
            layer = document.createElement('div');
            layer.className = 'ui-chart-state';
            body.appendChild(layer);
        }
        const hadFocus = layer.contains(document.activeElement);
        let box = null;
        if (!opts) {
            layer.hidden = true;
            layer.replaceChildren();
            layer.removeAttribute('aria-busy');
            delete body.dataset.state;
        } else {
            layer.hidden = false;
            box = api.state(layer, { rows: 4, ...opts });
            body.dataset.state = opts.kind || 'empty';
        }
        setBusy(body, opts?.kind === 'loading');
        // Der Knopf im alten Zustand ist weg; Fokus auf den Diagrammtitel statt auf <body>.
        if (hadFocus && !layer.contains(document.activeElement)) {
            const title = chart.querySelector('.ui-chart-title');
            if (title) { title.tabIndex = -1; title.focus({ preventScroll: true }); }
        }
        return box;
    };

    // ---------- Chips ----------
    // Chips mit aria-pressed schalten beim Klick um; in .ui-chipgroup[data-ui-single] ist hoechstens
    // einer aktiv, mit data-ui-required genau einer. Jede Aenderung feuert 'ui:toggle' (bubbelt).
    const setPressed = (chip, pressed) => {
        chip.setAttribute('aria-pressed', String(pressed));
        chip.dispatchEvent(new CustomEvent('ui:toggle', { bubbles: true, detail: { pressed } }));
    };
    document.addEventListener('click', (e) => {
        const chip = e.target.closest('.ui-chip[aria-pressed]');
        if (!chip) return;
        if (chip.form && chip.type === 'submit') e.preventDefault();
        if (chip.disabled || chip.getAttribute('aria-disabled') === 'true') return;
        const pressed = chip.getAttribute('aria-pressed') !== 'true';
        const group = chip.closest('.ui-chipgroup[data-ui-single]');
        if (group && !pressed && group.hasAttribute('data-ui-required')) return;
        if (group && pressed) {
            group.querySelectorAll('.ui-chip[aria-pressed="true"]').forEach((c) => { if (c !== chip) setPressed(c, false); });
        }
        setPressed(chip, pressed);
    });

    // ---------- Tabs ----------
    // ui.tabs(tablist, { onChange, persist }): tablist enthaelt role="tab"-Elemente mit data-tab="<id>"
    // und aria-controls auf ihr role="tabpanel"; nur das aktive Panel ist sichtbar. Pfeiltasten,
    // Home und End bewegen die Auswahl, tabindex wandert mit. persist ist ein localStorage-Schluessel;
    // der aktive Tab steht dann auch im URL-Hash (hash: false schaltet das ab).
    // Nur EINE Instanz je Seite darf den Hash nutzen; weitere bekommen hash: false. select(id, { persist: false })
    // schreibt weder Speicher noch Hash: steht im Hash ein anderer Tab, landet ein Neuladen auf diesem.
    // Jedes Panel bekommt tabindex="0", damit Tastaturnutzer auch in Panels ohne Fokusziel kommen.
    const tabsPick = (ids, { hash = '', stored = '' } = {}) => {
        const fromHash = String(hash).replace(/^#/, '');
        if (ids.includes(fromHash)) return fromHash;
        return ids.includes(stored) ? stored : ids[0];
    };
    const tabsKeyTarget = (key, index, count) => {
        if (key === 'ArrowRight') return (index + 1) % count;
        if (key === 'ArrowLeft') return (index - 1 + count) % count;
        if (key === 'Home') return 0;
        if (key === 'End') return count - 1;
        return -1;
    };

    api.tabs = function (tablist, opts = {}) {
        if (typeof tablist === 'string') tablist = document.getElementById(tablist);
        if (!tablist) return null;
        const { onChange, persist } = opts;
        const useHash = opts.hash === undefined ? !!persist : !!opts.hash;
        const tabs = [...tablist.querySelectorAll('[role="tab"]')];
        const ids = tabs.map((tab) => tab.getAttribute('data-tab'));
        let current = null;

        const readStored = () => {
            if (!persist) return '';
            try { return window.localStorage.getItem(persist) || ''; } catch { return ''; }
        };
        const remember = (id) => {
            if (persist) { try { window.localStorage.setItem(persist, id); } catch { /* privater Modus */ } }
            if (useHash) {
                const loc = window.location;
                try { window.history.replaceState(window.history.state, '', `${loc.pathname}${loc.search}#${id}`); } catch { /* Sandbox */ }
            }
        };

        function select(id, { focus = false, persist: save = true } = {}) {
            if (!ids.includes(id)) return current;
            const changed = id !== current;
            current = id;
            tabs.forEach((tab) => {
                const on = tab.getAttribute('data-tab') === id;
                tab.setAttribute('aria-selected', String(on));
                tab.setAttribute('tabindex', on ? '0' : '-1');
                const panel = document.getElementById(tab.getAttribute('aria-controls'));
                if (panel) panel.toggleAttribute('hidden', !on);
                if (on && focus) tab.focus?.();
            });
            if (save) remember(id);
            if (changed && onChange) onChange(id);
            return current;
        }

        tablist.addEventListener('click', (e) => {
            const tab = e.target.closest('[role="tab"]');
            if (!tab || !tablist.contains(tab) || tab.getAttribute('aria-disabled') === 'true') return;
            select(tab.getAttribute('data-tab'));
        });
        tablist.addEventListener('keydown', (e) => {
            const tab = e.target.closest('[role="tab"]');
            const index = tabs.indexOf(tab);
            if (index < 0 || e.altKey || e.ctrlKey || e.metaKey) return;
            const target = tabsKeyTarget(e.key, index, tabs.length);
            if (target < 0) return;
            e.preventDefault();
            select(ids[target], { focus: true });
        });
        if (useHash) {
            window.addEventListener('hashchange', () => {
                const id = String(window.location.hash).replace(/^#/, '');
                if (ids.includes(id)) select(id, { persist: false });
            });
        }

        select(tabsPick(ids, { hash: useHash ? window.location.hash : '', stored: readStored() }), { persist: false });
        return { select, ids, get current() { return current; } };
    };
    api.tabs.pick = tabsPick;
    api.tabs.keyTarget = tabsKeyTarget;

    // ---------- Job-Aktionen ----------
    // Einheitliche Icon-Knoepfe fuer ui-job-actions: abbrechen, wiederholen, loeschen, Meldung schliessen.
    const JOB_ACTIONS = {
        cancel: { icon: 'x', verb: 'abbrechen' },
        retry: { icon: 'rotate-ccw', verb: 'erneut versuchen' },
        delete: { icon: 'trash-2', verb: 'löschen', danger: true },
        dismiss: { icon: 'x', verb: 'Meldung schließen' },
        discard: { icon: 'x', verb: 'verwerfen' },
    };
    let iconsQueued = false;
    const queueIcons = () => {
        if (iconsQueued) return;
        iconsQueued = true;
        requestAnimationFrame(() => {
            iconsQueued = false;
            // lucide kommt per defer von unpkg und kann spaeter fertig sein als der erste Knopf.
            if (window.lucide?.createIcons) window.lucide.createIcons();
            else window.addEventListener('load', () => window.lucide?.createIcons?.(), { once: true });
        });
    };
    // name: worauf sich die Aktion bezieht ("Lied.mp3"), landet im aria-label ("Lied.mp3 abbrechen").
    api.jobAction = function (kind, { name, onClick } = {}) {
        const a = JOB_ACTIONS[kind] || JOB_ACTIONS.cancel;
        const label = name ? `${name}: ${a.verb}` : a.verb.charAt(0).toUpperCase() + a.verb.slice(1);
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'btn icon' + (a.danger ? ' danger' : '');
        b.setAttribute('aria-label', label);
        b.title = label;
        b.innerHTML = `<i data-lucide="${a.icon}"></i>`;
        if (onClick) b.addEventListener('click', onClick);
        queueIcons();
        return b;
    };

    // ---------- Fortschritt ----------
    // value 0..100 setzt Breite und aria-valuenow; null schaltet auf unbestimmt.
    // opts.valueText setzt aria-valuetext ("Fehlgeschlagen", "Wartet"), sonst entfaellt es.
    api.setProgress = function (el, value, label, opts) {
        if (typeof el === 'string') el = document.getElementById(el);
        if (!el) return;
        el.setAttribute('role', 'progressbar');
        el.setAttribute('aria-valuemin', '0');
        el.setAttribute('aria-valuemax', '100');
        if (label) el.setAttribute('aria-label', label);
        if (opts && opts.valueText) el.setAttribute('aria-valuetext', opts.valueText);
        else el.removeAttribute('aria-valuetext');
        let bar = el.querySelector('.ui-progress-bar');
        if (!bar) { bar = document.createElement('span'); bar.className = 'ui-progress-bar'; el.appendChild(bar); }
        if (value == null) {
            el.setAttribute('data-indeterminate', '');
            el.removeAttribute('aria-valuenow');
        } else {
            const v = Math.max(0, Math.min(100, Number(value) || 0));
            el.removeAttribute('data-indeterminate');
            el.setAttribute('aria-valuenow', String(Math.round(v)));
            el.style.setProperty('--value', `${v}%`);
        }
    };

    // ---------- Fuellstand ----------
    // value 0..100 setzt Breite bzw. Bogen und aria-valuenow; null heisst: kein Messwert.
    // Ton: tone ('ok' | 'warn' | 'error') oder Schwellen warnAt / errorAt; ohne beides Akzentfarbe.
    const SVG_NS = 'http://www.w3.org/2000/svg';
    const ringSvg = (arc) => {
        const svg = document.createElementNS(SVG_NS, 'svg');
        svg.setAttribute('viewBox', arc ? '0 0 40 23' : '0 0 40 40');
        svg.setAttribute('aria-hidden', 'true');
        svg.setAttribute('focusable', 'false');
        ['track', 'fill'].forEach((part) => {
            const shape = document.createElementNS(SVG_NS, arc ? 'path' : 'circle');
            if (arc) shape.setAttribute('d', 'M3 20A17 17 0 0 1 37 20');
            else { shape.setAttribute('cx', '20'); shape.setAttribute('cy', '20'); shape.setAttribute('r', '17'); }
            shape.setAttribute('pathLength', '100');
            shape.setAttribute('class', `ui-meter-ring-${part}`);
            svg.appendChild(shape);
        });
        return svg;
    };
    api.setMeter = function (el, value, opts) {
        if (typeof el === 'string') el = document.getElementById(el);
        if (!el) return;
        const o = opts || {};
        el.setAttribute('role', 'meter');
        el.setAttribute('aria-valuemin', '0');
        el.setAttribute('aria-valuemax', '100');
        if (o.label) el.setAttribute('aria-label', o.label);
        if (el.classList.contains('ui-meter-ring')) {
            if (!el.querySelector('svg')) el.insertBefore(ringSvg(el.dataset.shape === 'arc'), el.firstChild);
        } else if (!el.querySelector('.ui-meter-fill')) {
            const fill = document.createElement('span');
            fill.className = 'ui-meter-fill';
            el.appendChild(fill);
        }
        const known = value != null && Number.isFinite(Number(value));
        const v = known ? Math.max(0, Math.min(100, Number(value))) : 0;
        if (known) el.setAttribute('aria-valuenow', String(Math.round(v)));
        else el.removeAttribute('aria-valuenow');
        const text = o.valueText || (known ? '' : 'keine Daten');
        if (text) el.setAttribute('aria-valuetext', text);
        else el.removeAttribute('aria-valuetext');
        const tone = o.tone || (!known ? null : o.errorAt != null && v >= o.errorAt ? 'error' : o.warnAt != null && v >= o.warnAt ? 'warn' : null);
        if (tone) el.setAttribute('data-tone', tone);
        else el.removeAttribute('data-tone');
        if (el.classList.contains('ui-meter-ring')) el.toggleAttribute('data-empty', v <= 0);
        el.style.setProperty('--value', `${v}%`);
        el.style.setProperty('--value-n', String(v));
    };

    // ---------- Upload ----------
    const zoneOf = (e) => e.target instanceof Element ? e.target.closest('.ui-dropzone') : null;
    const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes('Files');
    // Das Datei-Feld prueft accept nur im Auswahldialog, beim Ablegen muss das hier passieren.
    const accepts = (input, file) => {
        const rules = (input.accept || '').split(',').map((r) => r.trim().toLowerCase()).filter(Boolean);
        if (!rules.length) return true;
        const name = file.name.toLowerCase(), type = (file.type || '').toLowerCase();
        return rules.some((r) => (r.startsWith('.') ? name.endsWith(r) : r.endsWith('/*') ? type.startsWith(r.slice(0, -1)) : type === r));
    };
    ['dragenter', 'dragover'].forEach((type) => document.addEventListener(type, (e) => {
        const zone = zoneOf(e);
        if (!zone || !hasFiles(e)) return;
        // Auch bei gesperrtem Feld abfangen, sonst oeffnet der Browser die Datei und die Seite ist weg.
        e.preventDefault();
        if (zone.querySelector('.ui-dropzone-input')?.disabled) { e.dataTransfer.dropEffect = 'none'; return; }
        zone.setAttribute('data-dragover', '');
    }));
    document.addEventListener('dragleave', (e) => {
        const zone = zoneOf(e);
        if (zone && !zone.contains(e.relatedTarget)) zone.removeAttribute('data-dragover');
    });
    document.addEventListener('drop', (e) => {
        const zone = zoneOf(e);
        if (!zone) return;
        e.preventDefault();
        zone.removeAttribute('data-dragover');
        const input = zone.querySelector('.ui-dropzone-input');
        if (!input || input.disabled || !e.dataTransfer?.files?.length) return;
        const files = [...e.dataTransfer.files].filter((f) => accepts(input, f));
        if (!files.length) {
            api.rejectFile(input, `${e.dataTransfer.files[0].name}: dieser Dateityp passt hier nicht.`);
            return;
        }
        zone.removeAttribute('data-invalid');
        const dt = new DataTransfer();
        (input.multiple ? files : files.slice(0, 1)).forEach((f) => dt.items.add(f));
        input.files = dt.files;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    });
    // Einfuegen (Cmd/Strg+V): Dateien aus der Zwischenablage landen im sichtbaren Upload-Feld
    // der Seite, das sie annimmt, genau wie beim Ablegen. Kandidaten sind alle Dropzones und
    // jedes eigene Datei-Feld mit data-paste (sichtbar zaehlt dann sein Elternelement oder
    // [data-paste-area]). Text-Einfuegen und Apps mit eigenem Handler bleiben unberuehrt.
    const visible = (el) => !!el && el.getClientRects().length > 0 && !el.closest('[hidden], dialog:not([open])');
    document.addEventListener('paste', (e) => {
        if (e.defaultPrevented) return;
        const pasted = [...(e.clipboardData?.items || [])]
            .filter((i) => i.kind === 'file').map((i) => i.getAsFile()).filter(Boolean);
        if (!pasted.length) return;
        const areaOf = (input) => input.closest('.ui-dropzone') || input.closest('[data-paste-area]')
            || (visible(input) ? input : input.parentElement);
        const inputs = [...document.querySelectorAll('.ui-dropzone-input, input[type="file"][data-paste]')]
            .filter((input) => !input.disabled && visible(areaOf(input)));
        // Fokus im Bereich eines Felds entscheidet, sonst das erste, das den Dateityp nimmt.
        const focused = inputs.find((input) => areaOf(input)?.contains(document.activeElement));
        const ext = (t) => (t.split('/')[1] || 'bin').replace('jpeg', 'jpg').replace(/[^a-z0-9]/g, '');
        // Screenshots aus der Zwischenablage haben keinen Namen; accept prueft auch die Endung.
        const named = pasted.map((f) => (f.name ? f : new File([f], `eingefuegt.${ext(f.type || '')}`, { type: f.type })));
        const input = [focused, ...inputs].find((i) => i && named.some((f) => accepts(i, f)));
        if (!input) return;
        e.preventDefault();
        const files = named.filter((f) => accepts(input, f));
        const dt = new DataTransfer();
        (input.multiple ? files : files.slice(0, 1)).forEach((f) => dt.items.add(f));
        input.files = dt.files;
        input.closest('.ui-dropzone')?.removeAttribute('data-invalid');
        input.dispatchEvent(new CustomEvent('ui:paste', { bubbles: true, detail: { count: dt.files.length } }));
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    });
    // Lehnt eine Datei ab: roter Rand, Grund in der Dropzone, Toast, Feld leer. Fuer eigene
    // Pruefungen der App (Groesse, Format) im change-Handler aufrufen.
    api.rejectFile = function (input, message) {
        const zone = input?.closest('.ui-dropzone');
        if (!zone) return;
        input.value = '';
        zone.removeAttribute('data-filled');
        zone.setAttribute('data-invalid', '');
        const list = zone.querySelector('.ui-dropzone-files');
        if (list) list.textContent = message;
        window.showToast?.(message, 'err');
        input.dispatchEvent(new CustomEvent('ui:reject', { bubbles: true, detail: { message } }));
    };
    document.addEventListener('change', (e) => {
        const input = e.target;
        if (!(input instanceof HTMLInputElement) || !input.classList.contains('ui-dropzone-input')) return;
        const zone = input.closest('.ui-dropzone');
        const names = [...(input.files || [])].map((f) => f.name);
        // Hat die App die Datei im eigenen change-Handler abgelehnt (Feld leer), bleibt ihr Hinweis stehen.
        if (!names.length && zone?.hasAttribute('data-invalid')) return;
        // Die App zeigt die Auswahl mit ui.dropzoneFiles unter dem Feld.
        if (zone?.hasAttribute('data-selected')) return;
        zone?.toggleAttribute('data-filled', names.length > 0);
        if (names.length) zone?.removeAttribute('data-invalid');
        const list = zone?.querySelector('.ui-dropzone-files');
        if (list) list.textContent = names.length > 3 ? `${names.slice(0, 3).join(', ')} und ${names.length - 3} weitere` : names.join(', ');
    });

    // Gewaehlte oder auf dem Server behaltene Dateien als Liste direkt unter der Dropzone, je Datei
    // mit Entfernen-Knopf. Die Liste steht neben dem <label>, nicht darin: Knoepfe in einem Label
    // waeren ungueltig und loesten den Dateidialog aus. items: [{ name, size?, keptUntil?, meta? }].
    const fmtBytes = (n) => (n >= 1024 * 1024 ? `${(n / (1024 * 1024)).toFixed(1).replace('.', ',')} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
    api.formatReadyUntil = function (ms) {
        const d = new Date(ms);
        const time = d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
        if (d.toDateString() === new Date().toDateString()) return `bereit bis ${time}`;
        if (d.toDateString() === new Date(Date.now() + 864e5).toDateString()) return `bereit bis morgen ${time}`;
        return `bereit bis ${d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })} ${time}`;
    };
    api.dropzoneFiles = function (input, items, { onRemove } = {}) {
        if (typeof input === 'string') input = document.getElementById(input);
        const zone = input?.closest('.ui-dropzone');
        if (!zone) return null;
        let list = zone.nextElementSibling?.classList.contains('ui-dropzone-selected') ? zone.nextElementSibling : null;
        const names = zone.querySelector('.ui-dropzone-files');
        if (!items || !items.length) {
            list?.remove();
            zone.removeAttribute('data-selected');
            zone.removeAttribute('data-filled');
            if (names && !zone.hasAttribute('data-invalid')) names.textContent = '';
            return null;
        }
        if (!list) {
            list = document.createElement('ul');
            list.className = 'ui-list ui-dropzone-selected';
            list.setAttribute('aria-label', items.length > 1 ? 'Gewählte Dateien' : 'Gewählte Datei');
            zone.after(list);
        }
        zone.setAttribute('data-selected', '');
        zone.setAttribute('data-filled', '');
        zone.removeAttribute('data-invalid');
        if (names) names.textContent = '';
        list.replaceChildren(...items.map((item, idx) => {
            const li = document.createElement('li');
            li.className = 'ui-row';
            const icon = document.createElement('span');
            icon.className = 'ui-row-icon';
            icon.innerHTML = '<i data-lucide="file"></i>';
            const text = document.createElement('span');
            text.className = 'ui-row-text';
            const title = document.createElement('span');
            title.className = 'ui-row-title';
            title.textContent = title.title = item.name;
            const meta = document.createElement('span');
            meta.className = 'ui-row-meta';
            meta.textContent = [item.size ? fmtBytes(item.size) : '', item.keptUntil ? api.formatReadyUntil(item.keptUntil) : '', item.meta || ''].filter(Boolean).join(' · ');
            text.append(title, meta);
            const actions = document.createElement('div');
            actions.className = 'ui-row-actions';
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'btn icon';
            remove.setAttribute('aria-label', `${item.name} entfernen`);
            remove.title = `${item.name} entfernen`;
            remove.innerHTML = '<i data-lucide="x"></i>';
            remove.addEventListener('click', () => {
                onRemove?.(item, idx);
                // Der Knopf ist danach weg: Fokus auf die naechste Datei oder zurueck aufs Feld.
                const rest = list.isConnected ? list.querySelectorAll('.ui-row-actions .btn') : [];
                (rest[Math.min(idx, rest.length - 1)] || input).focus();
            });
            actions.append(remove);
            li.append(icon, text, actions);
            return li;
        }));
        queueIcons();
        return list;
    };

    // ---------- Slider ----------
    function syncRange(input) {
        const min = Number(input.min || 0), max = Number(input.max || 100);
        const pct = max > min ? ((Number(input.value) - min) / (max - min)) * 100 : 0;
        input.style.setProperty('--fill', `${pct}%`);
        const out = input.id && document.querySelector(`output[for~="${CSS.escape(input.id)}"]`);
        if (out) out.textContent = `${input.value}${out.dataset.unit || ''}`;
    }
    api.syncRange = syncRange;
    document.addEventListener('input', (e) => {
        if (e.target instanceof HTMLInputElement && e.target.classList.contains('ui-range')) syncRange(e.target);
    });
    // Startwert einmal nach dem Laden setzen; spaeter eingefuegte Slider ruft die App mit ui.syncRange().
    const initRanges = () => document.querySelectorAll('input.ui-range').forEach(syncRange);
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initRanges, { once: true });
    else initRanges();

    // ---------- Formularfeld ----------
    // Setzt oder entfernt den Fehler eines Feldes: Text, aria-invalid, aria-describedby.
    api.setFieldError = function (control, message) {
        if (typeof control === 'string') control = document.getElementById(control);
        const field = control?.closest('.ui-field');
        if (!field) return;
        if (!control.id) control.id = `ui-field-${++seq}`;
        let error = field.querySelector('.ui-field-error');
        if (!error) {
            error = document.createElement('p');
            error.className = 'ui-field-error';
            error.id = `${control.id}-error`;
            field.appendChild(error);
        }
        // Sonst hoert ein Screenreader den Fehler nur, wenn der Fokus gerade wechselt.
        if (!error.hasAttribute('role')) error.setAttribute('role', 'alert');
        const ids = new Set((control.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
        if (message) {
            error.textContent = message;
            error.hidden = false;
            ids.add(error.id);
            control.setAttribute('aria-invalid', 'true');
            field.setAttribute('data-invalid', '');
        } else {
            error.textContent = '';
            error.hidden = true;
            ids.delete(error.id);
            control.removeAttribute('aria-invalid');
            field.removeAttribute('data-invalid');
        }
        if (ids.size) control.setAttribute('aria-describedby', [...ids].join(' '));
        else control.removeAttribute('aria-describedby');
    };

    // ---------- Audio-Player ----------
    // Es klingt immer nur eine Quelle. Wer abspielt, meldet eine Stopp-Funktion an; startet
    // danach etwas anderes, wird sie aufgerufen. Eigene Audio-Engines (Web Audio, Mehrspur)
    // melden sich genauso an, damit auch sie verstummen.
    const audioClaims = new Set();
    api.claimAudio = function (stop) {
        for (const other of [...audioClaims]) {
            if (other === stop) continue;
            audioClaims.delete(other);
            try { other(); } catch (_) { /* ein kaputter Player darf den neuen nicht aufhalten */ }
        }
        if (stop) audioClaims.add(stop);
    };
    api.releaseAudio = function (stop) { audioClaims.delete(stop); };

    const PEAK_COUNT = 400;
    const peakRequests = new Map();
    const peakQueue = [];
    let fetchingPeaks = 0;

    api.peaksFromBuffer = function (buffer, count = PEAK_COUNT) {
        const channels = [];
        for (let c = 0; c < buffer.numberOfChannels; c++) channels.push(buffer.getChannelData(c));
        const length = channels[0]?.length || 0;
        const peaks = new Float32Array(count);
        for (let i = 0; i < count; i++) {
            const from = Math.floor(i * length / count);
            const to = Math.floor((i + 1) * length / count);
            let peak = 0;
            for (const data of channels) {
                for (let j = from; j < to; j++) peak = Math.max(peak, Math.abs(data[j]) || 0);
            }
            peaks[i] = Math.min(1, peak);
        }
        return peaks;
    };

    function validWaveform(value) {
        return value?.version === 1 && value.algorithm === 'abs-max-v1' && value.count === PEAK_COUNT
            && Number.isFinite(value.durationSec) && value.durationSec > 0
            && Array.isArray(value.peaks) && value.peaks.length === PEAK_COUNT
            && value.peaks.every((peak) => Number.isFinite(peak) && peak >= 0 && peak <= 1);
    }

    async function readWaveformResponse(res, controller) {
        if (!res.ok || res.status === 202) return null;
        if (!/^application\/json(?:\s*;|$)/i.test(res.headers.get('Content-Type') || '')
            || Number(res.headers.get('Content-Length')) > 16384) {
            controller.abort();
            return null;
        }
        const reader = res.body?.getReader();
        if (!reader) return null;
        const chunks = [];
        let size = 0;
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            size += value.byteLength;
            if (size > 16384) { controller.abort(); await reader.cancel(); return null; }
            chunks.push(value);
        }
        const bytes = new Uint8Array(size);
        let offset = 0;
        for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
        return JSON.parse(new TextDecoder().decode(bytes));
    }

    async function readPeaks(url, localDecode) {
        const target = new URL(url, window.location?.href || 'http://localhost/');
        if (target.protocol === 'blob:' || target.protocol === 'data:') {
            if (!localDecode) return null;
            const res = await fetch(url);
            if (!res.ok) return null;
            const Offline = window.OfflineAudioContext || window.webkitOfflineAudioContext;
            const buffer = await new Offline(1, 1, 44100).decodeAudioData(await res.arrayBuffer());
            return { peaks: api.peaksFromBuffer(buffer), duration: buffer.duration };
        }
        const origin = new URL(window.location?.href || 'http://localhost/').origin;
        if (target.origin !== origin || !['http:', 'https:'].includes(target.protocol)) return null;
        target.searchParams.set('waveform', '1');
        for (let attempt = 0; attempt < 6; attempt++) {
            const controller = new AbortController();
            let deadline;
            const { res, value } = await Promise.race([
                fetch(target.href, { credentials: 'same-origin', cache: 'no-store', signal: controller.signal }).then(async (res) => ({ res, value: await readWaveformResponse(res, controller) })),
                new Promise((_, reject) => { deadline = setTimeout(() => { controller.abort(); reject(new Error('waveform_timeout')); }, 10000); }),
            ]).finally(() => clearTimeout(deadline));
            if (res.status === 202) {
                if (attempt === 5) return null;
                const retry = res.headers.get('Retry-After');
                const seconds = Number(retry);
                const requested = retry && Number.isFinite(seconds) ? seconds * 1000 : Date.parse(retry) - Date.now();
                const delay = Math.min(30000, Math.max(250, Number.isFinite(requested) ? requested : 500 * 2 ** attempt));
                await new Promise((resolve) => setTimeout(resolve, delay));
                continue;
            }
            if (!res.ok) return null;
            return validWaveform(value) ? { peaks: value.peaks, duration: value.durationSec } : null;
        }
        return null;
    }

    function pumpPeaks() {
        while (fetchingPeaks < 2 && peakQueue.length) {
            const { key, url, localDecode, resolve, promise } = peakQueue.shift();
            fetchingPeaks++;
            readPeaks(url, localDecode).catch(() => null).then(resolve).finally(() => {
                if (peakRequests.get(key) === promise) peakRequests.delete(key);
                fetchingPeaks--;
                pumpPeaks();
            });
        }
    }

    // Only concurrent requests are shared; a newly selected asset checks its current revision.
    api.audioPeaks = function (url, { localDecode = false } = {}) {
        const key = `${localDecode}:${url}`;
        if (!peakRequests.has(key)) {
            let settle;
            const promise = new Promise((resolve) => { settle = resolve; });
            peakQueue.push({ key, url, localDecode, resolve: settle, promise });
            peakRequests.set(key, promise);
            pumpPeaks();
        }
        return peakRequests.get(key);
    };

    const BAR = 3, BAR_GAP = 2;
    // Balken aus Spitzenwerten. Ohne Werte bleibt eine flache Spur: keine erfundene Form.
    // progress 0..1 hebt den gespielten Teil hervor, -1 zeichnet alles gleich.
    api.drawWave = function (canvas, peaks, { progress = -1, gain = 1, normalize = true } = {}) {
        const dpr = window.devicePixelRatio || 1;
        const w = Math.max(1, Math.round(canvas.clientWidth));
        const h = Math.max(1, Math.round(canvas.clientHeight));
        if (canvas.width !== w * dpr) canvas.width = w * dpr;
        if (canvas.height !== h * dpr) canvas.height = h * dpr;
        const g = canvas.getContext('2d');
        g.setTransform(dpr, 0, 0, dpr, 0, 0);
        g.clearRect(0, 0, w, h);
        g.fillStyle = getComputedStyle(canvas).color;
        const bars = Math.max(1, Math.floor((w + BAR_GAP) / (BAR + BAR_GAP)));
        const offset = (w - (bars * (BAR + BAR_GAP) - BAR_GAP)) / 2;
        let max = 0;
        if (peaks && normalize) for (const p of peaks) if (p > max) max = p;
        const scale = normalize && max > 0 ? 1 / max : 1;
        for (let i = 0; i < bars; i++) {
            let v = 0;
            if (peaks && peaks.length) {
                const a = Math.floor((i * peaks.length) / bars);
                const b = Math.max(a + 1, Math.floor(((i + 1) * peaks.length) / bars));
                for (let j = a; j < b && j < peaks.length; j++) if (peaks[j] > v) v = peaks[j];
                v = Math.min(1, v * scale * gain);
            }
            const bh = Math.max(2, v * (h - 8));
            if (progress < 0) g.globalAlpha = 0.75;
            else g.globalAlpha = (i + 0.5) / bars <= progress ? 1 : 0.4;
            g.fillRect(offset + i * (BAR + BAR_GAP), (h - bh) / 2, BAR, bh);
        }
        g.globalAlpha = 1;
    };

    const fmtTime = (sec) => {
        const s = Math.max(0, Math.floor(Number(sec) || 0));
        return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
    };
    const PLAYER_ICONS = {
        play: '<polygon points="6 3 20 12 6 21 6 3"/>',
        pause: '<rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/>',
        loading: '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
    };
    const playerIcon = (name) => `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PLAYER_ICONS[name]}</svg>`;

    const waveObserver = 'IntersectionObserver' in window
        ? new IntersectionObserver((entries) => {
            for (const e of entries) if (e.isIntersecting) e.target._uiPlayerVisible?.();
        }, { rootMargin: '200px' })
        : null;

    // Ein Player fuer alle Apps: Knopf, Wellenform mit Abspielstrich, Zeit.
    // opts: src, label, duration (Sekunden, falls vorab bekannt), peaks, wave (false deaktiviert), localDecode,
    // time (Zeitanzeige, Standard an), size ('sm' | 'lg'), preload ('none' | 'metadata'),
    // title (sichtbarer Name), meta (Zeile unter dem Namen), layout ('stacked': Zeit unter der Wellenform),
    // actions (Elemente rechts neben der Wellenform), topActions (oben rechts neben der Zeit, etwa Download).
    api.player = function (opts = {}) {
        let label = opts.label || 'Audio';
        let src = null;
        let peaks = null;
        let duration = 0;
        let waveMode = 'metadata';
        let localDecode = false;
        let sourceGeneration = 0;
        let peaksRequested = false;
        let state = 'idle';
        let raf = 0;
        let rangeEnd = null;
        let seen = false;
        let fatal = false;
        let drag = null;
        // Sprungziel, solange noch keine Metadaten da sind: currentTime greift dann nicht ueberall.
        let pendingTime = null;

        const root = document.createElement('div');
        root.className = `ui-player${opts.size ? ` ui-player-${opts.size}` : ''}`;
        const stacked = opts.layout === 'stacked';
        if (stacked) root.classList.add('ui-player-stacked');
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn icon ui-player-toggle';
        const wave = document.createElement('div');
        wave.className = 'ui-player-wave';
        wave.tabIndex = 0;
        wave.setAttribute('role', 'slider');
        wave.setAttribute('aria-valuemin', '0');
        const canvas = document.createElement('canvas');
        canvas.className = 'ui-player-canvas';
        canvas.setAttribute('aria-hidden', 'true');
        const head = document.createElement('span');
        head.className = 'ui-player-head';
        head.hidden = true;
        wave.append(canvas, head);
        const time = document.createElement('span');
        time.className = 'ui-player-time';
        time.setAttribute('aria-hidden', 'true');
        time.hidden = opts.time === false;
        if (opts.title) {
            root.classList.add('ui-player-titled');
            const top = document.createElement('div');
            top.className = 'ui-player-top';
            const heading = document.createElement('div');
            heading.className = 'ui-player-heading';
            const title = document.createElement(stacked && opts.href ? 'a' : 'span');
            if (stacked && opts.href) title.href = opts.href;
            title.className = 'ui-player-title';
            title.textContent = opts.title;
            title.title = opts.titleFull || opts.title;
            heading.append(title);
            if (opts.meta) {
                const meta = document.createElement('span');
                meta.className = 'ui-player-meta';
                meta.textContent = opts.meta;
                heading.append(meta);
            }
            const end = document.createElement('div');
            end.className = 'ui-player-top-end';
            if (!stacked) end.append(time);
            if (Array.isArray(opts.topActions)) end.append(...opts.topActions);
            top.append(heading, end);
            root.append(top, button, wave);
            if (stacked) root.append(time);
        } else {
            root.append(button, wave, time);
        }
        if (Array.isArray(opts.actions) && opts.actions.length) {
            const actions = document.createElement('div');
            actions.className = 'ui-player-actions';
            actions.append(...opts.actions);
            root.append(actions);
        }

        const audio = new Audio();
        audio.preload = opts.wave === false || opts.localDecode === true ? opts.preload || 'none' : 'none';

        const total = () => (Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : duration);
        const position = () => pendingTime ?? (audio.currentTime || 0);
        const moveTo = (sec) => {
            if (audio.readyState >= 1) audio.currentTime = sec;
            else pendingTime = sec;
        };

        function paint() {
            const d = total();
            const t = Math.min(position(), d || Infinity);
            const p = d ? t / d : 0;
            head.style.left = `${p * 100}%`;
            api.drawWave(canvas, peaks, { progress: state === 'idle' || state === 'error' ? -1 : p });
            if (state === 'error') time.textContent = fatal ? opts.errorText || 'Nicht abspielbar' : 'Laden fehlgeschlagen';
            else time.textContent = d ? `${fmtTime(t)} / ${fmtTime(d)}` : '';
            wave.setAttribute('aria-valuemax', String(Math.round((d || 0) * 10) / 10));
            wave.setAttribute('aria-valuenow', String(Math.round(t * 10) / 10));
            wave.setAttribute('aria-valuetext', d ? `${fmtTime(t)} von ${fmtTime(d)}` : 'unbekannte Länge');
        }

        function setState(next) {
            state = next;
            root.dataset.state = next;
            const playing = next === 'playing';
            button.innerHTML = playerIcon(next === 'loading' ? 'loading' : playing ? 'pause' : 'play');
            button.setAttribute('aria-label', `${label} ${playing ? 'pausieren' : 'abspielen'}`);
            button.setAttribute('aria-busy', String(next === 'loading'));
            const dead = !src || (next === 'error' && fatal);
            button.disabled = dead;
            wave.setAttribute('aria-disabled', String(dead));
            head.hidden = next === 'idle' || next === 'error';
            cancelAnimationFrame(raf);
            if (playing) {
                const loop = () => {
                    // Aus dem Dokument genommen (Liste neu gebaut): ein freies Audio spielte sonst ohne Knopf weiter.
                    if (!root.isConnected) { reset(); return; }
                    paint();
                    raf = requestAnimationFrame(loop);
                };
                raf = requestAnimationFrame(loop);
            }
            paint();
            root.dispatchEvent(new CustomEvent('ui:player', { bubbles: true, detail: { state: next, fatal: next === 'error' && fatal } }));
        }

        // Zurueck auf Anfang, Strich weg. Auch der Weg, auf dem ein anderer Player diesen abloest.
        function reset() {
            api.releaseAudio(reset);
            cancelAnimationFrame(raf);
            rangeEnd = null;
            pendingTime = null;
            audio.pause();
            if (audio.readyState > 0) audio.currentTime = 0;
            if (state !== 'error') setState('idle');
        }

        function loadPeaks() {
            if (!waveMode || peaksRequested || peaks || !src || !seen) return;
            peaksRequested = true;
            const generation = sourceGeneration;
            const want = src;
            wave.dataset.wave = 'loading';
            api.audioPeaks(want, { localDecode }).then((result) => {
                if (generation !== sourceGeneration || want !== src) return;
                delete wave.dataset.wave;
                if (!result) { wave.dataset.wave = 'unavailable'; return; }
                peaks = result.peaks;
                if (!duration) duration = result.duration;
                paint();
            });
        }
        wave._uiPlayerVisible = () => { seen = true; waveObserver?.unobserve(wave); loadPeaks(); };
        if (waveObserver) waveObserver.observe(wave);
        else seen = true;

        function play(from) {
            if (!src || (state === 'error' && fatal)) return;
            // Nach einem Netzfehler darf der naechste Druck es erneut versuchen.
            if (state === 'error') { audio.load(); state = 'idle'; }
            api.claimAudio(reset);
            if (Number.isFinite(from)) moveTo(Math.max(0, from));
            if (audio.readyState < 3) setState('loading');
            audio.play().catch((err) => {
                // AbortError: ein Pause oder neues src kam dazwischen, das ist kein Fehler.
                if (err?.name !== 'AbortError' && err?.name !== 'NotAllowedError') setState('error');
                else if (state === 'loading') setState(audio.currentTime > 0 ? 'paused' : 'idle');
            });
        }
        function pause() { audio.pause(); }
        function seek(sec) {
            if (!src || state === 'error') return;
            // Wer selbst springt, verlaesst den vorgegebenen Bereich.
            rangeEnd = null;
            const d = total();
            moveTo(Math.max(0, d ? Math.min(d, sec) : sec));
            if (state === 'idle') { api.claimAudio(reset); setState('paused'); }
            else paint();
        }

        audio.addEventListener('playing', () => setState('playing'));
        audio.addEventListener('waiting', () => { if (state === 'playing') setState('loading'); });
        audio.addEventListener('pause', () => { if (state === 'playing' || state === 'loading') setState('paused'); });
        audio.addEventListener('ended', reset);
        audio.addEventListener('loadedmetadata', () => {
            if (pendingTime != null) { audio.currentTime = pendingTime; pendingTime = null; }
            paint();
        });
        audio.addEventListener('timeupdate', () => {
            if (!root.isConnected) { reset(); return; }
            if (rangeEnd != null && audio.currentTime >= rangeEnd) { rangeEnd = null; audio.pause(); }
            if (state !== 'playing') paint();
        });
        audio.addEventListener('error', () => {
            if (!src) return;
            api.releaseAudio(reset);
            // Code 4: Datei fehlt oder Format unbekannt. Alles andere (Netz) ist einen neuen Versuch wert.
            fatal = audio.error?.code === 4;
            setState('error');
        });

        button.addEventListener('click', () => (state === 'playing' || state === 'loading' ? pause() : play()));
        const seekFromX = (x) => {
            const r = wave.getBoundingClientRect();
            const d = total();
            if (!d || !r.width) return;
            rangeEnd = null;
            seek(Math.min(1, Math.max(0, (x - r.left) / r.width)) * d);
        };
        // Maus springt sofort. Ein Finger erst beim Loslassen oder nach waagerechtem Ziehen:
        // pointerdown kommt vor der Entscheidung, ob gescrollt wird, und Scrollen ueber eine
        // Liste voller Wellenformen soll nichts anspringen.
        const tapOrSeek = (x) => {
            // Laenge unbekannt (nichts geladen): erst laden, dann springt der naechste Druck.
            if (!total()) play();
            else seekFromX(x);
        };
        wave.addEventListener('pointerdown', (e) => {
            if (e.button !== 0 || !src || state === 'error') return;
            drag = { id: e.pointerId, x: e.clientX, touch: e.pointerType !== 'mouse', moved: false };
            if (drag.touch) return;
            wave.setPointerCapture?.(e.pointerId);
            tapOrSeek(e.clientX);
        });
        wave.addEventListener('pointermove', (e) => {
            if (!drag || e.pointerId !== drag.id) return;
            if (drag.touch && !drag.moved) {
                if (Math.abs(e.clientX - drag.x) < 8) return;
                drag.moved = true;
                wave.setPointerCapture?.(e.pointerId);
            }
            if (!drag.touch || drag.moved) seekFromX(e.clientX);
        });
        wave.addEventListener('pointerup', (e) => {
            if (drag?.touch && !drag.moved && e.pointerId === drag.id) tapOrSeek(e.clientX);
            drag = null;
        });
        wave.addEventListener('pointercancel', () => { drag = null; });
        wave.addEventListener('keydown', (e) => {
            const d = total();
            const step = e.shiftKey ? 5 : 1;
            let target = null;
            if (e.key === 'ArrowRight' || e.key === 'ArrowUp') target = position() + step;
            else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') target = position() - step;
            else if (e.key === 'Home') target = 0;
            else if (e.key === 'End' && d) target = d;
            else if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); button.click(); return; }
            if (target == null || !d) return;
            e.preventDefault();
            seek(target);
        });
        const resizeObserver = 'ResizeObserver' in window ? new ResizeObserver(() => paint()) : null;
        resizeObserver?.observe(wave);

        const player = {
            el: root,
            audio,
            get state() { return state; },
            get currentTime() { return position(); },
            play,
            pause,
            seek,
            reset,
            toggle() { button.click(); },
            // Spielt einen Bereich und haelt an seinem Ende an, etwa die Vorschau eines Schnitts.
            playRange(from, to) { play(from); rangeEnd = Number.isFinite(to) ? to : null; },
            // Fuer Listen, die Player verwerfen: gibt Beobachter und Datei frei.
            destroy() {
                reset();
                waveObserver?.unobserve(wave);
                resizeObserver?.disconnect();
                sourceGeneration++;
                src = null;
                audio.removeAttribute('src');
                audio.load();
            },
            setSrc(next, more = {}) {
                reset();
                if (more.label) label = more.label;
                if (src) peakRequests.delete(`${localDecode}:${src}`);
                sourceGeneration++;
                peaksRequested = false;
                src = next || null;
                peaks = more.peaks || null;
                duration = Number(more.duration) || 0;
                waveMode = more.wave === false ? false : 'metadata';
                localDecode = more.localDecode === true;
                audio.preload = waveMode && !localDecode ? 'none' : more.preload || 'none';
                fatal = false;
                delete wave.dataset.wave;
                if (src) audio.src = src;
                else { audio.removeAttribute('src'); audio.load(); }
                wave.setAttribute('aria-label', `Position in ${label}`);
                state = 'idle';
                setState('idle');
                loadPeaks();
            },
        };
        player.setSrc(opts.src, opts);
        return player;
    };

    api.mediaCard = function (opts = {}) {
        const download = opts.download?.href ? document.createElement('a') : null;
        if (download) {
            download.className = 'btn icon ui-media-download';
            download.href = opts.download.href;
            download.download = opts.download.filename || '';
            download.setAttribute('aria-label', `${opts.title || opts.label || 'Audio'} herunterladen`);
            download.title = 'Herunterladen';
            download.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3v12m-5-5 5 5 5-5M5 16v5h14v-5"/></svg>';
        }
        const player = api.player({ ...opts, title: opts.title || opts.label || 'Audio', layout: 'stacked',
            actions: [], topActions: download ? [download] : [] });
        player.el.classList.add('ui-media-card');
        if (download) player.el.addEventListener('ui:player', (event) => {
            download.hidden = event.detail.fatal || !player.audio.getAttribute('src');
        });
        if (download) download.hidden = !opts.src;
        return player;
    };
})();
