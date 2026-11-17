nr_input:
nr_busy:
    mov r0, #0
    bx lr

nr_app_allowed:
    mov r0, #1
    bx lr
nr_close_capture_app:
    bx lr
