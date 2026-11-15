# electribe 2 (AM1802): halt the CPU right now and say where it is. Writes nothing.
# For the manual timing trick (a reset over JTAG does not work on this board):
# start OpenOCD with this script in the moment you press the power button.
#   pc 0x8000xxxx = factory boot loader in on-chip RAM   -> good, go on by hand (see below)
#   pc 0xC....... = already in the firmware area         -> too late: power off, try again
# The CPU stays halted and OpenOCD keeps running (telnet localhost 4444).
# This is how we did our two debricks in September 2026 (CH347 adapter).

proc reg_val {name} {
    if {![regexp {0x[0-9a-fA-F]+} [reg $name] v]} { error "cannot read register $name" }
    return $v
}

proc halt_now {} {
    init
    halt 1000
    set pcv [reg_val pc]
    echo "HALT_PC $pcv cpsr=[reg_val cpsr]"
    if {$pcv >= 0x80000000 && $pcv < 0x80020000} {
        echo "RESULT IN_BOOTLOADER good. Next by hand (telnet localhost 4444):  bp 0xc0000000 4 hw   then   resume"
    } elseif {$pcv >= 0xc0000000 && $pcv < 0xd0000000} {
        echo "RESULT TOO_LATE firmware area already running - power off and start a little earlier"
    } else {
        echo "RESULT ELSEWHERE boot ROM or exception vectors - type resume, then halt again a moment later"
    }
}

if {[catch {halt_now} e]} {
    echo "RESULT ERR $e (device off or chain not alive yet? start again)"
    shutdown
}
