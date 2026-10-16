/** What the Rettung page (site/app/rescue.mjs) says. `status` uses the markers of docs/README.md, `source` names the file that backs the step. */

export const STATUS = {
  gemessen: { tone: "ok", text: "gemessen am Gerät", meaning: "Am Gerät beobachtet." },
  offline: { tone: "info", text: "offline gelesen", meaning: "Im Code oder im Emulator gelesen, am Gerät nicht gesehen." },
  hergeleitet: { tone: "info", text: "hergeleitet", meaning: "Aus Gemessenem geschlossen, selbst nicht gemessen." },
  offen: { tone: "warn", text: "offen, nicht geprüft", meaning: "Steht so in einer Anleitung oder ist vermutet, am Gerät nicht geprüft. Behandle es als ungeprüft." },
};

export const LINKS = {
  debrick: "https://github.com/bangcorrupt/hacktribe/wiki/Debrick",
  howTo: "https://github.com/bangcorrupt/hacktribe/wiki/How-To",
};

export default {
  stop: {
    title: "Stopp: der Bootloader wird nie angefasst",
    lines: [
      "Weder der Editor noch du solltest je den Bootloader beschreiben. Der Editor sperrt ihn (Flash 0x000000 bis 0x020000) und hat keinen Weg, dorthin zu schreiben.",
      "Hängt das Gerät schon, bevor eine Update-Abfrage kommt, hilft nach der Anleitung von Hacktribe nur noch JTAG mit OpenOCD, und ein defekter Secondary Bootloader braucht eine eigene Wiederherstellung. Dann nichts weiter ausprobieren.",
    ],
    source: "docs/messungen/2026-10-08-firmware-rueckweg.md",
  },

  before: [
    "Lege vor jedem Update die gesicherte Original-SYSTEM.VSB bereit. Ohne sie gibt es den Weg zurück nicht.",
    "Netzteil anschließen oder frische Batterien einlegen, und das Gerät während des Updates nicht ausschalten.",
    "Halte beim Einschalten keine anderen Tasten als die hier genannten. Bestimmte Tastenpaare führen in Testseiten der Fertigung, was dort passiert, ist nicht untersucht.",
  ],

  folders: [
    {
      running: "Hacktribe",
      path: "KORG/hacktribe/System/SYSTEM.VSB",
      status: "gemessen",
      note: "Das liest die laufende Hacktribe-Firmware. Am 10.10. am Gerät hin und zurück geübt.",
      source: "docs/messungen/2026-10-10-rueckweg-geuebt.md",
    },
    {
      running: "BLECH",
      path: "KORG/blechtribe/System/SYSTEM.VSB",
      status: "gemessen",
      note: "Das liest die laufende BLECH. Am 15.10. am Gerät gesehen: sie nahm ihr Update aus dieser Datei.",
      source: "docs/geraetetests/blech-datei.md",
    },
    {
      running: "Korgs Original",
      path: "KORG/electribe sampler/System/SYSTEM.VSB",
      status: "offen",
      note: "Der Pfad der Werksfirmware für einen als Sampler verkauften Electribe laut Hacktribe-Doku. Am Gerät nicht geübt.",
      source: "docs/messungen/2026-10-08-firmware-rueckweg.md",
    },
  ],

  cases: [
    {
      id: "starts",
      label: "Das Gerät startet, aber etwas stimmt nicht",
      hint: "Das Menü hängt, zeigt Unsinn, oder ein Patch oder Plugin macht Ärger.",
      steps: [
        {
          text: "Menü hängt oder zeigt Unsinn: EXIT drücken. Hilft das nicht, das Gerät ausschalten und mit gehaltenem EXIT wieder einschalten. Dann gibt BLECH nur an die Original-Firmware weiter, und nur für diesen Start.",
          status: "offen",
          note: "Am Gerät bestätigt ist der Notschalter nur für den MFX-2-Patch (13.10.), für den ganzen BLECH-Satz nicht. Er hilft nicht gegen kaputte Startdaten, DSP-Patches, kaputte gespeicherte Daten und Patches, die den Panel-Austausch stören.",
          source: "docs/geraetetests/blech-datei.md",
        },
        {
          text: "Die gesicherte Original-SYSTEM.VSB auf der Karte in den Ordner der Firmware legen, die jetzt läuft (Tabelle oben). Am Rechner die Prüfsumme der Datei auf der Karte nachlesen, sie muss der der gesicherten Datei gleichen.",
          status: "gemessen",
          note: "So am 10.10. geübt, mit Hacktribe. Der Ordner von BLECH ist am 15.10. am Gerät gesehen.",
          source: "docs/messungen/2026-10-10-rueckweg-geuebt.md",
        },
        {
          text: "Karte in das ausgeschaltete Gerät, Netzteil anschließen, einschalten. DATA UTILITY, dann SOFTWARE UPDATE. Direkt davor steht FACTORY RESET in der Liste: das nicht bestätigen.",
          status: "gemessen",
          note: "Das Update über das Menü lief am 10.10. am Gerät durch. Dass FACTORY RESET direkt davor steht, steht in der Anleitung für den Gerätetest.",
          source: "docs/messungen/2026-10-10-rueckweg-geuebt.md",
        },
        {
          text: "Die Versionsanzeige ansehen, bestätigen, den Abschluss abwarten, dann ausschalten und neu einschalten. Das Gerät startet wieder mit der alten Firmware.",
          status: "gemessen",
          note: "Am Gerät zurück auf das alte Startbild beobachtet. Die Anzeige \"Now 2.02, Next 2.02\" und \"OK. Please Reboot.\" stammen aus dem Emulator.",
          source: "docs/messungen/2026-10-10-rueckweg-geuebt.md",
        },
      ],
      limit: "Das ist Korgs normaler Updateweg. Er setzt eine laufende Anwendung voraus und beweist keine Wiederherstellung nach jedem Firmwarefehler.",
      limitSource: "docs/messungen/2026-10-08-firmware-rueckweg.md",
    },
    {
      id: "prompt",
      label: "Beim Einschalten steht SOFTWARE UPDATE und press ENTER",
      hint: "Das Gerät fragt nach einer Update-Datei, statt zu starten.",
      steps: [
        {
          text: "Diese Abfrage gehört zur Firmware, nicht zum Bootloader. Sie kommt, wenn die Kennung der Nutzerdaten im Flash fehlt.",
          status: "offline",
          source: "docs/messungen/2026-10-08-emulator-boot.md",
        },
        {
          text: "Eine passende Werksfirmware auf der Karte kann die Wiederherstellung ermöglichen. Für einen ursprünglich als Sampler verkauften Electribe liegt sie unter KORG/electribe sampler/System/SYSTEM.VSB. Das ist ein anderer Pfad als der der laufenden Hacktribe.",
          status: "offen",
          note: "So beschreibt es die Hacktribe-Dokumentation. Am Gerät ist dieser Weg nicht geübt. Ob die Datei, die schon unter diesem Pfad lag, eine passende Werksfirmware ist, blieb im Test offen.",
          source: "docs/messungen/2026-10-08-firmware-rueckweg.md",
        },
        {
          text: "Karte ins ausgeschaltete Gerät, Netzteil, einschalten, bei der Abfrage ENTER drücken.",
          status: "offen",
          source: "docs/geraetetests/blech-datei.md",
        },
        {
          text: "Im Emulator suchte die Abfrage System/SYSTEM.VSB an der Kartenwurzel, ohne KORG davor, und meldete \"Error, Invalid File\". Warum, ist offen. Klappt es am Gerät nicht, nichts weiter ausprobieren.",
          status: "offline",
          source: "docs/hintergrund/virtuelle-sd.md",
        },
      ],
      limit: "Das ist der einzige dokumentierte Weg ohne JTAG, wenn die laufende Firmware nicht mehr startet, und er ist am Gerät ungeübt.",
      limitSource: "docs/ideen/offene-messungen.md",
    },
    {
      id: "zero",
      label: "Das Display zeigt nur 00",
      hint: "Beim Einschalten erscheint die Anzeige 00.",
      steps: [
        {
          text: "So zeigt die Firmware das Panel-Update: Sie fragt den Panel-Controller nach seiner Version und erwartet 0x96. Bei einer anderen Antwort oder keiner startet das Panel-Update mit der Anzeige 00. Das passt zum Debrick-Wiki von Hacktribe.",
          status: "offline",
          source: "docs/messungen/2026-10-08-emulator-boot.md",
        },
        {
          text: "Welche Schritte am Gerät bei 00 helfen, ist in diesem Projekt nicht gemessen. Einen geübten Rettungsweg dafür gibt es nicht. Nicht auf Verdacht Tasten halten oder Dateien tauschen.",
          status: "offen",
          source: "docs/ideen.md",
        },
        {
          text: "Kommt danach die Update-Abfrage, gilt der Fall davor. Hängt das Gerät ohne eine Update-Abfrage, gilt das Stopp-Schild: nach der Anleitung von Hacktribe nur JTAG.",
          status: "offen",
          note: "Aus der Debrick-Anleitung von Hacktribe, am Gerät nicht nachgestellt.",
          source: "docs/messungen/2026-10-08-firmware-rueckweg.md",
        },
      ],
      limit: "Eine Firmware, die vor dem Panel-Austausch, den gehaltenen Tasten und der Update-Abfrage hängt, ist ohne JTAG nicht zu retten.",
      limitSource: "docs/patcher.md",
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
          source: "docs/messungen/2026-10-08-firmware-rueckweg.md",
        },
      ],
      limit: "Das ist das Stopp-Schild: nichts weiter ausprobieren.",
      limitSource: "docs/messungen/2026-10-08-firmware-rueckweg.md",
    },
  ],
};
