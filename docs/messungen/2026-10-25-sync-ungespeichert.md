# Sync Group: gestoppt mit ungespeicherten Änderungen ohne Rückfrage (25.10.)

Wunsch vom Gerät, im Emulator gebaut und geprüft (Hacktribe, Korgs Original und blau). Am Gerät noch nicht geprüft.

Gestoppt und mit ungespeicherten Änderungen blätterte das Rad nur (VIEW:), MENU lud, EXIT blieb ([Idee 57](../ideen/57-ungespeichert-warnen.md)).
Das galt auch beim Wechsel innerhalb einer Sync Group, und ein schnelles Durchschalten durch die Patterns einer Gruppe blieb an dieser
Rückfrage hängen.

## Was jetzt gilt

- **Gestoppt, ungespeichert, das nächste Pattern hat die Sync Group des geladenen:** das Rad lädt es sofort, ohne VIEW: und ohne MENU.
  Die ungespeicherten Änderungen an Steps, Motion und den übrigen Werten, die eine Gruppe nicht mitnimmt, gehen dabei verloren, wie bei
  jedem Wechsel ohne Rückfrage; die Werte, die eine Gruppe mitnimmt, gehen ins neue Pattern ([Sync Groups](2026-10-19-sync-groups.md)).
  Ein Blättern, das schon offen war (VIEW:), endet auf einem Pattern der Gruppe ebenso mit dem Laden.
- **Ein anderes Pattern, das nicht in der Gruppe ist:** wie bisher VIEW:, MENU lädt, EXIT bleibt.
- **Ein Pattern, das durch den Abgleich einer Gruppe hereinkam, gilt nicht als ungespeichert wegen der mitgenommenen Werte.** Sie
  weichen vom Bank-Platz ab (Part-Mutes, Klang, Tempo und so weiter vom Pattern davor), das war bisher eine "Änderung". Ohne diesen Teil
  hielte das zweite Pattern einer Folge die Rückfrage vor jedem Schritt aus der Gruppe hinaus an. `pc_dirty` vergleicht die mitgenommenen
  Werte jetzt mit dem, was der Abgleich hineingeschrieben hat (`SG_BUF`), oder mit dem Bank-Platz (nach einem WRITE). Jede andere
  Abweichung und jede Änderung an einem mitgenommenen Wert nach dem Laden bleibt eine ungespeicherte Änderung.

## Wo es steht

`tools/patch/pattern_switch.py`:

- `wh_group_load`: das Rad gestoppt auf ein Pattern der Gruppe (`pc_grouped`): Blättern beenden, den Selektor der Firmware mit dem
  Schritt zur Zielnummer aufrufen.
- `S_SGNUM` (Zustand `+0x38`): der Bank-Platz, den ein Abgleich ins RAM-Pattern gebracht hat, sonst "keiner". Setzt `copy_hook`.
- `pd_synced` in `pc_dirty`: die Byte-Schleife über das Pattern in Adressreihenfolge, die mitgenommenen Werte (`sg_head_at`, Bytes 1 bis
  `0x2F` je Part) gegen `SG_BUF`, alles andere gegen den Bank-Platz, `0x3C`, `0x3E`, `0x3F` ausgenommen wie bisher.
- `SG_BUF` liegt jetzt bei `0xC0173000` (frei zwischen dem Code und der Tabelle des SysEx-Patches, beide Builds), weil der Code mit
  `pd_synced` den alten Platz hinter sich füllt. `CODE_END` ist `0xC0180F00`.

`tools/emu/pswitch_cases.py`, `case_sync_unsaved`:

| Fall | Erwartung |
|---|---|
| `group_unsaved_loads_at_once` | Pattern 1 bearbeitet, ein Klick auf Pattern 2 (gleiche Gruppe): geladen, kein Blättern |
| `group_unsaved_run_through` | zwei Klicks weiter auf Pattern 4 (Gruppe): geladen, trotz abweichender mitgenommener Werte |
| `group_carry_is_not_unsaved` | danach ein Klick in ein Pattern ohne Gruppe: lädt sofort, keine Rückfrage |
| `group_edit_after_carry_browses` | nach dem Abgleich ein Step geändert: der Klick aus der Gruppe blättert |
| `group_carried_edit_browses` | nach dem Abgleich ein mitgenommener Wert (Part-Mute) geändert: der Klick aus der Gruppe blättert |
| `group_ends_an_open_browse` | offenes Blättern, dann ein Klick auf ein Pattern der Gruppe: lädt |
| `other_group_unsaved_browses` | andere Gruppe: Blättern wie bisher |
| `group_unsaved_kill_switch_is_stock` | EXIT beim Einschalten: die Firmware allein |

Grenze: ein Pattern, das durch den Abgleich kam und dessen mitgenommener Wert später von Hand auf genau den Wert des Bank-Platzes
zurückgestellt wird, gilt als gespeichert (es gleicht dem Bank-Platz).
