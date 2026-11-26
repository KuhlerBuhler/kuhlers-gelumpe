.equ NR_MAGIC, 0x3152434E
.equ NR_SIZE, 72
.equ NR_FAULT_END, 152             ; NR_FAULTS to NR_STOP_ACK (recording_runtime.py), zeroed with the context
.equ NR_RING_BYTES, 2097152
.equ NR_DISABLED, 32
.equ NR_OOM, 33
.equ NR_NO_CARD, 34
; A byte right behind NR_SETTING (script_menu.s), inside the 76 bytes of NATIVE_RECORDING (script_hooks.py): a take started by PLAY
; in the setup (recording_ui.s) waits for the transport to run (1), then runs with it (2); STOP ends it (nr_transport_frame).
; Any other value, FF at power-on included, binds nothing.
.equ NR_PLAY_BOUND, 73
.equ NR_PLAY_WAIT, 1
.equ NR_PLAY_RUN, 2
; The byte after it: 3 a PLAY the Sampler's setup took waits for the setup to close (recording_ui.s), 2 and 1 how many of its
; packets (press, release), sent through the panel queue, still go past nr_input untouched. Other values, FF at power-on
; included, mean none.
.equ NR_PLAY_INJECT, 74
.equ NR_PLAY_PENDING, 3

; Public state contains no pointers that the input or frame task dereferences.
nr_init:
    .word 0xE10F3000                 ; mrs r3, cpsr
    orr r1, r3, #0xC0
    .word 0xE121F001                 ; msr cpsr_c, r1
    ldr r2, =NATIVE_RECORDING
    ldr r0, [r2]
    ldr r1, =NR_MAGIC
    cmp r0, r1
    beq nr_init_done
    mov r0, #0
    mov r1, #NR_SIZE-4
nr_init_zero:
    str r0, [r2, r1]
    subs r1, r1, #4
    bne nr_init_zero
    mov r1, #NR_FAULTS
nr_init_faults:
    str r0, [r2, r1]
    add r1, r1, #4
    cmp r1, #NR_FAULT_END
    blo nr_init_faults
    ldr r0, =NR_MAGIC
    str r0, [r2]
nr_init_done:
    mov r0, r2
    .word 0xE121F003                 ; msr cpsr_c, r3
    bx lr
.pool

; UiTask acknowledges only at a frame boundary, after its preceding card calls returned.
nr_ui_ack:
    push {lr}
    bl nr_init
    mov r1, #1
    str r1, [r0, #NR_UI_READY]
    pop {pc}

nr_enabled:
    ldr r1, =MENU_STATE
    ldr r0, [r1, #M_ON]
    cmp r0, #1
    movne r0, #0
    bxne lr
    ldr r1, =NATIVE_RECORDING        ; NATIVE RECORDING (script_menu.s:NR_SETTING), only 1 is ON (FF at power-on)
    ldrb r0, [r1, #NR_SETTING]
    cmp r0, #1
    movne r0, #0
    bx lr

nr_busy:
    push {r4, lr}
    bl nr_init
    ldr r1, [r0, #NR_PHASE]
    ldr r2, [r0, #NR_REQUEST]
    cmp r2, #1
    orreq r1, r1, #1
    cmp r1, #0
    movne r0, #1
    moveq r0, #0
    pop {r4, pc}

; r0 = 1 start, 0 stop. Only memory operations run under the interrupt mask.
nr_post:
    push {r4-r6, lr}
    mov r4, r0
    cmp r4, #1
    movhi r0, #RW_BAD_ARG
    bhi nr_post_return
    bl nr_init
    mov r5, r0
    cmp r4, #0
    beq nr_post_lock
    bl nr_enabled
    cmp r0, #0
    moveq r0, #NR_DISABLED
    beq nr_post_return
    ; Without a card a start would only fail in the writer; refuse it here and say why.
    ldr r0, =REC_SD_INPUT
    ldr r0, [r0]
    tst r0, #REC_SD_DETECT
    movne r0, #NR_NO_CARD
    strne r0, [r5, #NR_ERROR]
    bne nr_post_return
nr_post_lock:
    .word 0xE10F6000                 ; mrs r6, cpsr
    orr r1, r6, #0xC0
    .word 0xE121F001                 ; msr cpsr_c, r1
    bl nr_busy
    cmp r4, #0
    beq nr_post_stop
    cmp r0, #0
    movne r0, #RW_BAD_STATE
    bne nr_post_unlock
    str r0, [r5, #NR_UI_READY]
    mov r0, #1
    str r0, [r5, #NR_REQUEST]
    mov r0, #0
    b nr_post_unlock
nr_post_stop:
    cmp r0, #0
    movne r0, #2
    strne r0, [r5, #NR_REQUEST]
    mov r0, #0
nr_post_unlock:
    .word 0xE121F006                 ; msr cpsr_c, r6
nr_post_return:
    pop {r4-r6, pc}
.pool

; r0 = the request claimed by CommandTask.
nr_take_request:
    .word 0xE10F2000                 ; mrs r2, cpsr
    orr r1, r2, #0xC0
    .word 0xE121F001                 ; msr cpsr_c, r1
    ldr r3, =NATIVE_RECORDING
    ldr r0, [r3, #NR_REQUEST]
    mov r1, #0
    str r1, [r3, #NR_REQUEST]
    .word 0xE121F002                 ; msr cpsr_c, r2
    bx lr

; CommandTask owns the allocation from the start claim through both close retries.
nr_service:
    push {r4-r8, lr}
    bl nr_init
    mov r4, r0
    bl nr_enabled
    cmp r0, #0
    bne nr_service_context
    mov r0, #0
    bl nr_post
    mov r0, #0
    str r0, [r4, #NR_SELECTED]
nr_service_context:
    ldr r5, [r4, #NR_CONTEXT]
    cmp r5, #0
    bne nr_service_command
    .word 0xE10F8000                 ; mrs r8, cpsr
    orr r1, r8, #0xC0
    .word 0xE121F001                 ; msr cpsr_c, r1
    ldr r0, [r4, #NR_REQUEST]
nr_service_claim_loaded:
    cmp r0, #1
    bne nr_service_claim
    ldr r1, [r4, #NR_UI_READY]
    cmp r1, #1
    beq nr_service_claim
    .word 0xE121F008                 ; msr cpsr_c, r8
    mov r0, #0
    b nr_service_return
nr_service_claim:
    cmp r0, #1
    mov r0, #0
    str r0, [r4, #NR_REQUEST]
    moveq r1, #3
    streq r1, [r4, #NR_PHASE]
    .word 0xE121F008                 ; msr cpsr_c, r8
    bne nr_service_return
    str r0, [r4, #NR_ERROR]
    str r0, [r4, #NR_BYTES]
    str r0, [r4, #NR_DROPPED]
    str r0, [r4, #NR_GAPS]
    str r0, [r4, #NR_ELAPSED]
    str r0, [r4, #NR_CAPACITY]
    mov r6, #NR_RING_BYTES
nr_service_allocate:
    add r0, r6, #RC_SIZE
    ldr r12, =MG_ALLOC
    blx r12
    cmp r0, #0
    bne nr_service_allocated
    cmp r6, #131072
    movls r0, #NR_OOM
    bls nr_service_start_error
    mov r6, r6, lsr #1
    b nr_service_allocate
nr_service_allocated:
    str r6, [r4, #NR_CAPACITY]
    mov r5, r0
    mov r1, #0
    mov r2, #RC_SIZE/4
nr_service_zero:
    str r1, [r0], #4
    subs r2, r2, #1
    bne nr_service_zero
    add r0, r5, #RC_SIZE
    str r0, [r5, #RC_RING]
    str r6, [r5, #RC_CAPACITY]
    mov r0, #RR_CHANNELS
    str r0, [r5, #RC_CHANNELS]
    ldr r0, [r4, #NR_NUMBER]
    str r0, [r5, #RW_NUMBER]
    ldr r0, =OS_TICKS
    ldr r0, [r0]
    str r0, [r4, #NR_START]
    str r5, [r4, #NR_CONTEXT]
    mov r0, r5
    mov r1, #1
    bl recorder_command
nr_service_command:
    bl nr_take_request
    cmp r0, #2
    bne nr_service_pump
    mov r0, r5
    mov r1, #0
    bl recorder_command
nr_service_pump:
    mov r0, r5
    bl recorder_pump
    str r0, [r4, #NR_ERROR]
    bl nr_fault_publish
    ldr r0, [r5, #RC_FILE_BYTES]
    str r0, [r4, #NR_BYTES]
    ldr r0, [r5, #RC_DROPPED]
    str r0, [r4, #NR_DROPPED]
    ldr r0, [r5, #RW_MARKER]
    cmp r0, #0
    movne r0, #1
    ldr r1, [r5, #RC_READER+RR_GAPS]
    add r0, r0, r1
    str r0, [r4, #NR_GAPS]
    ldr r0, [r5, #RW_NUMBER]
    str r0, [r4, #NR_NUMBER]
    ldr r0, =OS_TICKS
    ldr r0, [r0]
    ldr r1, [r4, #NR_START]
    sub r0, r0, r1
    str r0, [r4, #NR_ELAPSED]
    ldr r0, [r5, #RC_ACTIVE]
    cmp r0, #0
    moveq r0, #2
    str r0, [r4, #NR_PHASE]
    mov r0, r5
    bl recorder_busy
    cmp r0, #0
    bne nr_service_return
    bl nr_drop_empty
    mov r0, r5
    ldr r12, =MG_FREE
    blx r12
    b nr_service_clear
nr_service_start_error:
    str r0, [r4, #NR_ERROR]
nr_service_clear:
    .word 0xE10F8000                 ; mrs r8, cpsr
    orr r1, r8, #0xC0
    .word 0xE121F001                 ; msr cpsr_c, r1
    mov r0, #0
    str r0, [r4, #NR_PHASE]
    str r0, [r4, #NR_REQUEST]
    str r0, [r4, #NR_CONTEXT]
    .word 0xE121F008                 ; msr cpsr_c, r8
nr_service_return:
    ldr r0, [r4, #NR_ERROR]
    pop {r4-r8, pc}
.pool

; r4 public state, r5 recorder context of a finished take. A failed take without one sample leaves no WAV with only its
; header: the file is deleted and its number given back, so the next take is named as this one was. Builds without
; f_unlink (FS_UNLINK 0, the synth) keep the file and the count.
nr_drop_empty:
    push {r4, lr}
    ldr r0, =FS_UNLINK
    cmp r0, #0
    ldrne r0, [r4, #NR_ERROR]
    cmpne r0, #0
    beq nr_drop_return
    ldr r0, [r5, #RW_DATA_BYTES]
    ldr r1, [r5, #RW_STATE]
    orr r0, r0, r1
    ldr r1, [r5, #RW_FS_ERROR]       ; a failed open or close: the name may not be this take's file
    orrs r0, r0, r1
    bne nr_drop_return
    ldr r0, [r5, #RW_NUMBER]
    ldr r1, [r4, #NR_NUMBER]
    cmp r0, #0
    cmpne r0, r1
    bne nr_drop_return
    ldrb r0, [r5, #RW_PATH]
    cmp r0, #0
    beq nr_drop_return
    add r0, r5, #RW_PATH
    ldr r12, =FS_UNLINK
    blx r12
    cmp r0, #0
    bne nr_drop_return
    ldr r0, [r4, #NR_NUMBER]
    sub r0, r0, #1
    str r0, [r4, #NR_NUMBER]
nr_drop_return:
    pop {r4, pc}
.pool

; r4 public state, r5 recorder context. Publishes the reader's first fault of this take once, plain READ can fetch it.
nr_fault_publish:
    push {r4, lr}
    add r1, r5, #RC_READER
    ldr r0, [r1, #RR_ACK]
    str r0, [r4, #NR_ACK]
    ldr r0, [r1, #RR_STOP_ACK]
    str r0, [r4, #NR_STOP_ACK]
    ldr r0, [r1, #RR_FAULT]
    cmp r0, #0
    beq nr_fault_return
    tst r0, #RR_FAULT_SEEN
    bne nr_fault_return
    orr r0, r0, #RR_FAULT_SEEN
    str r0, [r1, #RR_FAULT]
    ldr r0, [r4, #NR_FAULTS]
    add r0, r0, #1
    str r0, [r4, #NR_FAULTS]
    add r0, r4, #NR_LAST
    bl nr_fault_copy
    ldr r0, [r4, #NR_FIRST]
    cmp r0, #0
    addeq r0, r4, #NR_FIRST
    bleq nr_fault_copy
nr_fault_return:
    pop {r4, pc}

; r0 destination, r1 reader context; keeps r1 and r4.
nr_fault_copy:
    ldr r2, [r1, #RR_FAULT]
    bic r2, r2, #RR_FAULT_SEEN
    str r2, [r0], #4
    add r12, r1, #RR_FAULT+4
    mov r3, #5
nr_fault_copy_word:
    ldr r2, [r12], #4
    str r2, [r0], #4
    subs r3, r3, #1
    bne nr_fault_copy_word
    ldr r12, =OS_TICKS
    ldr r12, [r12]
    ldr r2, [r4, #NR_START]
    sub r2, r12, r2
    str r2, [r0], #4
    str r12, [r0]
    bx lr
.pool

; UiTask frame (every ~40 ms, priority above CommandTask and the card task): reads the DSP ring while CommandTask waits on a
; card write. NR_PHASE is 1 only while the context is live (CommandTask publishes 2 before it frees it), and nothing here
; blocks before recorder_poll claims the reader, so the lower CommandTask cannot free the context in between.
nr_reader_frame:
    @ least-code: two nops only move the UI frame timing so the emulator's
    @ loadbar no-card case does not catch the main screen half drawn (red).
    @ Interim; replace once the test tolerates a split screen redraw.
    mov r0, r0
    mov r0, r0
    ldr r1, =NATIVE_RECORDING
    ldr r0, [r1, #NR_PHASE]
    cmp r0, #1
    bxne lr
    ldr r0, [r1, #NR_CONTEXT]
    b recorder_poll
.pool

nr_runtime_end:
