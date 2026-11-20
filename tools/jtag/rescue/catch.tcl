proc rv {n} { regexp {0x[0-9a-fA-F]+} [reg $n] v; return $v }
proc go {} {
  init
  halt 300
  set pc [rv pc]
  echo "HALT_PC $pc"
  if {$pc >= 0xc0000000 && $pc < 0xd0000000} { echo "RESULT TOO_LATE"; return }
  bp 0xc0000000 4 hw
  resume
  if {[catch {wait_halt 30000}]} { halt 1000; echo "RESULT NO_BP pc=[rv pc]"; return }
  rbp 0xc0000000
  set pc [rv pc]
  echo "AT $pc cpsr=[rv cpsr] c1=[format 0x%x [arm mrc 15 0 1 0 0]] ttb=[format 0x%x [arm mrc 15 0 2 0 0]]"
  if {$pc != 0xc0000000} { echo "RESULT WRONG_BP"; return }
  load_image $::env(IMAGE) 0xc0000000 bin
  echo "FIRST [mdw 0xc0000000 2]"
  reg pc 0xc0000000
  resume
  echo "RESULT STARTED"
}
if {[catch {go} e]} { echo "RESULT ERR $e" }
