.text
/* THRU has finished its right channel; the click starts at the return address. */
record_after_input:
    R1 = (A0 += A1);
    P1.H = 0x01f1; P1.L = 0x2100;
    R7 = [P1 + 12]; CC = R7 == 0;
    IF CC JUMP record_input_return;
    [P1] = R0; [P1 + 4] = R1;
record_input_return:
    R2 = [P0++]; R3 = [P0++]; R7 = [P0++];
    P1.H = 0xffa0; P1.L = 0x18e6;
    JUMP (P1);

.org 0x80
/* The capture word uses the same smoothed output gain, with no click added. */
record_after_gain:
    P1.H = 0x01f1; P1.L = 0x2100;
    R7 = [P1 + 12]; CC = R7 == 0;
    IF CC JUMP record_gain_return;
    R5 = R0; R6 = R1;
    R0 = [P1]; R1 = [P1 + 4];
    A1 = R4.H * R0.L (M), A0 = R4.H * R0.H;
    A1 = A1 >>> 15;
    R0 = (A0 += A1);
    A1 = R4.H * R1.L (M), A0 = R4.H * R1.H;
    A1 = A1 >>> 15;
    R1 = (A0 += A1);
    R0.L = 0;
    R1 = R1 >> 16;
    R1.H = 0;
    R0 = R0 | R1;
    [P1 + 8] = R0;
    R0 = R5; R1 = R6;
record_gain_return:
    R4.H = 0; R4.L = 1;
    R5 = R0 | R4;
    P1.H = 0xffa0; P1.L = 0x1948;
    JUMP (P1);

.org 0x100
record_state:
    .long 0, 0, 0, 0, 0x4345524e
