
; ---- the Patterns folder (red and Hacktribe; plan 2026-11-14-patterns-ordner)
; EXPORT PATTERN and EXPORT ALL PATTERN build their path as drive + 0xC0035720(type) + name + "." + extension, where 0xC0035720
; puts "KORG/blechtribe/" into a std::string (the folder string of the blechtribe patch). Both calls of it are sent here instead:
; the same string with "Patterns/" behind it. The folder is made first (f_mkdir, "exists" is no error to us), so a card whose
; KORG/blechtribe has no Patterns yet exports too. Nothing else of the firmware's export changes.
.equ PF_STRING, 0xC00A324C      ; std::string(this, const char *, allocator *), what 0xC0035720 calls
.equ PF_EXPORT_AT, 0xC00371B0   ; EXPORT PATTERN: bl 0xC0035720
.equ PF_EXPORT_ALL_AT, 0xC002E084   ; EXPORT ALL PATTERN: bl 0xC0035720

pat_export_hook:
    ldr lr, =PF_EXPORT_AT+4
    b pat_folder
pat_export_all_hook:
    ldr lr, =PF_EXPORT_ALL_AT+4
; r0 = the std::string to construct, r1 = the device type (unused: the folder string is the same for both). Returns r0 as 0xC0035720.
pat_folder:
    push {r0, r1, r4, lr}
    mov r4, r0
    ldr r0, =pf_dir
    ldr r12, =FS_MKDIR
    blx r12
    mov r0, r4
    ldr r1, =pf_path
    add r2, sp, #4
    ldr r12, =PF_STRING
    blx r12
    mov r0, r4
    add sp, sp, #4
    pop {r1, r4, pc}
.pool
pf_dir:
    .asciz "SD:KORG/blechtribe/Patterns"
pf_path:
    .asciz "KORG/blechtribe/Patterns/"
.align 4
