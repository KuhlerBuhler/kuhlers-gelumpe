# electribe 2 (AM1802): stop the CPU at the right place during power-on.
# Writes NOTHING - no flash, no RAM. Way back at any time: power off/on.
#
# What it does
#   1. polls the JTAG chain until the CPU can be halted (start this first, then switch the device on),
#   2. accepts the halt only while the PC is inside the factory boot loader (on-chip RAM 0x8000xxxx);
#      if the firmware area 0xC....... is already running it asks for another power cycle,
#   3. sets a hardware breakpoint on the firmware entry 0xC0000000, resumes and waits,
#   4. leaves the CPU HALTED at 0xC0000000 and keeps OpenOCD running (telnet 4444, gdb 3333).
#
# Status
#   Steps 3 and 4 are what we did by hand over telnet in our two debricks in September 2026
#   (CH347 adapter, a valid firmware was in flash).
#   The polling loop (steps 1 and 2) is from 2026-11-07. On our device it did NOT catch the boot
#   loader reliably (mostly "too late"). If that happens: use halt-now.tcl with the manual timing
#   trick (start OpenOCD in the moment you press power).
#   Not known: whether the factory boot loader still reaches 0xC0000000 when the SYSTEM region in
#   flash is empty. If the breakpoint never hits you get RESULT NO_BP with the place the CPU is at.

set ENTRY      0xc0000000   ;# firmware entry (the boot loader copies SYSTEM from flash to here and jumps)
set SBL_LO     0x80000000   ;# factory boot loader runs in on-chip RAM
set SBL_HI     0x80020000
set POLL_S     500          ;# give up polling after this many seconds
set BP_WAIT_MS 20000        ;# how long to wait for the breakpoint
set ARMED      0            ;# 0: first wait until the device was seen OFF once (normal case)
                            ;# 1: accept the first halt (when OpenOCD is restarted in a loop around the power cycle)
set TARGET     omapl138.arm

set last_err ""

proc try_halt {} {
    global last_err TARGET
    if {[catch {jtag arp_init} e]} { set last_err "arp_init: $e"; return 0 }
    if {[catch {jtag tapisenabled $TARGET} en] || !$en} { set last_err "arm tap not enabled"; return 0 }
    if {[catch {$TARGET arp_examine} e]} { set last_err "examine: $e"; return 0 }
    if {[catch {halt 300} e]} { set last_err "halt: $e"; return 0 }
    return 1
}

proc reg_val {name} {
    if {![regexp {0x[0-9a-fA-F]+} [reg $name] v]} { error "cannot read register $name" }
    return $v
}

proc catch_entry {} {
    global ENTRY SBL_LO SBL_HI POLL_S BP_WAIT_MS ARMED last_err
    catch {init}
    set t0 [clock seconds]
    set phase "wait"
    set seen_off $ARMED
    set n 0
    while {1} {
        if {[clock seconds] - $t0 > $POLL_S} {
            echo "RESULT TIMEOUT phase=$phase tries=$n last=$last_err"
            return 0
        }
        incr n
        if {![try_halt]} {
            if {!$seen_off} { echo "INFO device is off (or not reachable) - switch it ON now" }
            set seen_off 1
            continue
        }
        if {!$seen_off} {
            catch {resume}
            if {$phase ne "on"} { echo "INFO device is running - switch it OFF, then ON again" }
            set phase "on"
            sleep 200
            continue
        }
        set pcv [reg_val pc]
        if {$pcv >= 0xc0000000 && $pcv < 0xd0000000} {
            if {$phase ne "late"} { echo "INFO too late, firmware area already running (pc=$pcv) - power off and on again" }
            set phase "late"
            catch {resume}
            continue
        }
        if {$pcv < $SBL_LO || $pcv >= $SBL_HI} {
            if {$phase ne "rom"} { echo "INFO still in the boot ROM / vectors (pc=$pcv) - going on until the boot loader runs" }
            set phase "rom"
            catch {resume}
            continue
        }
        echo "HALT_PC $pcv after $n tries (inside the factory boot loader)"
        break
    }

    bp $ENTRY 4 hw
    resume
    if {[catch {wait_halt $BP_WAIT_MS} e]} {
        catch {halt 1000}
        catch {rbp $ENTRY}
        set pc2 "?"
        set cp2 "?"
        catch {set pc2 [reg_val pc]}
        catch {set cp2 [reg_val cpsr]}
        echo "RESULT NO_BP breakpoint at $ENTRY not reached within $BP_WAIT_MS ms; CPU halted at pc=$pc2 cpsr=$cp2"
        echo "INFO the boot loader did not jump to the firmware entry (or took longer). CPU stays halted, OpenOCD stays open."
        return 0
    }
    set pc2 [reg_val pc]
    rbp $ENTRY
    if {$pc2 != $ENTRY} {
        echo "RESULT WRONG_BP halted at pc=$pc2 instead of $ENTRY; CPU stays halted"
        return 0
    }
    echo "RESULT AT_ENTRY pc=$pc2 cpsr=[reg_val cpsr]"
    echo "INFO CPU is halted at the firmware entry. OpenOCD stays open: telnet localhost 4444"
    echo "INFO next, by hand:  load_image <raw system image> $ENTRY bin   then   reg pc $ENTRY   then   resume"
    return 1
}

if {[catch {catch_entry} e]} { echo "RESULT ERR $e" }
