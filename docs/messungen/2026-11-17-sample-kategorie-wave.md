# Sample-Kategorie "Wave" auf Hacktribe: braucht e2sSample.all ein Wave-Sample?

17.11.2026, Emulator (unicorn, `tools/emu`), kein Gerät. Firmware: Korg 2.02 rot (`1d0f0689`) und Hacktribe (`163d1d8d`),
jeweils ohne BLECH-Patch. Frage (17.11.): HT liest `e2sSample.all` angeblich nicht mehr, wenn kein Sample in der
Kategorie User/"Wave" steht. Warum?

Ergebnis: **im Emulator nicht nachstellbar.** HT liest, exportiert und lädt wieder eine Datei ohne ein einziges Wave-Sample.
Im Code gibt es keine Stelle, die ein Wave-Sample braucht.

Markierungen: **gemessen** (Emulator), **offline** (Disassembly gelesen), **hergeleitet**.

## Belegtabelle

| Aussage | Status | Beleg |
|---|---|---|
| HT zeigt Kategorie 17 als "Wave" (rot "User"). Feld: Namenseintrag `0xC047B08C + Slot*32 + 0x10` = `esli[18:20]` | offline | Texttabelle von `0xC007881C`, siehe docs der Recherche (Sprungtabelle `0xC0078874`) |
| HT lädt eine Datei mit 3 Samples (501, 502, 601), alle Kategorie 2: alle 3 geladen, 0 Assertions | gemessen | Probe `users_cat2` |
| HT lädt eine Datei mit allen 499 User-Plätzen (501 bis 999), alle Kategorie 0 (kein Wave): 499/499 geladen | gemessen | Probe `allusers_cat0` |
| Gleiche Datei, ein Sample auf 17: 499/499, kein Unterschied | gemessen | Probe `allusers_one17` |
| HT: diese Datei ohne Wave laden, EXPORT ALL SAMPLE, Neustart mit der neuen Karte: Datei hat 499 Einträge, alle Kategorie 0; nach dem Neustart 499/499 geladen, 0 Assertions | gemessen | `export_probe.py` |
| Rot verhält sich gleich (`allusers_cat0`: 499/499) | gemessen | Gegenprobe |
| Im RAM gibt es immer Einträge mit 17: jeder leere Platz bekommt beim Start 17 (HT nach Laden von 499 Samples noch 226 Einträge, rot 79). "Kein Wave" gibt es also nur in der Datei, nie im RAM | gemessen + offline | Histogramm der Kategorien über Slot 0 bis 999; Platz leeren `0xC004DF90` schreibt 17 bei `0xC004E178` |
| Der Ladeweg von HT ist bis auf zwei Konstanten gleich wie rot; keine der Änderungen liest die Kategorie | offline | Bytevergleich `0xC004C000..0xC0052000`: `0xC004D97C` (`bne` zu `nop`), Literale bei `0xC004E3BC`/`0xC004FAF8` (Zahl der Plätze/Wellen) |
| Das Laden kopiert `esli[2:34]` in den Namenseintrag ohne Prüfung der Kategorie | offline + gemessen | memcpy bei `0xC004EE94`; alle Proben oben |
| Abgelehnt wird ein Eintrag nur, wenn die Wave-Nummer `esli[20:22]` <= 49 ist (Oszillator-Platz), belegt oder zu groß. Der Original-Lader bricht beim ersten abgelehnten Eintrag die **ganze Datei** ab | offline | `0xC004EE04` (`cmp r3,#0x31`), Abbruch `0xC00362A4` / `0xC0035B10` (Rückgabe 0x24), siehe `tools/patch/ht_osc.py` `SKIP_SITE` |
| `sample_errors.py` meldete genau diese Ablehnung als "slot_category" (`R_CATEGORY`), obwohl es die Wave-Nummer ist; seit dem 21.11. heißt sie `slot_wave` (`R_WAVE`) | offline | Recherche 2026-11-16 |
| Kategorie-Sprung am OSC-Rad (`0xC0040DD0`/`0xC0040E5C`) läuft im Kreis, bis eine andere Kategorie kommt; Oszillatoren 0 bis 17 haben immer andere Kategorien, also kein Hänger, auch wenn alle Samples gleich sind | offline | Schleife `0xC0040E0C..0xC0040E48`, Umlauf bei 0x3E5 |
| DELETE SAMPLE leert den Platz über dieselbe Funktion `0xC004DF90` (Kategorie 17). Ein gelöschtes Sample wird also wieder "Wave" | hergeleitet | `0xC004DF90` hat 3 Aufrufer (`0xC004E360` Start-Schleife, `0xC004F1A8`, `0xC004F5B4`); welcher DELETE ist, nicht im Emulator geprüft |

## Antworten auf die vier Fragen

1. **Wert:** 17. Rot zeigt "User", HT "Wave".
2. **Wo scheitert das Lesen ohne Wave-Sample?** Im Emulator nirgends: Laden, Export, Neuladen gehen mit 0 Wave-Samples auf HT und rot.
   Eine Schleife, ein Index -1 oder eine Division, die ein Wave-Sample braucht, gibt es im Ladeweg nicht.
   **Mögliche Erklärung (hergeleitet):** der Original-Lader bricht die ganze Datei beim ersten Eintrag ab, dessen
   **Wave-Nummer** (`esli[20:22]`) unter 50 liegt. BLECH meldet das als "slot_wave" (bis 21.11. "slot_category"). Ein Werkzeug, das beim Umstellen
   der Kategorie auch das Nachbarfeld ändert oder das Feld verwechselt, ergibt dann genau "Datei wird nicht gelesen".
   Am Gerät nicht geprüft; dafür bräuchte es die Datei, die nicht ging.
3. **Werks-Sample mit Kategorie User:** es gibt keine Zählung, also spielt es keine Rolle. DELETE SAMPLE setzt den Platz
   auf 17 zurück (hergeleitet), und jeder leere Platz ist im RAM 17.
4. **Fix in BLECH nötig?** Nein, für die Kategorie nicht. Die Sperre "mindestens ein Wave" kann wegfallen. Bleibt die Ursache
   offen, hilft am ehesten der schon vorhandene Haken `SKIP_SITE` (abgelehnter Eintrag überspringen statt Datei abbrechen),
   der in BLECH-Builds drin ist.

## Offen

- Der gemeldete Fall am Gerät: Datei in einem Sample-Werkzeug am Rechner geändert, lief auf Original-Hacktribe (ohne BLECH, also ohne `SKIP_SITE`).
  Die Datei gibt es nicht mehr. Der Verdacht mit dem Nachbarfeld `esli[20:22]` bleibt unbestätigt.
- DELETE SAMPLE im Emulator durchspielen (welcher der zwei Aufrufer von `0xC004DF90`).

## Proben

Im Scratchpad, nicht im Repo: `p07/wave_probe.py <dev> <VSB> <fall>` (Fälle `users_cat2`, `users_one17`, `allusers_cat0`,
`allusers_one17`), `p07/export_probe.py <dev> <VSB>`. Sie bauen die Datei mit `tools/emu/sampleset.py` (`ht_osc_cases.bank`)
und setzen `esli[18:20]` je Eintrag. Laufzeit je Fall etwa 1 bis 2 Minuten.
