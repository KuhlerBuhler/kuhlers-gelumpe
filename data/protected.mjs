/**
 * The regions the editor never writes to, as a machine rule.
 *
 * docs/speicherbereiche.md is the map this list is cut from: every entry names
 * the measurement it rests on, and `status` says whether the boundary was
 * measured or is a protection proposal. The gate (src/gate.mjs) and the sender
 * (src/sender.mjs) both read it through src/protect.mjs, so a message the
 * terminal builds meets the same rule as one the effect editor builds.
 *
 * This list sits on top of the allow list (`allowedRegions()` in src/plan.mjs),
 * it does not replace it. A write has to fit a declared region and must not
 * touch an entry here. An entry may name `except`: the declared regions (by
 * `what`, a prefix up to the first space) that are allowed to lie inside it,
 * because the editor edits exactly those bytes and a test holds that no other
 * declared region overlaps an entry. Without `except` nothing may touch it.
 *
 * `deny` is "write" or "any". Writing is refused everywhere in the list; reads
 * are refused only where an access itself is a risk (a port, memory the device
 * stops answering for, the loader).
 *
 * Intervals are half open. RAM is the CPU address space, flash the offsets of
 * the Hacktribe flash read command. The two never mix: a RAM address is no
 * flash offset.
 */

export default {
  ram: {
    /** The window that answered every read, measured. Nothing outside it is known, so nothing outside it is touched. */
    window: { start: 0xc0000000, end: 0xc8000000, evidence: "measure:2026-10-07/cpu-ram-fenster" },
    /**
     * The upper 64 MiB of the window repeat the lower ones nearly byte for byte
     * (4074 of 4096 block pairs equal). Not proven to be a mirror, so a write to
     * one half is checked against the protected regions of the other too.
     */
    mirror: { distance: 0x4000000, status: "assumed", evidence: "measure:2026-10-07/cpu-ram-fenster" },
  },
  regions: [
    {
      id: "firmware-image", space: "ram", start: 0xc0000000, end: 0xc0200000, deny: "write", status: "measured",
      except: ["table.ifx", "table.mfx", "preset.stock", "menu.ifxCount", "menu.mfxCount"],
      what: "Firmware-Abbild",
      why: "Code und statische Daten der Firmware. Frei sind nur die erklärten Tabellen (Hacktribes und die Preset-Records von Korgs Build) und Menüzähler.",
      evidence: "measure:2026-10-08/systemspeicher-offline",
    },
    {
      id: "sysex-hook", space: "ram", start: 0xc0170540, end: 0xc0171fec, deny: "write", status: "measured",
      what: "SysEx-Haken und eingebetteter Loader",
      why: "Der Haken, über den der Editor mit dem Gerät spricht, mit Cache- und Startcode.",
      evidence: "measure:2026-10-08/boot-pattern-speicher",
    },
    {
      id: "task-stacks", space: "ram", start: 0xc0200000, end: 0xc03167a8, deny: "write", status: "measured",
      what: "Task-Stacks",
      why: "Zehn Task-Stacks, vom Boot angelegt, die gespeicherten Zeiger passen. Auch scheinbar ungenutzte Bytes gehören dazu.",
      evidence: "measure:2026-10-08/systemspeicher-offline",
    },
    {
      id: "task-control-blocks", space: "ram", start: 0xc06a24e4, end: 0xc06a2624, deny: "write", status: "measured",
      what: "Task-Kontrollblöcke",
      why: "Zehn Kontrollblöcke mit Deskriptor- und Stackzeigern, Kernelzustand.",
      evidence: "measure:2026-10-08/systemspeicher-offline",
    },
    {
      id: "heap", space: "ram", start: 0xc06a2940, end: 0xc08a2940, deny: "write", status: "measured",
      what: "Heap",
      why: "Der 2-MiB-Pool des untersuchten New/Delete-Pfads; frei heißt hier nicht fremd nutzbar.",
      evidence: "measure:2026-10-08/systemspeicher-offline",
    },
    {
      id: "boot-clear", space: "ram", start: 0xc0200000, end: 0xc08a2940, deny: "write", status: "measured",
      except: ["display", "sample.name", "sample.tune"],
      what: "Boot-Löschbereich",
      why: "Task-Stacks, Systemdaten und Heap, die der Boot löscht und füllt. Frei sind nur der Display-Puffer und Name und Tune je Sample (am Gerät geschrieben, measure:2026-10-07).",
      evidence: "measure:2026-10-08/systemspeicher-offline",
    },
    {
      id: "sample-info-cache", space: "ram", start: 0xc0c9a940, end: 0xc0d3a940, deny: "write", status: "measured",
      what: "Sample-Info-Cache",
      why: "Der 640-KiB-Cache der Sample-Tabellen, kein PCM und kein freier Uploadspeicher.",
      evidence: "measure:2026-10-08/boot-pattern-speicher",
    },
    {
      id: "work-buffer", space: "ram", start: 0xc0d3a940, end: 0xc273aa40, deny: "write", status: "measured",
      except: ["stub buffer"],
      what: "Datei- und Sample-Arbeitspuffer",
      why: "Gemeinsamer Puffer für Import, Export und den SysEx-Haken. Frei ist nur das erste KiB für Stubs.",
      evidence: "measure:2026-10-08/systemspeicher-offline",
    },
    {
      id: "start-stack", space: "ram", start: 0xc273aa40, end: 0xc274aa40, deny: "write", status: "proposal",
      what: "Startstack",
      why: "Der Stack wächst vom Reset-SP 0xC274AA40 hinein, die größte Tiefe ist nicht gemessen. Konservativ reserviert.",
      evidence: "measure:2026-10-08/boot-pattern-speicher",
    },
    {
      id: "irq-stack", space: "ram", start: 0xc274aa40, end: 0xc274ea3c, deny: "write", status: "measured",
      what: "Interrupt- und Idle-Stack",
      why: "Füllbereich und Umschaltung der Interrupts, geprüft.",
      evidence: "measure:2026-10-08/boot-pattern-speicher",
    },
    {
      id: "loader", space: "ram", start: 0xffff0000, end: 0xffff125c, deny: "any", status: "measured",
      what: "Loader-Kopie",
      why: "Loadercode, Dateninitialisierung und sechs CPU-Modus-Stackzeiger.",
      evidence: "measure:2026-10-08/boot-pattern-speicher",
    },
    {
      id: "dsp-ports", space: "ram", start: 0x60000000, end: 0x60000004, deny: "any", status: "proposal",
      what: "DSP-Ports",
      why: "Datenport 0x60000000 und Steuerport 0x60000002 gehören zu einem Protokoll mit Handshake. Ein einzelner Zugriff stört den Austausch.",
      evidence: "measure:2026-10-08/dsp-audiopfade",
    },

    // Flash: no write path is approved anywhere. The list cuts [0, FLASH_END) into the areas the map knows.
    {
      id: "flash-bootloader", space: "flash", start: 0x000000, end: 0x020000, deny: "write", status: "measured",
      what: "Bootloader",
      why: "Startimage (TIPA/AIS) und Bootloader. Ist er defekt, hilft nur JTAG.",
      evidence: "measure:2026-10-07/werks-sample-flash",
    },
    {
      id: "flash-firmware", space: "flash", start: 0x020000, end: 0x220000, deny: "write", status: "measured",
      what: "Firmware",
      why: "Das 2-MiB-Abbild der Firmware.",
      evidence: "measure:2026-10-07/werks-sample-flash",
    },
    {
      id: "flash-user-data", space: "flash", start: 0x220000, end: 0x640000, deny: "write", status: "measured",
      what: "Nutzerdaten",
      why: "Nutzerkennung, Globals und Patternbank. Wiederherstellbar, aber ein Flash-Schreibweg ist nicht freigegeben.",
      evidence: "measure:2026-10-07/werks-sample-flash",
    },
    {
      id: "flash-factory-patterns", space: "flash", start: 0x640000, end: 0x660017, deny: "write", status: "measured",
      what: "Werks-Patternbank",
      why: "Die komprimierte Patternbank des Werks.",
      evidence: "measure:2026-10-07/werks-sample-flash",
    },
    {
      id: "flash-unassigned", space: "flash", start: 0x660017, end: 0x800000, deny: "write", status: "measured",
      what: "Nicht zugeordnet",
      why: "Gemessen nur FF und in allen Ständen gleich, dass die Firmware es nie beschreibt ist nicht gemessen.",
      evidence: "measure:2026-10-09/flash-dump",
    },
    {
      id: "flash-factory-samples", space: "flash", start: 0x800000, end: 0xe5f013, deny: "write", status: "measured",
      what: "Werks-Samplebank",
      why: "Tabellen und der Block-Strom der Werks-Samples. Bekannte Kodierung heißt nicht sichere Schreibbarkeit.",
      evidence: "measure:2026-10-07/werks-sample-flash",
    },
    {
      id: "flash-tail", space: "flash", start: 0xe5f013, end: 0x1000000, deny: "write", status: "measured",
      what: "Flash-Ende",
      why: "Gemessen nur FF und in allen Ständen gleich.",
      evidence: "measure:2026-10-09/flash-dump",
    },
  ],
};
