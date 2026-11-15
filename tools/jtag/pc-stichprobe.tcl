# Nur lesen: 12x anhalten, PC/LR lesen, weiter.
proc go {} {
  init
  for {set i 0} {$i < 12} {incr i} {
    halt 1000
    echo "S$i PC [lindex [reg pc] 2] LR [lindex [reg lr] 2] CPSR [lindex [reg cpsr] 2]"
    resume
    sleep 211
  }
  echo "RESULT OK"
}
if {[catch {go} e]} { echo "RESULT ERR $e" }
shutdown
