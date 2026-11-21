# Nur lesen: verbinden, anhalten, Zustand lesen, weiterlaufen. Schreibt nichts.
proc go {} {
  init
  echo "TARGETS [target names]"
  halt 1000
  echo "PC [reg pc]"
  echo "CPSR [reg cpsr]"
  echo [format "CP15_C1 0x%08x" [arm mrc 15 0 1 0 0]]
  echo "SBL-Tabelle [mdw 0x8001c000 1]"
  echo "DDR0 [mdw 0xc0000000 4]"
  echo "USR-Stempel-RAM? [mdw 0xc0000020 2]"
  resume
  echo "RESULT OK"
}
if {[catch {go} e]} { echo "RESULT ERR $e" }
shutdown
