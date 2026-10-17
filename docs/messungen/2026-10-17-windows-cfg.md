# Windows: der Emulator stirbt beim ersten Firmware-Befehl

Stand 2026-10-17. Gemessen per SSH auf einem Windows-PC, auf dem die App 1.0.0 den Fehler
"Der Emulator auf Port N antwortet nicht" zeigte: Intel Core i7-7700K, Windows 10 Home
22H2 (Build 19045). Firmware: eine eigene `SYSTEM.VSB` mit BLECH auf Hacktribe.
Markierungen: **gemessen**, **hergeleitet**.

- **Gemessen:** Der Dienst startet und antwortet. Beim Start der Firmware verschwindet der
  Prozess ohne Python-Fehler und ohne faulthandler-Spur, im ersten `emu_start`, noch vor dem
  ersten MMIO-Zugriff.
- **Gemessen:** Ein Testprogramm, das mit PyInstaller gepackt ist und 100 NOPs ausführt, stirbt
  mit Unicorn 2.1.4 genauso. Mit 2.1.3 und 2.1.0 läuft es durch.
- **Gemessen:** Ungepackt mit Python 3.10 und Unicorn 2.1.4 bootet derselbe PC die Firmware
  5 s lang ohne Fehler. Die Stack-Größe des Threads (64 KiB bis 4 MiB) ändert daran nichts.
- **Gemessen:** Der Bootloader von PyInstaller ist mit Control Flow Guard gebaut
  (`GUARD_CF` in den DllCharacteristics), `python.exe` nicht. Mit dem gelöschten Bit läuft
  dieselbe gepackte exe mit Unicorn 2.1.4 durch, auch mit CPU-Modell, Exits und MMIO.
- **Hergeleitet:** Unicorn führt die Firmware als Code aus, den es zur Laufzeit erzeugt. Mit
  CFG beendet Windows 10 den Prozess beim Sprung in diesen Code. Auf GitHubs
  Windows-Runnern trat das nicht auf.
- **Behebung:** `tools/emu/build-sidecar.mjs` löscht das Bit im Windows-Sidecar
  (`tools/emu/pe-flags.mjs`, Test `test/pe-flags.test.mjs`).
