# Blackfin: HOSTDP-Register und Interrupts

Fortsetzung: [SPORT0 und der native Audiotakt](2026-11-14-blackfin-sport0.md).

## Hergeleitet

Das
[BF52x-Hardwarehandbuch](https://www.analog.com/media/en/dsp-documentation/processor-manuals/ADSP-BF52x_hwr_rev1.2.pdf),
Seiten 8-26 bis 8-32, und die veröffentlichten
[Registerdefinitionen](https://raw.githubusercontent.com/torvalds/linux/v4.16/arch/blackfin/mach-bf527/include/mach/defBF522.h)
beschreiben drei HOSTDP-Register:

| Adresse | Register | Rücksetzwert |
|---|---|---|
| `0xFFC03400` | `HOST_CONTROL` | `0x0400` |
| `0xFFC03404` | `HOST_STATUS` | `0x000C` |
| `0xFFC03408` | `HOST_TIMEOUT` | `0` |

Die MMRs sind 16 Bit breit. Das Modell erlaubt zusätzlich nullerweiterte
32-Bit-Lesungen wie die übrigen GNU-MMR-Modelle; 32-Bit-Schreibzugriffe werden
abgewiesen. Das Timeoutfeld ist auf elf Bit begrenzt.

`HOST_STATUS` hat unterschiedliche Schreibregeln: `DMA_CMPLT` wird durch
eine geschriebene Eins gesetzt, `HSHK` ist beschreibbar, und `HIRQ`,
`HOSTDP_TOUT` sowie `HOSTRD_DONE` werden durch eine Eins quittiert.
Nur-Lese-Bits lassen sich dadurch nicht verändern. `BTE` folgt der
Timeoutfreigabe in `HOST_CONTROL`. Das Resetbit liest sich als null zurück;
ein Softreset setzt den Status zurück, erhält Steuerung und Timeout und
nimmt anstehende Interruptsignale zurück.

Der Konfigurationsstatus wird hier als atomarer, untätiger Zustand
nachgebildet. Einschalten erlaubt Konfiguration, HRDY-Override sperrt sie.
Eine zeitgenaue Rücksetzsequenz während eines laufenden Transfers ist damit
nicht geprüft.

## Gemessen mit erzeugten Programmen

Das zusätzliche GNU-Gerät besitzt echte MMR-Rückrufe. Es wird in die
BF52x-Gerätetabellen eingetragen und an die vorhandenen SIC-Eingänge
angeschlossen. Es ist keine gewöhnliche RAM-Region.

Acht erste Gegenproben schlagen vor dem Einbau fehl und bestehen danach.
Weitere Prüfungen kontrollieren Softreset bei anstehenden Interrupts,
Zugriffsbreiten und einen tatsächlich ausgeführten Interrupt-Handler.
Ein erzeugtes Blackfin-Programm empfängt einen HOSTDP-Interrupt über SIC und
CEC, schreibt einen Zähler, quittiert `HIRQ` durch einen nativen MMR-Zugriff
und kehrt mit `RTI` zurück. Es gibt keinen direkten Aufruf dieses Handlers.

Die Statuseingänge halten die SIC-Leitung aktiv, solange noch mindestens
eine ihrer Quellen ansteht. Das Quittieren nur einer Quelle nimmt die
andere nicht zurück. `HOSTRD_DONE` wird getrennt weitergeleitet und quittiert.
Die Ereignisse werden für diese Tests ausdrücklich eingespeist; sie sind
kein Nachweis eines vorherigen Datentransfers.

77 Modulprüfungen und neun Dokumentationsprüfungen bestehen. Der Unitlauf
besteht mit 1612 Prüfungen bei 166 ausgelassenen Prüfungen. Die erneute
vollständige Browserprüfung läuft beim Sichern dieses Zwischenstands noch.

Nicht unterstützte Ereignisse beenden die Sitzung mit Fehler. Für
HOSTDP-DMA-Datenzugriffe sind ausdrückliche Abbrüche hinterlegt, damit der
allgemeine GNU-Durchgriff zum übergeordneten Speicherbus keine erfolgreiche
Übertragung vortäuscht. FIFO-Datentransfers und automatische Timeoutabläufe
nach einem Buszugriff sind noch nicht implementiert.

## Gemessen beim originalen RTOS-Start

Die private rote Originalfirmware 2.02 durchläuft jetzt den vorher
fehlgeschlagenen Schreibzugriff bei `0x18F90` auf `HOST_STATUS`. Der Lauf
benutzt weiterhin die originale Reset- und RTOS-Sequenz sowie die beiden
[SysControl-Aufrufe](2026-11-14-blackfin-syscontrol.md).

Die nächste Grenze liegt bei der Einrichtung einer DMA-Gegenstelle:

```text
/core/bfin_dmac@0: Unable to locate peer for bfin_dma (pmap:0x3000 /core/bfin_sport@0)
```

SPORT0 ist im GNU-Gerätemodell nicht implementiert. Auch die entsprechende
Quelldatei fehlt; eine zusätzliche Adresszuordnung allein behebt das nicht.
Der Prozess beendet den Lauf mit Fehlerstatus 2, die Startdiagnose mit
Status 1. Es gibt keine Bereitschaftsantwort und keine bestandene
Initialisierung.

## Wiederholen

```sh
python3 tools/dsp/build_blackfin.py "$BFIN_SDK"
export BFIN_WORKER="$BFIN_SDK/blackfin-worker"
PYTHONPATH=tools/emu tools/emu/.venv/bin/python -m unittest test_blackfin_backend test_blackfin_stream test_blackfin_syscontrol test_blackfin_hostdp test_dsp_model test_bootcache
python3 tools/dsp/blackfin_probe.py --worker "$BFIN_WORKER" --vsb "$E2_STOCK_VSB"
```

Die Prozessschnittstelle trägt `BFIN4`. Ältere Hilfsprogramme werden
abgewiesen und müssen neu gebaut werden. SDK, Firmware und Rohprotokolle
bleiben außerhalb des Repositorys. Alle Tests bauen ihre Daten selbst.

## Offen

- SPORT0 mit Register- und FIFO-Modell, DMA-Anschluss und ausdrücklich
  konfiguriertem Prüftakt. Geplant sind 48 kHz mit der nativen Blockgröße,
  Nullen als Standard und ein zusätzlicher fester LCG-Eingang.
- Vollständiger RTOS-Start, endgültige Heap- und Task-Stackbelegung sowie
  die IFX-Gegenprobe mit vollständiger Schreibspur.
- HOSTDP-Datentransfers, natürliche Timeoutzustände und das Zusammenführen
  mit dem funktionalen ARM-Transport.
- Gerätevergleich für das Timing. Die bisherigen Tests liefern keinen Ton.

Es gab keinen Gerätezugriff und keine Änderung einer Firmwaredatei.
