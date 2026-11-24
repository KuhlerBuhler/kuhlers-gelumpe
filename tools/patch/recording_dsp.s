.text
/* THRU has finished its right channel; the click starts at the return address.
   The taps run every frame and never read a word the ARM writes: 0x01F00000 is write-through cacheable in the DSP's
   data CPLB table, so a host-port write there stays hidden behind the cached line, and a gate on the control word
   at +12 read 0 for good (silent takes on the device, 2026-11-24). */
record_after_input:
    R1 = (A0 += A1);
    P1.H = 0x01f1; P1.L = 0x2100;
    [P1] = R0; [P1 + 4] = R1;
    R2 = [P0++]; R3 = [P0++]; R7 = [P0++];
    P1.H = RECORD_INPUT_RETURN; P1.L = RECORD_INPUT_RETURN;
    JUMP (P1);

.org 0x80
/* The capture word uses the same smoothed output gain, with no click added. */
record_after_gain:
    P1.H = 0x01f1; P1.L = 0x2100;
    R5 = R0; R6 = R1;
    R0 = [P1]; R1 = [P1 + 4];
    A1 = R4.H * R0.L (M), A0 = R4.H * R0.H;
    A1 = A1 >>> 15;
    R0 = (A0 += A1);
    A1 = R4.H * R1.L (M), A0 = R4.H * R1.H;
    A1 = A1 >>> 15;
    R1 = (A0 += A1);
.if RECORD_CHANNELS == 1
    R0 >>>= 1; R1 >>>= 1;
    R0 = R0 + R1;
.else
    R0.L = 0;
    R1 = R1 >> 16;
    R1.H = 0;
    R0 = R0 | R1;
.endif
    [P1 + 8] = R0;
    R0 = R5; R1 = R6;
    R4.H = 0; R4.L = 1;
    R5 = R0 | R4;
    P1.H = RECORD_GAIN_RETURN; P1.L = RECORD_GAIN_RETURN;
    JUMP (P1);

.org 0x100
record_state:
    .long 0, 0, 0, 0, 0x4345524e
