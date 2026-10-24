/**
 * The page Features under Gerät: everything BLECHTRIBE adds, what it does and how to reach it on
 * the device, with a picture of the display where there is one. The facts
 * come from README.md ("Was kann was?") and docs/patcher.md; a new patch gets its entry here.
 */
import { el } from "./fields.mjs";
import { drawDisplay } from "./emulator.mjs";
import { e2Outline } from "./e2-art.mjs";

const BOTH = ["red", "blue"];
const RED = ["red"];
/** The last group: what is planned (docs/ideen.md), without a date. */
const SOON = "Geplant";
const DEVICE = { red: "Electribe 2 Sampler (rot)", blue: "Electribe 2 (blau)" };
const SHORT = { red: "Rot", blue: "Blau" };

/** One entry per function. `how` is what you press, `where` which Electribe has it, `image` a picture of the display. */
export const FEATURES = [
  { group: "Spielen", id: "note-assist", title: "Notenassistent", where: BOTH, image: "img/features/note-assist.svg",
    text: "Im KEYBOARD-Modus leuchten nach einer Note die Pads, die dazu passen. Je heller, desto besser passt die Note. Im CHORD-Modus zeigt er die passenden nächsten Akkorde.",
    how: "KEYBOARD-Modus, eine Note spielen. Abschalten unter Menü -> BLECH -> FEATURES -> NOTE ASSIST." },
  { group: "Spielen", id: "dice", title: "Würfeln", where: BOTH, image: "img/features/dice.svg",
    text: "Schreibt eine neue Melodie in den gewählten Part, aus Tonart und Tonleiter des Patterns. Gespeichert wird erst mit WRITE.",
    how: "SHIFT + PART ERASE." },
  { group: "Spielen", id: "tap-motion", title: "TAP Motion", where: BOTH, image: "img/features/tap-motion.svg",
    text: "TAP schaltet die aufgenommene Motion Sequence des gewählten Parts an und aus. Die TAP-Lampe zeigt, ob sie läuft. Das Tap-Tempo fällt dafür weg.",
    how: "TAP drücken. MASTER FX halten + TAP für die Master-FX-Gesten. Einstellen unter Menü -> BLECH -> FEATURES -> TAP MOTION." },
  { group: "Spielen", id: "pattern-switch", title: "Patternwechsel mit Bestätigung", where: BOTH, image: "img/features/pattern-switch.svg",
    text: "Beim Spielen blättert das Rad nur durch die Patterns. Gewechselt wird erst, wenn du bestätigst.",
    how: "Rad drehen, MENU bestätigt, EXIT nimmt zurück." },
  { group: "Spielen", id: "sync-group", title: "Sync-Gruppen", where: BOTH,
    text: "Patterns einer Gruppe spielen wie ein langes Pattern: am Ende geht es ohne MENU ins nächste, Mutes, Klang, Tempo und MFX gehen mit. So werden aus zwei Patterns mit je 64 Steps eins mit 128.",
    how: "Im EDIT-Ring die Seite SYNC GROUP, gleich vor dem Pattern Menü: Gruppe am Rad wählen, WRITE speichert sie mit dem Pattern." },
  { group: "Spielen", id: "mfx2", title: "Zweiter Master-Effekt", where: BOTH, image: "img/features/mfx2.svg",
    text: "TOUCH SCALE wird zu MFX 2: ein zweiter Master-Effekt pro Pattern.",
    how: "TOUCH SCALE drücken." },
  { group: "Spielen", id: "exit-write", title: "Schnell speichern", where: BOTH, image: "img/features/exit-write.svg",
    text: "Speichert das Pattern an seinen Platz, ohne Fenster. Solange etwas ungespeichert ist, atmet die WRITE-LED.",
    how: "EXIT halten + WRITE." },
  { group: "Spielen", id: "exit-pad", title: "Part zurücksetzen", where: BOTH,
    text: "Setzt den Klang eines Parts auf die gespeicherten Werte zurück.",
    how: "EXIT halten + Pad des Parts." },

  { group: "Aussehen", id: "splash", title: "Eigenes Startbild", where: BOTH, image: "img/features/splash.png",
    text: "Dein Bild beim Einschalten, selbst gemalt im Bereich Startbildschirm. Auf der roten auch direkt am Gerät.",
    how: "In der App: Gerät -> Startbildschirm." },
  { group: "Aussehen", id: "loading", title: "Ladeanimation", where: RED, image: "img/features/loading.png",
    text: "Solange die Samples laden, zieht Blechy eine Line über den Tisch, darunter stehen die Prozent.",
    how: "Kommt von selbst beim Einschalten." },
  { group: "Aussehen", id: "colors", title: "Pad- und LED-Farben", where: BOTH, image: "img/features/colors.svg",
    text: "Farben für Pads, den gewählten Part, die unteren LEDs und das Display-Licht. Im Power Save werden die LEDs gedimmt.",
    how: "Menü -> BLECH -> CUSTOMIZATION." },
  { group: "Aussehen", id: "theme", title: "Schrift und Symbole", where: BOTH,
    text: "Eigene Schrift und Symbole auf dem Display, Seitenreiter mit gestanzter Ecke.",
    how: "Kommt mit dem Patch." },
  { group: "Aussehen", id: "power-off", title: "Blechy beim Ausschalten", where: BOTH,
    text: "Statt „Power Off“ winkt Blechy, dann geht das Bild aus wie eine alte Röhre.",
    how: "Ausschalten." },
  { group: "Aussehen", id: "poly-pink", title: "Akkorde in Pink", where: BOTH,
    text: "Im SEQUENCER-Modus zeigt ein Poly-Part Steps mit mehreren Noten in Pink.",
    how: "SEQUENCER-Modus, Poly-Part." },

  { group: "Plugins und Effekte", id: "plugins", title: "BLECH-Menü und Plugins", where: BOTH, image: "img/features/menu.svg",
    text: "Ein eigenes Menü am Gerät mit Plugins: Lauflichter, eigene Menüseiten, Spiele wie Snake und Tetris. Am Ende des Menüs wohnt Blechy.",
    how: "Am Gerät: Menü -> BLECH. Plugins holst du dir in der App unter BLECHTRIBE -> Plugins." },
  { group: "Plugins und Effekte", id: "presets", title: "Eigene Effekte", where: RED, image: "img/features/presets.svg",
    text: "128 Plätze für eigene MFX- und IFX-Presets, gebaut in der App mit Namen und echten Einheiten.",
    how: "In der App: BLECHTRIBE -> Baukasten. Einen fertigen Effekt nehmen oder selbst bauen." },
  { group: "Plugins und Effekte", id: "doom", title: "Doom", where: RED, image: "img/features/doom.svg",
    text: "Ja, wirklich.",
    how: "Erst die Dateien unter BLECHTRIBE -> Doom auf die Karte legen, dann SHIFT + TAP beim Einschalten." },

  { group: "Sicher und bequem", id: "rescue-switch", title: "Notschalter", where: BOTH,
    text: "Startet die Electribe ohne BLECHTRIBE, fast wie das Original.",
    how: "EXIT beim Einschalten halten." },
  { group: "Sicher und bequem", id: "sample-errors", title: "Klare Meldung bei kaputten Samples", where: RED,
    text: "Statt „Unknown Error“ nennt das Fenster das Sample und den Grund, und die übrigen Samples laden trotzdem.",
    how: "Kommt von selbst beim Laden." },
  { group: "Sicher und bequem", id: "migrate", title: "Ordner übernehmen", where: RED,
    text: "Beim ersten Start fragt BLECHTRIBE, ob dein Hacktribe- oder Electribe-Ordner auf der Karte übernommen werden soll.",
    how: "Erster Start mit Karte, MENU kopiert, EXIT startet ohne." },
  { group: "Sicher und bequem", id: "usb-update", title: "Update über USB", where: RED,
    text: "Ist BLECHTRIBE einmal drauf, kommt jedes weitere Update aus der App direkt über USB.",
    how: "In der App: BLECHTRIBE -> Firmware Patcher -> Update auf Gerät." },
  ...[
    // from docs/ideen.md: what is planned or still being worked out, so people know what comes
    ["usb-samples", "Samples übers Kabel", "Samples rein und raus und die Karte lesen, ohne sie aus der Electribe zu nehmen."],
    ["preset-edit", "Effekte am Gerät bauen", "Ein Menüpunkt Preset Edit: eigene Effekte direkt an der Electribe zusammenstellen und auf der Karte speichern."],
    ["fx-export", "Effekte vom Gerät sichern", "Die Effekte, wie sie gerade auf der Electribe sind, als Datei auf die Karte schreiben."],
    ["mod-live", "Modulationen live ausprobieren", "Eigene Modulationen aus dem Baukasten direkt auf der Electribe anhören, ohne Umweg über die Karte."],
    ["mac-midi", "MIDI in der Mac-App", "Die App spricht direkt über USB-MIDI mit der Electribe, so wie der Browser."],
    ["more-samples", "Mehr Platz für Samples", "Samples von der Karte nachladen, statt alle auf einmal in den Speicher zu legen."],
    ["factory-samples", "Werks-Samples ersetzen", "Eigene Samples direkt am Gerät auf die Plätze der Werks-Samples legen: SELECT DESTINATION beim Import erlaubt dann auch die Plätze unter 501."],
    ["modular-rack", "Modular Rack", "Kicks und andere Klänge im Browser bauen: Oszillatoren mit Kabeln verbinden und modulieren, das Ergebnis direkt als Sample auf die Electribe holen."],
    ["osc-drawer", "OSC Drawer", "Einen eigenen Oszillator auf dem Touchpad malen und als Sample speichern."],
    ["filters", "Eigene Filtertypen", "Neue Filter aus den Bausteinen, die die Electribe schon hat."],
    ["mfx-free", "Zweiter Master-Effekt ohne Touchpad", "Ein zweiter Master-Effekt, der unabhängig vom Touchpad läuft. Ob der Klangprozessor (DSP) das schafft, ist noch offen."],
    ["gapless", "Patternwechsel ohne Lücke", "Die kurze Stille beim Wechsel des Patterns soll verschwinden."],
    ["fast-load", "Schneller laden, weniger Strom", "Samples laden schneller, und mit Batterien hält die Electribe länger."],
    ["tap-free", "TAP frei belegen", "TAP mit einer Funktion deiner Wahl belegen."],
    ["blechy-voice", "Blechy mit Stimme", "Blechy begrüßt dich beim Einschalten mit einem Ton und lernt vielleicht sogar sprechen."],
    ["bugfixes", "Korgs Fehler beheben", "Bekannte Fehler der Firmware ausbessern, die Korg nicht mehr behebt."],
  ].map(([id, title, text]) => ({ group: SOON, id, title, text, where: [], image: "img/features/soon.svg", soon: true })),
];

/** A picture cut to the one bit per pixel of the display and drawn like the plugin pictures of the catalog. */
function drawFeature(canvas, src) {
  const picture = new Image();
  picture.onload = () => {
    const work = document.createElement("canvas");
    work.width = 128;
    work.height = 64;
    const ctx = work.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(picture, 0, 0, 128, 64);
    const rgba = ctx.getImageData(0, 0, 128, 64).data;
    const bytes = new Uint8Array(1024);
    for (let i = 0; i < 128 * 64; i++) {
      if (rgba[i * 4] + rgba[i * 4 + 1] + rgba[i * 4 + 2] > 3 * 127) bytes[(i >> 10) * 128 + (i & 127)] |= 1 << ((i >> 7) & 7);
    }
    drawDisplay(canvas, bytes);
  };
  picture.src = src;
}

const pictures = [];
/** A canvas for an entry's picture; drawn once the list is in the page, where the canvas has its colours. */
function pictureOf(f) {
  const canvas = el("canvas", { className: "cee-lcd cee-catalog-thumb", width: 128, height: 64 });
  canvas.setAttribute("aria-hidden", "true");
  pictures.push([canvas, f.image]);
  return canvas;
}

export function featuresPage(root) {
  const groups = [...new Set(FEATURES.map(f => f.group))];
  root.replaceChildren(
    el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: "Was BLECHTRIBE kann" })]),
    el("p", { className: "muted", textContent: "Alles, was BLECHTRIBE der Electribe 2 beibringt, und wie du drankommst. Die Spielhilfen lassen sich unter Menü -> BLECH -> FEATURES einzeln abschalten, EXIT beim Einschalten schaltet alles ab." }),
    ...groups.map(group => el("section", { className: "ui-section cee-feature-group" }, [
      el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: group })]),
      group === SOON ? el("p", { className: "muted", id: "cee-features-soon-lead", textContent: "Das kommt noch. Ohne Termin, und manches muss erst noch erforscht werden." }) : null,
      el("ul", { className: "cee-features" }, FEATURES.filter(f => f.group === group).map(f => el("li", { className: "cee-feature", id: `cee-feature-${f.id}` }, [
        f.image ? pictureOf(f) : null,
        el("h3", { textContent: f.title }),
        el("p", { textContent: f.text }),
        f.how ? el("div", { className: "cee-feature-how" }, [el("span", { className: "cee-feature-how-label", textContent: "So geht's" }), el("p", { textContent: f.how })]) : null,
        f.where.length ? Object.assign(el("ul", { className: "cee-feature-where" }, f.where.map(device => {
          const art = e2Outline(DEVICE[device]);
          art.setAttribute("aria-hidden", "true");
          const chip = el("li", { className: "ui-chip ui-chip-sm", title: DEVICE[device] }, [art, SHORT[device]]);
          chip.dataset.device = device;
          return chip;
        })), { ariaLabel: "Unterstützt" }) : null,
      ]))),
    ])),
  );
  for (const [canvas, src] of pictures.splice(0)) drawFeature(canvas, src);
}
