/** What the Rettung page (site/app/rescue.mjs) says. `status` uses the markers of docs/README.md. */

export const STATUS = {
  gemessen: { tone: "ok", text: "gemessen am Gerät", meaning: "Am Gerät beobachtet." },
  offline: { tone: "info", text: "offline gelesen", meaning: "Im Code oder im Emulator gelesen, am Gerät nicht gesehen." },
  hergeleitet: { tone: "info", text: "hergeleitet", meaning: "Aus Gemessenem geschlossen, selbst nicht gemessen." },
  offen: { tone: "warn", text: "offen, nicht geprüft", meaning: "Steht so in einer Anleitung oder ist vermutet, am Gerät nicht geprüft. Behandle es als ungeprüft." },
};

export const LINKS = {
  debrick: "https://github.com/bangcorrupt/hacktribe/wiki/Debrick",
  howTo: "https://github.com/bangcorrupt/hacktribe/wiki/How-To",
  issues: "https://github.com/KuhlerBuhler/kuhlers-gelumpe/issues",
};

/** What Blechy says between the steps of the question flow; the steps themselves are the cases below. */
export const TALK = {
  hello: "Moin, ich bin Blechy. Keine Panik, wir kriegen das hin. Was zeigt deine Electribe, wenn du sie einschaltest?",
  helped: "Hat geholfen",
  notHelped: "Hilft nicht",
  fixed: "Jut. Mit gehaltenem EXIT startet sie nur dieses Mal ohne BLECHTRIBE. Spinnt sie beim nächsten normalen Start wieder, komm zurück, dann gehen wir auf die alte Firmware.",
  before: "Dann gehen wir zurück auf deine alte Firmware. Vorher zwei Sachen:",
  ready: "Hab ich bereit",
  notReady: "Hab ich nicht",
  noBackup: "Ohne die gesicherte Original-SYSTEM.VSB gibt es diesen Weg zurück nicht. Such die Sicherung, zum Beispiel auf dem Schreibtisch oder in deinem Download-Ordner, und fang dann von vorn an.",
  which: "Welche Firmware läuft gerade auf deiner Electribe?",
  folder: "Leg deine gesicherte Original-SYSTEM.VSB auf der Karte hierhin:",
  done: "Hab ich gemacht",
  // A line of parts like the stop sign's: { link } is a key of LINKS.
  end: ["Kommst du nicht weiter, schick ein Foto vom Display und was du zuletzt gemacht hast, ", { link: "issues", text: "als GitHub Issue" }, " oder auf Instagram. Probier nichts auf Verdacht."],
  again: "Von vorn",
  back: "Zurück",
};

export default {
  stop: {
    title: "Stopp: der Bootloader wird nie angefasst",
    lines: [
      "Weder der Editor noch du solltest je den Bootloader beschreiben. Der Editor sperrt ihn (Flash 0x000000 bis 0x020000) und hat keinen Weg, dorthin zu schreiben.",
      ["Hängt das Gerät schon, bevor eine Update-Abfrage kommt, hilft nach ", { link: "debrick", text: "der Anleitung von Hacktribe" }, " nur noch JTAG mit OpenOCD, und ein defekter Secondary Bootloader braucht eine eigene Wiederherstellung. Dann nichts weiter ausprobieren."],
    ],
  },

  before: [
    "Lege vor jedem Update die gesicherte Original-SYSTEM.VSB bereit. Ohne sie gibt es den Weg zurück nicht.",
    "Netzteil anschließen oder frische Batterien einlegen, und das Gerät während des Updates nicht ausschalten.",
    "Halte beim Einschalten keine anderen Tasten als die hier genannten. Bestimmte Tastenpaare führen in Testseiten der Fertigung, was dort passiert, ist nicht untersucht.",
  ],

  // Every folder is checked on devices: version 1.2 went onto four of the author's Electribes and many from the internet.
  folders: [
    { title: "Korg Electribe 2 Sampler", body: "red", path: "KORG/electribe sampler/System/SYSTEM.VSB" },
    { title: "Korg Electribe 2", body: "blue", path: "KORG/electribe/System/SYSTEM.VSB" },
    { title: "Electribe 2 / 2s + Hacktribe", body: "grey", path: "KORG/hacktribe/System/SYSTEM.VSB" },
    { title: "Electribe 2 / 2s + BLECHTRIBE (+ Hacktribe optional)", body: "grey", path: "KORG/blechtribe/System/SYSTEM.VSB" },
  ],

  cases: [
    {
      id: "starts",
      label: "Das Gerät startet, aber etwas stimmt nicht",
      hint: "Das Menü hängt, zeigt Unsinn, oder ein Patch oder Plugin macht Ärger.",
      steps: [
        {
          text: "Menü hängt oder zeigt Unsinn: EXIT drücken. Hilft das nicht, das Gerät ausschalten und mit gehaltenem EXIT wieder einschalten. Dann gibt BLECHTRIBE nur an die Original-Firmware weiter, und nur für diesen Start.",
          status: "offen",
          note: "Am Gerät bestätigt ist der Notschalter nur für den MFX-2-Patch (13.10.), für den ganzen BLECHTRIBE-Satz nicht. Er hilft nicht gegen kaputte Startdaten, DSP-Patches, kaputte gespeicherte Daten und Patches, die den Panel-Austausch stören.",
        },
        {
          act: true,
          text: "Die gesicherte Original-SYSTEM.VSB auf der Karte in den Ordner der Firmware legen, die jetzt läuft (Tabelle oben). Am Rechner die Prüfsumme der Datei auf der Karte nachlesen, sie muss der der gesicherten Datei gleichen.",
          status: "gemessen",
          note: "So am 10.10. geübt, mit Hacktribe. Der Ordner von BLECHTRIBE ist am 15.10. am Gerät gesehen.",
        },
        {
          act: true,
          text: "Karte in das ausgeschaltete Gerät, Netzteil anschließen, einschalten. DATA UTILITY, dann SOFTWARE UPDATE. Direkt davor steht FACTORY RESET in der Liste: das nicht bestätigen.",
          status: "gemessen",
          note: "Das Update über das Menü lief am 10.10. am Gerät durch. Dass FACTORY RESET direkt davor steht, steht in der Anleitung für den Gerätetest.",
        },
        {
          act: true,
          text: "Die Versionsanzeige ansehen, bestätigen, den Abschluss abwarten, dann ausschalten und neu einschalten. Das Gerät startet wieder mit der alten Firmware.",
          status: "gemessen",
          note: "Am Gerät zurück auf das alte Startbild beobachtet. Die Anzeige \"Now 2.02, Next 2.02\" und \"OK. Please Reboot.\" stammen aus dem Emulator.",
        },
      ],
      limit: "Das ist Korgs normaler Updateweg. Er setzt eine laufende Anwendung voraus und beweist keine Wiederherstellung nach jedem Firmwarefehler.",
    },
    {
      id: "prompt",
      label: "Beim Einschalten steht SOFTWARE UPDATE und press ENTER",
      hint: "Das Gerät fragt nach einer Update-Datei, statt zu starten.",
      steps: [
        {
          text: "Diese Abfrage gehört zur Firmware, nicht zum Bootloader. Sie kommt, wenn die Kennung der Nutzerdaten im Flash fehlt.",
          status: "offline",
        },
        {
          act: true,
          text: "Leg Korgs Original-Firmware für den Sampler auf die Karte: KORG/electribe sampler/System/SYSTEM.VSB. Das ist ein anderer Ordner als der von Hacktribe oder BLECHTRIBE.",
          status: "gemessen",
          note: "Am Gerät so bestätigt (23.10.). Die Hacktribe-Dokumentation beschreibt denselben Weg.",
        },
        {
          act: true,
          text: "Karte ins ausgeschaltete Gerät, Netzteil anschließen, einschalten. Bei der Abfrage ENTER drücken, das Update durchlaufen lassen, dann aus- und wieder einschalten. Das Gerät startet wieder mit Korgs Firmware.",
          status: "gemessen",
          note: "Am Gerät bestätigt (23.10.). Im Emulator suchte die Abfrage die Datei an der Kartenwurzel und meldete \"Error, Invalid File\"; warum, ist offen.",
        },
      ],
      limit: "Das ist der Weg ohne JTAG, wenn die laufende Firmware nicht mehr startet. Danach kannst du BLECHTRIBE wie beim ersten Mal wieder aufspielen.",
    },
    {
      id: "zero",
      label: "Das Display zeigt nur 00",
      hint: "Beim Einschalten erscheint die Anzeige 00.",
      steps: [
        {
          text: "So zeigt die Firmware das Panel-Update: Sie fragt den Panel-Controller nach seiner Version und erwartet 0x96. Bei einer anderen Antwort oder keiner startet das Panel-Update mit der Anzeige 00. Das passt zum Debrick-Wiki von Hacktribe.",
          status: "offline",
        },
        {
          act: true,
          text: "Leg Korgs Original-Firmware für den Sampler auf die Karte: KORG/electribe sampler/System/SYSTEM.VSB.",
          status: "gemessen",
          note: "Bei 00 am Gerät so bestätigt (23.10.).",
        },
        {
          act: true,
          text: "Karte ins ausgeschaltete Gerät, Netzteil anschließen, einschalten. Das Gerät fragt nach dem Update: ENTER drücken, das Update durchlaufen lassen, dann aus- und wieder einschalten. Danach startet es wieder.",
          status: "gemessen",
          note: "Am Gerät bestätigt (23.10.).",
        },
      ],
      limit: "Kommt keine Update-Abfrage und das Gerät hängt weiter, gilt das Stopp-Schild: nach der Anleitung von Hacktribe nur JTAG.",
    },
    {
      id: "silent",
      label: "Das Gerät startet nicht und fragt auch nichts",
      hint: "Das Display bleibt dunkel oder hängt ohne eine Abfrage.",
      steps: [
        {
          text: "Die Dokumentation kennt hier keinen Weg über die Karte. Nach der Anleitung von Hacktribe bleibt JTAG mit OpenOCD, ein defekter Secondary Bootloader braucht eine eigene Wiederherstellung.",
          status: "offen",
          note: "Aus der Debrick-Anleitung von Hacktribe. Der Editor führt dich dort nicht weiter und schreibt nie in diesen Bereich.",
        },
      ],
      limit: "Das ist das Stopp-Schild: nichts weiter ausprobieren.",
    },
  ],
};
