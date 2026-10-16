# SysEx: globaler Kanal und Leseobergrenze

Gemessen 2026-09-14.

**Kanal.** Die erweiterten Befehle von Hacktribe (`0x52` RAM lesen, `0x53`
und `0x54` RAM schreiben, `0x55` Flash lesen) und Korgs eigene Befehle
(`0x0E` Global-Dump) antworten nur, wenn der Kopf `42 3n 00 01 24` den
globalen Kanal des Geräts trägt. Das Gerät stand auf Kanal 9 (0-basiert). Auf
Kanal 0 kam auf keinen einzigen Befehl eine Antwort, auf Kanal 9 auf alle.
Der Kanal steht in Byte 4 der Antwort auf die Gerätesuche `F0 42 50 00 00 F7`.

**Antwort.** Die Nutzdaten einer Leseantwort beginnen ab Byte 9 und gehen bis
vor `F7`, 7-Bit-gepackt. In Byte 6 steht bei RAM- und Flash-Lesen `0x54`,
nicht die Befehlsnummer: gemessen "0x52 -> 84 bytes, func=0x54" und
"0x55 -> 84 bytes, func=0x54", der Global-Dump kam mit `0x51`. Was in Byte 7
und 8 steht, ist nicht festgehalten.

**Obergrenze.** Ein Flash-Lesen ab `0x1000000` bekommt keine Antwort, das
Display bleibt schwarz, das Gerät muss aus- und eingeschaltet werden. Danach
ist alles heil. Durchsatz beim Lesen über USB rund 200 KiB/s bei Blöcken von
`0x4000`.
