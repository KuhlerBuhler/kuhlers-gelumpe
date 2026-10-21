script_runtime_init:
    push {r4-r7, lr}
    mov r4, r0
    mov r5, r1
    mov r0, #0
    str r0, [r4, #RT_ARMED]
    ldr r6, =SCRIPT_POOL_BYTES
    mov r0, r4
    cmp r2, r6
    movlo r6, r2
    ldr r2, =SCRIPT_RUNTIME_SIZE
    mov r1, #0
    bl mem_fill
    str r5, [r4, #RT_ARENA]
    str r6, [r4, #RT_SIZE]
    ldr r0, =LIM_FUEL
    str r0, [r4, #RT_FUEL]
    ldr r0, =SCRIPT_FRAME_TICKS
    str r0, [r4, #RT_MAXTICKS]
    mov r0, #SCRIPT_PHASE_IDLE
    str r0, [r4, #RT_CURSOR_PHASE]
    mov r0, #ERR_OK
    pop {r4-r7, pc}
.pool

; r0 address, r1 byte, r2 length.
mem_fill:
    cmp r2, #0
    bxeq lr
mf_loop:
    strb r1, [r0], #1
    subs r2, r2, #1
    bne mf_loop
    bx lr

; r0 address -> little endian halfword, no alignment requirement.
read_half:
    ldrb r1, [r0, #1]
    ldrb r0, [r0]
    orr r0, r0, r1, lsl #8
    bx lr

; r0 instruction address, r1 opcode -> r0 first operand, r1 second operand.
decode_operands:
    push {r4-r6, lr}
    mov r4, r0
    ldr r2, =script_op_operands
    add r2, r2, r1, lsl #1
    ldrb r3, [r2]
    ldrb r6, [r2, #1]
    mov r5, #0
    cmp r3, #ARG_NONE
    beq dec_second
    ldrb r5, [r4, #1]
    add r4, r4, #1
    cmp r3, #ARG_VAR
    blo dec_second
    cmp r3, #ARG_TARGET
    bhi dec_second
    ldrb r3, [r4, #1]
    orr r5, r5, r3, lsl #8
    add r4, r4, #1
dec_second:
    mov r1, #0
    cmp r6, #ARG_NONE
    beq dec_done
    ldrb r1, [r4, #1]
    cmp r6, #ARG_VAR
    blo dec_done
    cmp r6, #ARG_TARGET
    bhi dec_done
    ldrb r3, [r4, #2]
    orr r1, r1, r3, lsl #8
dec_done:
    mov r0, r5
    pop {r4-r6, pc}
.pool

; r4 runtime, r6 GSCR block. Only section pointers are changed.
set_sections:
    push {r5, lr}
    str r6, [r4, #RT_BLOB]
    add r5, r6, #HDR_SIZE
    add r0, r6, #HDR_HANDLER_COUNT
    bl read_half
    add r5, r5, r0, lsl #2
    str r5, [r4, #RT_CONSTANTS]
    add r0, r6, #HDR_CONST_COUNT
    bl read_half
    add r5, r5, r0, lsl #2
    str r5, [r4, #RT_STRINGS]
    add r0, r6, #HDR_STRING_COUNT
    bl read_half
    add r5, r5, r0, lsl #5
    str r5, [r4, #RT_CODE]
    add r0, r6, #HDR_CODE_SIZE
    bl read_half
    str r0, [r4, #RT_CODESIZE]
    add r0, r0, #3
    bic r0, r0, #3
    add r5, r5, r0
    str r5, [r4, #RT_LINES]
    add r0, r6, #HDR_LINE_COUNT
    bl read_half
    str r0, [r4, #RT_LINECOUNT]
    ldr r0, [r6, #HDR_VAR_COUNT]
    str r0, [r4, #RT_VARS]
    pop {r5, pc}

; r0 runtime, r1 available GSCR bytes, r2 available length -> error, entry pointer. The block is copied into the pool.
script_load_block:
    mov r3, #0
; r3 = 1: the block stays where it is, outside the pool (the one that is built into BLECH): only its entry and its
; variables take room in the pool, and the entry's blob pointer is the address it was given. Everything else is the same.
script_load_block_ex:
    push {r4-r11, lr}
    sub sp, sp, #4
    str r3, [sp]
    mov r4, r0
    mov r6, r1
    mov r7, r2
    mvn r8, #0
    str r8, [r4, #RT_OFFSET]
    cmp r7, #8
    blo l_truncated
    ldr r0, [r6, #HDR_MAGIC]
    ldr r1, =SCRIPT_MAGIC
    cmp r0, r1
    bne l_magic
    add r0, r6, #HDR_FORMAT_VERSION
    bl read_half
    cmp r0, #SCRIPT_FORMAT_VERSION
    bne l_format_version
    cmp r7, #HDR_SIZE
    blo l_truncated
    add r0, r6, #HDR_API_VERSION
    bl read_half
    cmp r0, #1
    blo l_api_version
    ldr r1, =SCRIPT_API_VERSION
    cmp r0, r1
    bhi l_api_version
    ldr r0, [r6, #HDR_VAR_COUNT]
    ldr r1, =LIM_VARS
    cmp r0, r1
    bhi l_limits
    add r0, r6, #HDR_CODE_SIZE
    bl read_half
    ldr r1, =LIM_CODE
    cmp r0, r1
    bhi l_limits
    add r0, r6, #HDR_STACK_MAX
    bl read_half
    cmp r0, #LIM_STACK
    bhi l_limits
    add r0, r6, #HDR_CONST_COUNT
    bl read_half
    cmp r0, #LIM_CONSTS
    bhi l_limits
    add r0, r6, #HDR_STRING_COUNT
    bl read_half
    cmp r0, #LIM_STRINGS
    bhi l_limits
    add r0, r6, #HDR_HANDLER_COUNT
    bl read_half
    cmp r0, #SCRIPT_EVENT_COUNT
    bhi l_limits
    add r0, r6, #HDR_LINE_COUNT
    bl read_half
    ldr r1, =LIM_CODE
    cmp r0, r1
    bhi l_limits
    add r0, r6, #HDR_FLAGS
    bl read_half
    bic r0, r0, #BLOCK_KNOWN_FLAGS
    cmp r0, #0
    bne l_bad_size
    bl set_sections
    ldr r0, [r4, #RT_LINES]
    ldr r1, [r4, #RT_LINECOUNT]
    add r0, r0, r1, lsl #2
    sub r10, r0, r6
    ldr r9, [r6, #HDR_TOTAL_SIZE]
    add r0, r6, #HDR_FLAGS
    bl read_half
    tst r0, #BLOCK_FLAG_DATA
    beq size_plain
    cmp r10, r9                 ; a data section follows the lines up to totalSize
    bhs l_bad_size
    b size_known
size_plain:
    cmp r10, r9
    bne l_bad_size
size_known:
    cmp r7, r9
    blo l_truncated
    add r0, r6, #HDR_CHECKSUM+4
    add r1, r6, r9
    mvn r2, #0
    ldr r5, =0xEDB88320
crc_byte:
    cmp r0, r1
    bhs crc_done
    ldrb r3, [r0], #1
    eor r2, r2, r3
    mov r3, #8
crc_bit:
    movs r2, r2, lsr #1
    eorcs r2, r2, r5
    subs r3, r3, #1
    bne crc_bit
    b crc_byte
crc_done:
    mvn r2, r2
    ldr r0, [r6, #HDR_CHECKSUM]
    cmp r0, r2
    bne l_checksum
    mov r0, r6
    mov r1, #0
    mov r2, r10
    mov r3, r9
    bl data_walk
    cmp r0, #1
    beq l_bad_size
    cmp r0, #2
    beq l_bad_var
    ldr r5, [r4, #RT_STRINGS]
    ldr r7, [r4, #RT_CODE]
text_slot:
    cmp r5, r7
    bhs text_done
    mov r1, #0
    mov r2, #0
text_char:
    ldrb r0, [r5, r1]
    cmp r0, #0
    moveq r2, #1
    cmp r2, #0
    bne text_tail
    cmp r0, #32
    blo l_bad_string
    cmp r0, #126
    bhi l_bad_string
    b text_next
text_tail:
    cmp r0, #0
    bne l_bad_string
text_next:
    add r1, r1, #1
    cmp r1, #SEC_STRING
    blo text_char
    cmp r2, #0
    beq l_bad_string
    add r5, r5, #SEC_STRING
    b text_slot
text_done:
    bl verify_code
    cmp r0, #0
    bne load_return
    ldr r0, [r6, #HDR_VAR_COUNT]
    mov r0, r0, lsl #2
    ldr r1, [sp]
    cmp r1, #0
    addeq r0, r0, r9
    add r0, r0, #SCRIPT_ENTRY_SIZE
    ldr r1, [r4, #RT_USED]
    adds r2, r0, r1
    bcs l_pool_budget
    ldr r3, [r4, #RT_SIZE]
    cmp r2, r3
    bhi l_pool_budget
    ldr r5, [r4, #RT_ARENA]
    add r5, r5, r1
    mov r7, r2
    mov r0, r5
    mov r1, #0
    mov r2, #SCRIPT_ENTRY_SIZE
    bl mem_fill
    add r10, r5, #SCRIPT_ENTRY_SIZE
    mov r11, r10
    ldr r0, [sp]
    cmp r0, #0
    movne r11, r6
    movne r9, #0
    mov r0, #0
copy_blob:
    cmp r0, r9
    bhs copy_done
    ldrb r1, [r6, r0]
    strb r1, [r10, r0]
    add r0, r0, #1
    b copy_blob
copy_done:
    str r11, [r5, #SCRIPT_ENTRY_BLOB]
    add r0, r10, r9
    str r0, [r5, #SCRIPT_ENTRY_VARS]
    ldr r2, [r6, #HDR_VAR_COUNT]
    mov r2, r2, lsl #2
    mov r1, #0
    bl mem_fill
    ldr r0, [r4, #RT_LINES]
    ldr r1, [r4, #RT_LINECOUNT]
    add r2, r0, r1, lsl #2
    sub r2, r2, r6
    mov r0, r11
    ldr r1, [r5, #SCRIPT_ENTRY_VARS]
    ldr r3, [r6, #HDR_TOTAL_SIZE]
    bl data_walk
    mov r0, #SCRIPT_STATE_LOADED
    str r0, [r5, #SCRIPT_ENTRY_STATE]
    ldr r0, [r4, #RT_TAIL]
    cmp r0, #0
    strne r5, [r0, #SCRIPT_ENTRY_NEXT]
    streq r5, [r4, #RT_HEAD]
    str r5, [r4, #RT_TAIL]
    str r7, [r4, #RT_USED]
    mov r0, #ERR_OK
    mov r1, r5
    add sp, sp, #4
    pop {r4-r11, pc}
load_return:
    str r8, [r4, #RT_OFFSET]
    mov r1, #0
    add sp, sp, #4
    pop {r4-r11, pc}
.pool

; The data section (BLOCK_FLAG_DATA): r0 = the block, r1 = its variables (0: only check), r2 = where the section starts in
; the block, r3 = totalSize -> r0 = 0 fine, 1 a record runs past totalSize, 2 a record is empty or leaves the variables.
; With variables, every byte of a record goes into one slot, from slot `base` on. Clobbers r1 to r3 and r12.
data_walk:
    push {r4-r8, lr}
    ldr r8, [r0, #HDR_VAR_COUNT]
    add r4, r0, r2
    add r5, r0, r3
dw_next:
    cmp r4, r5
    movhs r0, #0
    bhs dw_done
    add r6, r4, #4
    cmp r6, r5
    bhi dw_size
    ldrb r6, [r4]
    ldrb r7, [r4, #1]
    orr r6, r6, r7, lsl #8
    ldrb r7, [r4, #2]
    ldrb r12, [r4, #3]
    orr r7, r7, r12, lsl #8
    cmp r7, #0
    beq dw_var
    add r12, r6, r7
    cmp r12, r8
    bhi dw_var
    add r4, r4, #4
    add r12, r7, #3
    bic r12, r12, #3
    add r12, r4, r12
    cmp r12, r5
    bhi dw_size
    cmp r1, #0
    beq dw_skip
    add r2, r1, r6, lsl #2
dw_copy:
    ldrb r3, [r4], #1
    str r3, [r2], #4
    subs r7, r7, #1
    bne dw_copy
dw_skip:
    mov r4, r12
    b dw_next
dw_size:
    mov r0, #1
    b dw_done
dw_var:
    mov r0, #2
dw_done:
    pop {r4-r8, pc}

verify_code:
    push {r5, r7, r9-r11, lr}
    ldr r0, =RT_BOUNDARIES
    add r0, r4, r0
    mov r1, #0
    ldr r2, [r4, #RT_CODESIZE]
    bl mem_fill
    ldr r7, [r4, #RT_CODE]
    ldr r9, [r4, #RT_CODESIZE]
    mov r8, #0
    cmp r9, #0
    beq v_bad_jump
vc_decode:
    ldrb r5, [r7, r8]
    cmp r5, #SCRIPT_OPCODE_COUNT
    bhs v_bad_opcode
    ldr r0, =script_op_size
    ldrb r0, [r0, r5]
    add r1, r8, r0
    cmp r1, r9
    bhi v_truncated
    ldr r2, =RT_BOUNDARIES
    add r2, r4, r2
    mov r3, #1
    strb r3, [r2, r8]
    mov r10, r8
    mov r8, r1
    cmp r8, r9
    blo vc_decode
    ldr r0, =script_op_flow
    ldrb r0, [r0, r5]
    cmp r0, #FLOW_END
    cmpne r0, #FLOW_JUMP
    movne r8, r10
    bne v_bad_jump
    mov r8, #0
vc_operands:
    ldrb r5, [r7, r8]
    add r0, r7, r8
    mov r1, r5
    bl decode_operands
    mov r10, r0
    mov r11, r1
    cmp r5, #OP_PUSHK
    beq vc_const
    cmp r5, #OP_PUSHS
    beq vc_string
    cmp r5, #OP_LOAD
    cmpne r5, #OP_STORE
    beq vc_var
    cmp r5, #OP_ALOAD
    cmpne r5, #OP_ASTORE
    beq vc_array
    cmp r5, #OP_JMP
    cmpne r5, #OP_JZ
    cmpne r5, #OP_JNZ
    cmpne r5, #OP_CALL
    beq vc_target
    cmp r5, #OP_CALLAPI
    beq vc_api
    b vc_next
vc_const:
    add r0, r6, #HDR_CONST_COUNT
    bl read_half
    cmp r10, r0
    bhs v_bad_const
    b vc_next
vc_string:
    add r0, r6, #HDR_STRING_COUNT
    bl read_half
    cmp r10, r0
    bhs v_bad_string
    b vc_next
vc_var:
    ldr r0, [r6, #HDR_VAR_COUNT]
    cmp r10, r0
    bhs v_bad_var
    b vc_next
vc_array:
    cmp r11, #0
    beq v_bad_var
    add r0, r10, r11
    ldr r1, [r6, #HDR_VAR_COUNT]
    cmp r0, r1
    bhi v_bad_var
    b vc_next
vc_target:
    cmp r10, r9
    bhs v_bad_jump
    ldr r0, =RT_BOUNDARIES
    add r0, r4, r0
    ldrb r0, [r0, r10]
    cmp r0, #0
    beq v_bad_jump
    b vc_next
vc_api:
    cmp r10, #SCRIPT_API_ENTRIES
    bhs v_api_unknown
    mov r0, r10, lsl #5
    add r0, r0, r10, lsl #4
    ldr r1, =script_api_table
    add r0, r0, r1
    ldrb r1, [r0]
    cmp r1, #0
    beq v_api_unknown
    mov r3, r0
    add r0, r0, #SCRIPT_API_SINCE
    bl read_half
    mov r2, r0
    add r0, r6, #HDR_API_VERSION
    bl read_half
    cmp r2, r0
    bhi v_api_version
    ldrb r1, [r3, #1]
    cmp r11, r1
    bne v_api_argc
vc_next:
    ldr r0, =script_op_size
    ldrb r0, [r0, r5]
    add r8, r8, r0
    cmp r8, r9
    blo vc_operands
    ldr r0, =RT_ARGC
    add r0, r4, r0
    mov r1, #255
    ldr r2, [r4, #RT_CODESIZE]
    bl mem_fill
    ldr r0, =RT_FNSTATE
    add r0, r4, r0
    mov r1, #0
    ldr r2, [r4, #RT_CODESIZE]
    bl mem_fill
    add r0, r6, #HDR_ENTRY
    bl read_half
    mov r8, r0
    cmp r8, r9
    bhs v_bad_handler_no_offset
    ldr r0, =RT_BOUNDARIES
    add r0, r4, r0
    ldrb r0, [r0, r8]
    cmp r0, #0
    beq v_bad_handler_no_offset
    ldr r0, =RT_ARGC
    add r0, r4, r0
    mov r1, #0
    strb r1, [r0, r8]
    add r10, r6, #HDR_SIZE
    ldr r11, [r4, #RT_CONSTANTS]
    mov r5, #0
vc_handlers:
    cmp r10, r11
    bhs vc_roots
    ldrb r0, [r10]
    cmp r0, #0
    beq v_bad_handler_no_offset
    cmp r0, #SCRIPT_EVENT_COUNT
    bhs v_bad_handler_no_offset
    mov r1, #1
    mov r1, r1, lsl r0
    tst r5, r1
    bne v_bad_handler_no_offset
    orr r5, r5, r1
    ldr r1, =script_event_argc
    ldrb r1, [r1, r0]
    ldrb r7, [r10, #1]
    cmp r7, r1
    bhi v_bad_handler_no_offset
    add r0, r10, #2
    bl read_half
    mov r8, r0
    cmp r8, r9
    bhs v_bad_handler_no_offset
    ldr r0, =RT_BOUNDARIES
    add r0, r4, r0
    ldrb r0, [r0, r8]
    cmp r0, #0
    beq v_bad_handler_no_offset
    ldr r0, =RT_ARGC
    add r0, r4, r0
    ldrb r1, [r0, r8]
    cmp r1, #255
    beq vc_handler_set
    cmp r1, r7
    bne v_stack_mismatch_no_offset
vc_handler_set:
    strb r7, [r0, r8]
    add r10, r10, #SEC_HANDLER
    b vc_handlers
vc_roots:
    add r0, r6, #HDR_ENTRY
    bl read_half
    mov r1, #0
    bl verify_fn
    cmp r0, #0
    bne verify_return
    add r10, r6, #HDR_SIZE
    ldr r11, [r4, #RT_CONSTANTS]
vc_fn_roots:
    cmp r10, r11
    bhs vc_api_roots
    add r0, r10, #2
    bl read_half
    mov r1, #0
    bl verify_fn
    cmp r0, #0
    bne verify_return
    add r10, r10, #SEC_HANDLER
    b vc_fn_roots
vc_api_roots:
    add r0, r6, #HDR_ENTRY
    bl read_half
    mov r1, #0
    bl verify_event
    cmp r0, #0
    bne verify_return
    add r10, r6, #HDR_SIZE
    ldr r11, [r4, #RT_CONSTANTS]
vc_event_roots:
    cmp r10, r11
    bhs vc_lines
    add r0, r10, #2
    bl read_half
    ldrb r1, [r10]
    bl verify_event
    cmp r0, #0
    bne verify_return
    add r10, r10, #SEC_HANDLER
    b vc_event_roots
vc_lines:
    ldr r10, [r4, #RT_LINES]
    ldr r11, [r4, #RT_LINECOUNT]
    mvn r5, #0
vc_line:
    cmp r11, #0
    beq vc_ok
    mov r0, r10
    bl read_half
    cmp r0, r9
    bhs v_bad_lines_no_offset
    cmp r5, #0
    blt vc_line_boundary
    cmp r0, r5
    bls v_bad_lines_no_offset
vc_line_boundary:
    mov r5, r0
    ldr r1, =RT_BOUNDARIES
    add r1, r4, r1
    ldrb r1, [r1, r0]
    cmp r1, #0
    beq v_bad_lines_no_offset
    add r0, r10, #2
    bl read_half
    cmp r0, #0
    beq v_bad_lines_no_offset
    add r10, r10, #SEC_LINE
    sub r11, r11, #1
    b vc_line
vc_ok:
    mov r0, #ERR_OK
verify_return:
    pop {r5, r7, r9-r11, pc}
.pool

; Each function has one argument count, a completed stack maximum and call depth.
verify_fn:
    push {r5, r7, r9-r11, lr}
    sub sp, sp, #16
    mov r5, r0
    str r1, [sp, #4]
    ldr r2, =RT_FNSTATE
    add r2, r4, r2
    ldrb r3, [r2, r5]
    cmp r3, #2
    beq vf_ok
    cmp r3, #1
    beq vf_recursion
    mov r3, #1
    strb r3, [r2, r5]
vf_restart:
    mov r0, #0
    str r0, [sp]
    ldr r0, =RT_DEPTH
    add r0, r4, r0
    mov r1, #255
    ldr r2, [r4, #RT_CODESIZE]
    bl mem_fill
    ldr r0, =RT_ARGC
    add r0, r4, r0
    ldrb r9, [r0, r5]
    mov r11, r9
    mov r8, r5
    mov r10, #0
vf_ins:
    ldr r0, =RT_DEPTH
    add r0, r4, r0
    ldrb r1, [r0, r8]
    cmp r1, #255
    beq vf_visit
    cmp r1, r9
    bne vf_stack_mismatch
    b vf_work
vf_visit:
    strb r9, [r0, r8]
    ldr r7, [r4, #RT_CODE]
    ldrb r7, [r7, r8]
    ldr r0, [r4, #RT_CODE]
    add r0, r0, r8
    mov r1, r7
    bl decode_operands
    str r0, [sp, #8]
    str r1, [sp, #12]
    ldr r0, =script_op_pop
    ldrb r0, [r0, r7]
    cmp r0, #SCRIPT_POP_ARGC
    moveq r0, r1
    cmp r9, r0
    blo vf_stack
    sub r9, r9, r0
    ldr r1, =script_op_push
    ldrb r1, [r1, r7]
    add r9, r9, r1
    cmp r9, #LIM_STACK
    bhi vf_stack_no_offset
    cmp r9, r11
    movhi r11, r9
    cmp r7, #OP_CALL
    beq vf_call
    b vf_flow
vf_call:
    ldr r0, [sp, #8]
    ldr r1, =RT_ARGC
    add r1, r4, r1
    ldrb r2, [r1, r0]
    ldr r3, [sp, #12]
    cmp r2, #255
    strbeq r3, [r1, r0]
    beq vf_child
    cmp r2, r3
    bne vf_stack_mismatch
vf_child:
    ldr r1, =RT_FNSTATE
    add r1, r4, r1
    ldrb r2, [r1, r0]
    cmp r2, #1
    beq vf_recursion
    cmp r2, #2
    beq vf_summary
    ldr r1, [sp, #4]
    add r1, r1, #1
    cmp r1, #LIM_CALL_DEPTH
    bhi vf_call_depth_no_offset
    bl verify_fn
    cmp r0, #0
    bne vf_return
    b vf_restart
vf_summary:
    ldr r1, =RT_NEED
    add r1, r4, r1
    ldrb r1, [r1, r0]
    add r1, r9, r1
    sub r1, r1, #1
    cmp r1, r11
    movhi r11, r1
    cmp r11, #LIM_STACK
    bhi vf_stack_no_offset
    ldr r1, =RT_DEEP
    add r1, r4, r1
    ldrb r1, [r1, r0]
    add r1, r1, #1
    ldr r2, [sp]
    cmp r1, r2
    strhi r1, [sp]
    cmp r1, #LIM_CALL_DEPTH
    bhi vf_call_depth_no_offset
vf_flow:
    cmp r7, #OP_HALT
    cmpne r7, #OP_RET
    beq vf_end
    cmp r7, #OP_JMP
    ldreq r8, [sp, #8]
    beq vf_ins
    cmp r7, #OP_JZ
    cmpne r7, #OP_JNZ
    bne vf_next
    ldr r0, =RT_WORK
    add r0, r4, r0
    ldr r1, [sp, #8]
    orr r1, r1, r9, lsl #16
    str r1, [r0, r10, lsl #2]
    add r10, r10, #1
vf_next:
    ldr r0, =script_op_size
    ldrb r0, [r0, r7]
    add r8, r8, r0
    b vf_ins
vf_end:
    cmp r9, #0
    bne vf_stack_mismatch
vf_work:
    cmp r10, #0
    beq vf_complete
    sub r10, r10, #1
    ldr r0, =RT_WORK
    add r0, r4, r0
    ldr r1, [r0, r10, lsl #2]
    mov r9, r1, lsr #16
    mov r8, r1, lsl #16
    mov r8, r8, lsr #16
    b vf_ins
vf_complete:
    ldr r0, =RT_NEED
    add r0, r4, r0
    strb r11, [r0, r5]
    ldr r0, =RT_DEEP
    add r0, r4, r0
    ldr r1, [sp]
    strb r1, [r0, r5]
    add r0, r6, #HDR_STACK_MAX
    bl read_half
    cmp r11, r0
    bhi vf_stack_mismatch_no_offset
    ldr r0, =RT_FNSTATE
    add r0, r4, r0
    mov r1, #2
    strb r1, [r0, r5]
vf_ok:
    mov r0, #ERR_OK
vf_return:
    add sp, sp, #16
    pop {r5, r7, r9-r11, pc}
.pool

verify_event:
    push {r5, r7, r9-r11, lr}
    mov r8, r0
    mov r5, #1
    mov r5, r5, lsl r1
    ldr r0, =RT_DEPTH
    add r0, r4, r0
    mov r1, #0
    ldr r2, [r4, #RT_CODESIZE]
    bl mem_fill
    mov r10, #0
ve_ins:
    ldr r0, =RT_DEPTH
    add r0, r4, r0
    ldrb r1, [r0, r8]
    cmp r1, #0
    bne ve_work
    mov r1, #1
    strb r1, [r0, r8]
    ldr r7, [r4, #RT_CODE]
    ldrb r7, [r7, r8]
    ldr r0, [r4, #RT_CODE]
    add r0, r0, r8
    mov r1, r7
    bl decode_operands
    mov r9, r0
    cmp r7, #OP_CALLAPI
    bne ve_flow
    mov r0, r9, lsl #5
    add r0, r0, r9, lsl #4
    ldr r1, =script_api_table
    add r0, r0, r1
    ldr r0, [r0, #4]
    tst r0, r5
    beq ve_api_event
ve_flow:
    cmp r7, #OP_HALT
    cmpne r7, #OP_RET
    beq ve_work
    cmp r7, #OP_JMP
    moveq r8, r9
    beq ve_ins
    cmp r7, #OP_JZ
    cmpne r7, #OP_JNZ
    cmpne r7, #OP_CALL
    bne ve_next
    ldr r0, =RT_WORK
    add r0, r4, r0
    str r9, [r0, r10, lsl #2]
    add r10, r10, #1
ve_next:
    ldr r0, =script_op_size
    ldrb r0, [r0, r7]
    add r8, r8, r0
    b ve_ins
ve_work:
    cmp r10, #0
    beq ve_ok
    sub r10, r10, #1
    ldr r0, =RT_WORK
    add r0, r4, r0
    ldr r8, [r0, r10, lsl #2]
    b ve_ins
ve_ok:
    mov r0, #ERR_OK
ve_return:
    pop {r5, r7, r9-r11, pc}
ve_api_event:
    mov r0, #ERR_API_EVENT
    b ve_return
.pool

; r0 runtime, r1 table entry, r2 event id, r3 event values.
script_run_event:
    push {r4-r11, lr}
    sub sp, sp, #4
    mov r4, r0
    mov r5, r1
    mov r11, r3
    str r5, [r4, #RT_ENTRY]
    str r2, [r4, #RT_EVENT]
    mov r0, #0
    str r0, [r4, #RT_OPS]
    str r0, [r4, #RT_COST]
    str r0, [r4, #RT_OFFSET]
    str r0, [r4, #RT_CALLDEPTH]
    str r0, [r4, #RT_HANDLED]
    ldr r0, [r5, #SCRIPT_ENTRY_STATE]
    cmp r2, #EV_START
    beq run_body
    cmp r0, #SCRIPT_STATE_ARMED
    bne run_skipped
    cmp r2, #SCRIPT_EVENT_COUNT
    bhs run_skipped
    ldr r6, [r5, #SCRIPT_ENTRY_BLOB]
    mov r7, #0
    mov r8, #HDR_SIZE
    add r0, r6, #HDR_HANDLER_COUNT
    bl read_half
    mov r9, r0
find_handler:
    cmp r7, r9
    bhs run_skipped
    ldrb r0, [r6, r8]
    ldr r1, [r4, #RT_EVENT]
    cmp r0, r1
    beq found_handler
    add r8, r8, #SEC_HANDLER
    add r7, r7, #1
    b find_handler
found_handler:
    add r0, r6, r8
    ldrb r9, [r0, #1]
    add r0, r0, #2
    bl read_half
    mov r8, r0
    b run_prepare
run_body:
    cmp r0, #SCRIPT_STATE_LOADED
    bne run_skipped
    ldr r6, [r5, #SCRIPT_ENTRY_BLOB]
    add r0, r6, #HDR_ENTRY
    bl read_half
    mov r8, r0
    mov r9, #0
run_prepare:
    bl set_sections
    mov r0, #1
    str r0, [r4, #RT_HANDLED]
    ldr r0, =RT_STACK
    add r0, r4, r0
    mov r1, #0
copy_args:
    cmp r1, r9
    bhs args_done
    ldr r2, [r11, r1, lsl #2]
    str r2, [r0, r1, lsl #2]
    add r1, r1, #1
    b copy_args
args_done:
    mov r11, r0
    ldr r10, [r4, #RT_FUEL]
    ldr r7, [r4, #RT_CODE]
    ldr r0, =SCRIPT_TIMER_ADDRESS
    ldr r0, [r0]
    str r0, [r4, #RT_STARTED]
run_next:
    ldr r0, [r4, #RT_CODESIZE]
    cmp r8, r0
    bhs e_bad_jump
    str r8, [r4, #RT_OFFSET]
    ldrb r2, [r7, r8]
    cmp r2, #SCRIPT_OPCODE_COUNT
    bhs e_bad_opcode
    ldr r0, =script_op_size
    ldrb r1, [r0, r2]
    add r1, r8, r1
    ldr r0, [r4, #RT_CODESIZE]
    cmp r1, r0
    bhi e_truncated
    ldr r0, [r4, #RT_OPS]
    cmp r0, #0
    bne run_periodic
    ldr r1, [r4, #RT_FRAME_ACTIVE]
    cmp r1, #1
    bne run_fuel
    b run_time
run_periodic:
    tst r0, #LIM_TIME_CHECK_EVERY-1
    bne run_fuel
run_time:
    ldr r0, =SCRIPT_TIMER_ADDRESS
    ldr r0, [r0]
    ldr r1, [r4, #RT_FRAME_ACTIVE]
    cmp r1, #1
    ldreq r1, [r4, #RT_FRAME_START]
    ldrne r1, [r4, #RT_STARTED]
    cmp r0, r1
    sub r0, r0, r1
    ldrlo r1, =SCRIPT_TIMER_PERIOD
    addlo r0, r0, r1
    ldr r1, [r4, #RT_MAXTICKS]
    cmp r0, r1
    bhi e_time
run_fuel:
    ldr r0, =script_op_cost
    ldrb r0, [r0, r2]
    cmp r0, r10
    bhi e_fuel
    push {r0, r2}
    add r0, r7, r8
    mov r1, r2
    bl decode_operands
    pop {r2, r3}
    push {r0, r1}
    ldr r12, =script_op_pop
    ldrb r12, [r12, r3]
    cmp r12, #SCRIPT_POP_ARGC
    moveq r12, r1
    cmp r9, r12
    blo run_stack_failed
    sub r12, r9, r12
    ldr r0, =script_op_push
    ldrb r0, [r0, r3]
    add r12, r12, r0
    cmp r12, #LIM_STACK
    bhi run_stack_failed
    sub r10, r10, r2
    ldr r0, [r4, #RT_COST]
    add r0, r0, r2
    str r0, [r4, #RT_COST]
    ldr r0, [r4, #RT_OPS]
    add r0, r0, #1
    str r0, [r4, #RT_OPS]
    ldr r0, =script_op_size
    ldrb r0, [r0, r3]
    add r8, r8, r0
    pop {r0, r1}
    ldr r2, =script_dispatch
    ldr pc, [r2, r3, lsl #2]
run_stack_failed:
    add sp, sp, #8
    b e_stack
run_skipped:
    mov r0, #ERR_OK
    add sp, sp, #4
    pop {r4-r11, pc}
.pool

op_halt:
    mov r0, #ERR_OK
    b run_finish
op_pushb:
    str r0, [r11, r9, lsl #2]
    add r9, r9, #1
    b run_next
op_pushk:
    ldrb r1, [r6, #HDR_CONST_COUNT+1]
    ldrb r2, [r6, #HDR_CONST_COUNT]
    orr r1, r2, r1, lsl #8
    cmp r0, r1
    bhs e_bad_const
    ldr r1, [r4, #RT_CONSTANTS]
    ldr r0, [r1, r0, lsl #2]
    b op_pushb
op_pushs:
    ldrb r1, [r6, #HDR_STRING_COUNT]
    cmp r0, r1
    bhs e_bad_string
    b op_pushb
op_load:
    ldr r1, [r6, #HDR_VAR_COUNT]
    cmp r0, r1
    bhs e_bad_var
    ldr r1, [r5, #SCRIPT_ENTRY_VARS]
    ldr r0, [r1, r0, lsl #2]
    b op_pushb
op_store:
    ldr r1, [r6, #HDR_VAR_COUNT]
    cmp r0, r1
    bhs e_bad_var
    sub r9, r9, #1
    ldr r2, [r11, r9, lsl #2]
    ldr r1, [r5, #SCRIPT_ENTRY_VARS]
    str r2, [r1, r0, lsl #2]
    b run_next
op_aload:
    cmp r1, #0
    beq e_bad_var
    add r2, r0, r1
    ldr r3, [r6, #HDR_VAR_COUNT]
    cmp r2, r3
    bhi e_bad_var
    sub r2, r9, #1
    ldr r3, [r11, r2, lsl #2]
    cmp r3, r1
    bhs e_bounds
    add r0, r0, r3
    ldr r1, [r5, #SCRIPT_ENTRY_VARS]
    ldr r0, [r1, r0, lsl #2]
    str r0, [r11, r2, lsl #2]
    b run_next
op_astore:
    cmp r1, #0
    beq e_bad_var
    add r2, r0, r1
    ldr r3, [r6, #HDR_VAR_COUNT]
    cmp r2, r3
    bhi e_bad_var
    sub r9, r9, #1
    ldr r2, [r11, r9, lsl #2]
    sub r9, r9, #1
    ldr r3, [r11, r9, lsl #2]
    cmp r3, r1
    bhs e_bounds
    add r0, r0, r3
    ldr r1, [r5, #SCRIPT_ENTRY_VARS]
    str r2, [r1, r0, lsl #2]
    b run_next
op_dup:
    sub r0, r9, #1
    ldr r0, [r11, r0, lsl #2]
    b op_pushb
op_drop:
    sub r9, r9, #1
    b run_next
op_neg:
    sub r1, r9, #1
    ldr r0, [r11, r1, lsl #2]
    rsb r0, r0, #0
    str r0, [r11, r1, lsl #2]
    b run_next
op_not:
    sub r1, r9, #1
    ldr r0, [r11, r1, lsl #2]
    cmp r0, #0
    mov r0, #0
    moveq r0, #1
    str r0, [r11, r1, lsl #2]
    b run_next
op_jmp:
    mov r8, r0
    b run_next
op_jz:
    sub r9, r9, #1
    ldr r2, [r11, r9, lsl #2]
    cmp r2, #0
    moveq r8, r0
    b run_next
op_jnz:
    sub r9, r9, #1
    ldr r2, [r11, r9, lsl #2]
    cmp r2, #0
    movne r8, r0
    b run_next
op_call:
    ldr r1, [r4, #RT_CALLDEPTH]
    cmp r1, #LIM_CALL_DEPTH
    bhs e_call_depth
    add r2, r4, #RT_CALLS
    str r8, [r2, r1, lsl #2]
    add r1, r1, #1
    str r1, [r4, #RT_CALLDEPTH]
    mov r8, r0
    b run_next
op_ret:
    ldr r1, [r4, #RT_CALLDEPTH]
    cmp r1, #0
    moveq r0, #ERR_OK
    beq run_finish
    sub r1, r1, #1
    str r1, [r4, #RT_CALLDEPTH]
    add r2, r4, #RT_CALLS
    ldr r8, [r2, r1, lsl #2]
    b run_next
.pool

op_callapi:
    cmp r0, #SCRIPT_API_ENTRIES
    bhs e_api_unknown
    mov r2, r0, lsl #5
    add r2, r2, r0, lsl #4
    ldr r3, =script_api_table
    add r2, r2, r3
    ldrb r3, [r2]
    cmp r3, #0
    beq e_api_unknown
    ldrb r3, [r2, #1]
    cmp r3, r1
    bne e_api_argc
    ldrb r3, [r2, #SCRIPT_API_SINCE]
    ldrb r12, [r2, #SCRIPT_API_SINCE+1]
    orr r3, r3, r12, lsl #8
    ldrb r12, [r6, #HDR_API_VERSION]
    ldrb r0, [r6, #HDR_API_VERSION+1]
    orr r12, r12, r0, lsl #8
    cmp r3, r12
    bhi e_api_version
    ldr r3, [r2, #4]
    ldr r12, [r4, #RT_EVENT]
    mov r3, r3, lsr r12
    tst r3, #1
    beq e_api_event
    ldrb r3, [r2, #3]
    cmp r3, r10
    bhi e_fuel
    sub r10, r10, r3
    ldr r12, [r4, #RT_COST]
    add r12, r12, r3
    str r12, [r4, #RT_COST]
    sub sp, sp, #16
    mov r3, #0
    mov r12, #0
    str r12, [sp]
    str r12, [sp, #4]
    str r12, [sp, #8]
    str r12, [sp, #12]
    sub r9, r9, r1
api_args:
    cmp r3, r1
    bhs api_invoke
    add r0, r9, r3
    ldr r0, [r11, r0, lsl #2]
    ldrb r12, [r2, #8]
    mov r12, r12, lsr r3
    tst r12, #1
    bne api_text
    ldrb r12, [r2, #9]
    mov r12, r12, lsr r3
    tst r12, #1
    bne api_array
    add r12, r2, r3, lsl #2
    ldr r12, [r12, #16]
    cmp r0, r12
    blt api_bad_arg
    add r12, r2, r3, lsl #2
    ldr r12, [r12, #32]
    cmp r0, r12
    bgt api_bad_arg
    b api_arg_store
api_text:
    ldrb r12, [r6, #HDR_STRING_COUNT]
    cmp r0, r12
    bhs api_bad_string
    ldr r12, [r4, #RT_STRINGS]
    add r0, r12, r0, lsl #5
api_arg_store:
    str r0, [sp, r3, lsl #2]
    add r3, r3, #1
    b api_args
; An array argument is the handle (first slot in the low half, length in the high half). It has to lie inside the
; variable area, and the call pays the entry's fuel for each of its slots. The glue gets the handle as it is.
api_array:
    str r0, [sp, r3, lsl #2]
    movs r12, r0, lsr #16
    beq api_bad_var
    mov r0, r0, lsl #16
    add r0, r12, r0, lsr #16
    push {r1}
    ldr r1, [r6, #HDR_VAR_COUNT]
    cmp r0, r1
    ldrb r1, [r2, #2]
    mul r0, r12, r1
    pop {r1}
    bhi api_bad_var
    cmp r0, r10
    bhi api_no_fuel
    sub r10, r10, r0
    ldr r12, [r4, #RT_COST]
    add r12, r12, r0
    str r12, [r4, #RT_COST]
    add r3, r3, #1
    b api_args
api_invoke:
    ldr r12, [r2, #12]
    cmp r12, #0
    beq api_no_glue
    ldmia sp, {r0-r3}
    blx r12
    add sp, sp, #16
    cmp r1, #ERR_OK
    movne r0, r1
    bne run_finish
    b op_pushb
api_no_glue:
    add sp, sp, #16
    mov r0, #0
    b op_pushb
api_bad_arg:
    add sp, sp, #16
    b e_api_arg
api_bad_string:
    add sp, sp, #16
    b e_bad_string
api_bad_var:
    add sp, sp, #16
    b e_bad_var
api_no_fuel:
    add sp, sp, #16
    b e_fuel
.pool

; r0 numerator, r1 nonzero denominator -> signed quotient r0 and remainder r1.
signed_divide:
    push {r4-r7, lr}
    mov r5, r0
    eor r6, r0, r1
    cmp r0, #0
    rsblt r0, r0, #0
    cmp r1, #0
    rsblt r1, r1, #0
    mov r2, #0
    mov r3, #0
    mov r4, #32
div_bit:
    movs r0, r0, lsl #1
    adc r2, r2, r2
    cmp r2, r1
    subhs r2, r2, r1
    adc r3, r3, r3
    subs r4, r4, #1
    bne div_bit
    cmp r6, #0
    rsblt r3, r3, #0
    cmp r5, #0
    rsblt r2, r2, #0
    mov r0, r3
    mov r1, r2
    pop {r4-r7, pc}

run_finish:
    cmp r0, #ERR_OK
    bne run_store
    ldr r2, [r4, #RT_FRAME_ACTIVE]
    cmp r2, #1
    bne run_store
    ldr r2, =SCRIPT_TIMER_ADDRESS
    ldr r2, [r2]
    ldr r3, [r4, #RT_FRAME_START]
    cmp r2, r3
    sub r2, r2, r3
    ldrlo r3, =SCRIPT_TIMER_PERIOD
    addlo r2, r2, r3
    ldr r3, [r4, #RT_MAXTICKS]
    cmp r2, r3
    movhi r0, #ERR_TIME
run_store:
    str r0, [r5, #SCRIPT_ENTRY_FAULT]
    ldr r1, [r4, #RT_OFFSET]
    str r1, [r5, #SCRIPT_ENTRY_OFFSET]
    ldr r2, [r4, #RT_OPS]
    str r2, [r5, #SCRIPT_ENTRY_OPS]
    ldr r2, [r4, #RT_COST]
    str r2, [r5, #SCRIPT_ENTRY_COST]
    ldr r3, [r4, #RT_EVENT]
    str r3, [r5, #SCRIPT_ENTRY_EVENT]
    add r3, r5, #SCRIPT_ENTRY_MAX_COST
    ldr r12, [r4, #RT_EVENT]
    ldr r12, [r3, r12, lsl #2]
    cmp r2, r12
    ldr r12, [r4, #RT_EVENT]
    strhi r2, [r3, r12, lsl #2]
    ldr r2, =SCRIPT_TIMER_ADDRESS
    ldr r2, [r2]
    ldr r3, [r4, #RT_STARTED]
    cmp r2, r3
    sub r2, r2, r3
    ldrlo r3, =SCRIPT_TIMER_PERIOD
    addlo r2, r2, r3
    ldr r3, [r5, #SCRIPT_ENTRY_MAX_TICKS]
    cmp r2, r3
    strhi r2, [r5, #SCRIPT_ENTRY_MAX_TICKS]
    add r3, r5, #SCRIPT_ENTRY_MAX_EVENT_TICKS
    ldr r12, [r4, #RT_EVENT]
    add r3, r3, r12, lsl #2
    ldr r12, [r3]
    cmp r2, r12
    strhi r2, [r3]
    ldr r2, [r4, #RT_LINES]
    ldr r3, [r4, #RT_LINECOUNT]
    mov r7, #0
finish_line:
    cmp r3, #0
    beq finish_state
    ldrb r8, [r2]
    ldrb r9, [r2, #1]
    orr r8, r8, r9, lsl #8
    cmp r8, r1
    bhi finish_state
    ldrb r7, [r2, #2]
    ldrb r9, [r2, #3]
    orr r7, r7, r9, lsl #8
    add r2, r2, #SEC_LINE
    sub r3, r3, #1
    b finish_line
finish_state:
    str r7, [r5, #SCRIPT_ENTRY_LINE]
    cmp r0, #ERR_OK
    movne r1, #SCRIPT_STATE_DISABLED
    strne r1, [r5, #SCRIPT_ENTRY_STATE]
    bne finished
    ldr r1, [r4, #RT_EVENT]
    cmp r1, #EV_START
    moveq r1, #SCRIPT_STATE_ARMED
    streq r1, [r5, #SCRIPT_ENTRY_STATE]
finished:
    add sp, sp, #4
    pop {r4-r11, pc}
.pool

; Dispatching continues after an individual script fault.
script_dispatch_event:
    push {r4-r8, lr}
    mov r4, r0
    mov r6, r1
    mov r7, r2
    mov r8, #ERR_OK
    ldr r5, [r4, #RT_HEAD]
dispatch_entry:
    cmp r5, #0
    beq dispatch_done
    mov r0, r4
    mov r1, r5
    mov r2, r6
    mov r3, r7
    bl script_run_event
    cmp r8, #ERR_OK
    moveq r8, r0
    ldr r5, [r5, #SCRIPT_ENTRY_NEXT]
    b dispatch_entry
dispatch_done:
    mov r0, r8
    pop {r4-r8, pc}
.pool
