# DSP-Simulator: Tempo, Poll-Vorlauf und Plattformen

Fortsetzung von [Modellzeit](2026-11-14-blackfin-modellzeit.md).
Alles lief im Simulator. Kein Gerät wurde angesprochen.

## Gemessen

Messlauf: 0,3 s Modellzeit ab Reset mit `clock-blech-hacktribe.VSB`,
DSP mit 516,096 MHz, Host-Port über FIFO, SPORT-Eingang Stille.

| Rechner | Poll-Vorlauf an | aus |
|---|---:|---:|
| Mac M5, Last um 44 (andere Jobs) | 7,3 s | 16,3 s |
| Linux x86, i7-10510U, Regler `powersave`, Last um 1 | 14,9 s | 25,3 s |

Alle vier Läufe enden im selben Zustand: 55078105 ARM-Befehle, 123533003
DSP-Zyklen, Modellzeit 300000001 ns, gleicher Registerstand. Der Vorlauf
überspringt 1374304 der rund 1,38 Mio. Lesezugriffe auf `DSP_CTRL`.

Die Zeit liegt danach fast ganz im DSP-Simulator selbst, etwa 5,8 der 7,3 s.
Die ARM-Seite braucht rund 5 %.

## Wie der Poll-Vorlauf arbeitet

Die Firmware wartet in der Funktion `0xC001462C` auf den DSP. Sie liest
`DSP_CTRL` zweimal je Durchlauf und schreibt dabei auf den Stack.

1. Liest der ARM an derselben Stelle denselben Status wie kurz zuvor, rechnet
   ein zweites Unicorn einen Durchlauf aus einer Kopie des Zustands nach.
   Andere Geräteregister, Interrupts, Firmware-Einsprünge oder fremde Hooks
   in der Schleife brechen das ab.
2. Der Durchlauf zählt nur, wenn danach Register, Flags und jede geschriebene
   Stelle dem Ausgangszustand gleichen.
3. Der Worker rechnet dann die DSP-Schritte bis zu jedem künftigen Lesezugriff
   am Stück (Auftrag 20) und hält an, sobald sich der Status oder das
   Bereit-Wort ändert.
4. Ganze Durchläufe werden übersprungen. Lesezugriffe nach dem letzten ganzen
   Durchlauf spielt die Maschine einzeln mit Zeit- und Adressprüfung nach.

Mit `POLL_READS = 0` ist der Vorlauf aus.

## Gleiche Läufe, gleiches Ergebnis

Gemessen im Sample-Swap-Fall (`blackfin_swap_cases.py`, Hacktribe-Kandidat):
Mit dem alten Worker gingen gleiche Läufe ab etwa 390 ms Modellzeit
auseinander, je nach Lauf mit oder ohne Fehler bei Sample 501. Die
Anfragen an den Worker waren dabei bis zur ersten Abweichung bytegleich.

Ursache: Der UART im GNU-Simulator liest die Standardeingabe des Workers
(`dv-bfin_uart.c`). Dort kamen die Anfragen an, im Shared-Memory-Modus die
Klingel-Bytes. Ob der DSP beim Lesen des UART-Status ein Byte sah, hing also
von der Wanduhr ab. Der Worker liest seine Anfragen jetzt von einer Kopie
des Deskriptors, fd 0 zeigt auf `/dev/null`.

Danach gemessen: sechs parallele Läufe bis 450 ms bytegleich, ein
aufgezeichneter Anfragestrom ergibt beim Abspielen exakt die aufgezeichneten
Antworten. Der volle Fall besteht mit Poll-Vorlauf an und aus, beide Läufe
sind über alle 55493 Scheiben gleich.

Gegen den Stand vor dem Tick-Budget gibt es eine Abweichung bei 417,5 ms:
Dort führte Unicorns eigenes `count` 24 statt der verlangten 23 Befehle aus,
das Budget in `arm_tick.c` hält genau 23 ein. Die Ursache in Unicorn ist nicht
geklärt, ein kleiner Nachbau zeigte den Überlauf nicht.

## Plattformen

Gemessen: Linux x86 baut und läuft ohne Änderung (gcc, zlib, `make
MAKEINFO=true`; libzstd ist nicht nötig).

Hergeleitet: Der Worker braucht `fork` für den Boot-Snapshot, `mmap` für den
gemeinsamen Speicher und `poll` auf Pipes. Unter Windows gibt es das nativ
nicht. Entscheidung (16.11.): Windows läuft über WSL2. Später soll die
DSP-Simulation in der App für alle laufen. Fehlt dann der Worker, bleibt nur
der DSP-Teil aus, der übrige Emulator läuft weiter.
