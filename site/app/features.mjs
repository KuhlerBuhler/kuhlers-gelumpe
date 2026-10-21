/**
 * The page Features under Gerät: everything BLECHTRIBE adds, what it does and how to reach it on
 * the device. The start page shows a few of the same entries as cards (`home: true`). The facts
 * come from README.md ("Was kann was?") and docs/patcher.md; a new patch gets its entry here.
 */
import { el } from "./fields.mjs";

const BOTH = "Rot und blau";
const RED = "Nur rot";

/** One entry per function. `how` is what you press, `where` which Electribe has it, `image` a picture for the start page. */
export const FEATURES = [
  { group: "Spielen", id: "note-assist", home: true, title: "Notenassistent", where: BOTH, image: "img/features/note-assist.svg",
    text: "Im KEYBOARD-Modus leuchten nach einer Note die Pads, die dazu passen. Je heller, desto besser passt die Note. Im CHORD-Modus zeigt er die passenden nächsten Akkorde.",
    how: "KEYBOARD-Modus, eine Note spielen. Abschalten im Menü BLECH, Seite NOTE ASSISTANT." },
  { group: "Spielen", id: "dice", home: true, title: "Würfeln", where: BOTH, image: "img/features/dice.svg",
    text: "Schreibt eine neue Melodie in den gewählten Part, aus Tonart und Tonleiter des Patterns. Gespeichert wird erst mit WRITE.",
    how: "SHIFT + PART ERASE." },
  { group: "Spielen", id: "tap-motion", home: true, title: "TAP Motion", where: BOTH, image: "img/features/tap-motion.svg",
    text: "TAP schaltet die aufgenommene Motion Sequence des gewählten Parts an und aus. Die TAP-Lampe zeigt, ob sie läuft. Das Tap-Tempo fällt dafür weg.",
    how: "TAP drücken. MASTER FX halten + TAP für die Master-FX-Gesten. Einstellen im Menü BLECH, Seite TAP MOTION." },
  { group: "Spielen", id: "pattern-switch", home: true, title: "Patternwechsel mit Bestätigung", where: BOTH, image: "img/features/pattern-switch.svg",
    text: "Beim Spielen blättert das Rad nur durch die Patterns. Gewechselt wird erst, wenn du bestätigst.",
    how: "Rad drehen, MENU bestätigt, EXIT nimmt zurück." },
  { group: "Spielen", id: "mfx2", home: true, title: "Zweiter Master-Effekt", where: BOTH, image: "img/features/mfx2.svg",
    text: "TOUCH SCALE wird zu MFX 2: ein zweiter Master-Effekt pro Pattern.",
    how: "TOUCH SCALE drücken." },
  { group: "Spielen", id: "exit-write", home: true, title: "Schnell speichern", where: RED, image: "img/features/exit-write.svg",
    text: "Speichert das Pattern an seinen Platz, ohne Fenster. Solange etwas ungespeichert ist, atmet die WRITE-LED.",
    how: "EXIT halten + WRITE." },
  { group: "Spielen", id: "exit-pad", title: "Part zurücksetzen", where: RED,
    text: "Setzt den Klang eines Parts auf die gespeicherten Werte zurück.",
    how: "EXIT halten + Pad des Parts." },

  { group: "Aussehen", id: "splash", home: true, title: "Eigenes Startbild", where: BOTH, image: "img/features/splash.png",
    text: "Dein Bild beim Einschalten, selbst gemalt im Bereich Startbildschirm. Auf der roten auch direkt am Gerät.",
    how: "In der App unter Firmware, Startbildschirm." },
  { group: "Aussehen", id: "loading", home: true, title: "Ladeanimation", where: RED, image: "img/features/loading.png",
    text: "Solange die Samples laden, zieht Blechy eine Line über den Tisch, darunter stehen die Prozent.",
    how: "Kommt von selbst beim Einschalten." },
  { group: "Aussehen", id: "colors", home: true, title: "Pad- und LED-Farben", where: BOTH, image: "img/features/colors.svg",
    text: "Farben für Pads, den gewählten Part, die unteren LEDs und das Display-Licht. Im Power Save werden die LEDs gedimmt.",
    how: "Menü BLECH, Gruppe CUSTOMIZATION." },
  { group: "Aussehen", id: "theme", title: "Schrift und Symbole", where: BOTH,
    text: "Eigene Schrift und Symbole auf dem Display, Seitenreiter mit gestanzter Ecke.",
    how: "Kommt mit dem Patch." },
  { group: "Aussehen", id: "power-off", title: "Blechy beim Ausschalten", where: BOTH,
    text: "Statt „Power Off“ winkt Blechy, dann geht das Bild aus wie eine alte Röhre.",
    how: "Ausschalten." },
  { group: "Aussehen", id: "poly-pink", title: "Akkorde in Pink", where: RED,
    text: "Im SEQUENCER-Modus zeigt ein Poly-Part Steps mit mehreren Noten in Pink.",
    how: "SEQUENCER-Modus, Poly-Part." },

  { group: "Plugins und Effekte", id: "plugins", home: true, title: "BLECH-Menü und Plugins", where: BOTH, image: "img/features/menu.png",
    text: "Ein eigenes Menü am Gerät mit Plugins: Lauflichter, eigene Menüseiten, Spiele wie Snake und Tetris. Am Ende des Menüs wohnt Blechy.",
    how: "Menü BLECH am Gerät. Plugins holst du dir in der App unter Plugins." },
  { group: "Plugins und Effekte", id: "presets", home: true, title: "Eigene Effekte", where: RED, image: "img/features/presets.svg",
    text: "128 Plätze für eigene MFX- und IFX-Presets, gebaut in der App mit Namen und echten Einheiten.",
    how: "In der App unter Sound, Presets." },
  { group: "Plugins und Effekte", id: "doom", home: true, title: "Doom", where: RED, image: "img/features/doom.svg",
    text: "Ja, wirklich.",
    how: "SHIFT + TAP beim Einschalten." },

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
    how: "Firmware Patcher, Schritt Aufs Gerät." },
];

export function featuresPage(root) {
  const groups = [...new Set(FEATURES.map(f => f.group))];
  root.replaceChildren(
    el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: "Was BLECHTRIBE kann" })]),
    el("p", { className: "muted", textContent: "Alles, was BLECHTRIBE der Electribe 2 beibringt, und wie du drankommst. Die Spielhilfen lassen sich im Menü BLECH einzeln abschalten, EXIT beim Einschalten schaltet alles ab." }),
    ...groups.map(group => el("section", { className: "ui-section cee-feature-group" }, [
      el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: group })]),
      el("ul", { className: "cee-features" }, FEATURES.filter(f => f.group === group).map(f => el("li", { className: "cee-feature", id: `cee-feature-${f.id}` }, [
        el("h3", { textContent: f.title }),
        el("p", { textContent: f.text }),
        el("p", { className: "cee-feature-how" }, [el("strong", { textContent: "So geht's: " }), f.how]),
        el("span", { className: "cee-feature-where", textContent: f.where }),
      ]))),
    ])),
  );
}
