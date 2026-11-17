
	.text
_start:
	SP.L = 0x4600; SP.H = 0xff90;
	USP = SP; FP = SP; SP += -12;
	R0 = 0x400 (Z); R0 <<= 5;
	P1.L = 0x0878; P1.H = 0x01f1; CALL (P1);
	R0 = 0x3b (X);
	P1.L = 0x95f0; P1.H = 0xffa0; CALL (P1);
	P1.L = 0xec38; P1.H = 0x01f0; CALL (P1);
	P1.L = 0x08c8; P1.H = 0x01f1; CALL (P1);
	R0.L = 0x0ccc; R0.H = 0xff90;
	P1.L = 0x0164; P1.H = 0; CALL (P1);
	P1.L = 0xc8d4; P1.H = 0x01f0; CALL (P1);
	/* script pointer lives in [OUTBUF + 0x100] */
	P4.H = 0x0310; P4.L = 0;
	R0.H = 0x0200; R0.L = 0; [P4 + 0x100] = R0;
next:
	P4.H = 0x0310; P4.L = 0;
	P5 = [P4 + 0x100];
	R0 = [P5++];
	CC = R0 == 0; IF CC JUMP finish;
	R1 = 3 (X); CC = R0 == R1; IF CC JUMP blocks;
	R1 = 4 (X); CC = R0 == R1; IF CC JUMP emit;
	R1 = 5 (X); CC = R0 == R1; IF CC JUMP dump;
	/* 1 or 2: addr, count, halfwords */
	R7 = R0;
	P2 = [P5++];
	R2 = [P5++];
	P0 = R2;
	CC = R2 == 0; IF CC JUMP copied;
	LSETUP(cb, ce) LC0 = P0;
cb:	R3 = W[P5++] (Z);
ce:	W[P2++] = R3;
copied:
	R0 = P5; R0 += 3; R1 = -4 (X); R0 = R0 & R1; [P4 + 0x100] = R0;
	R1 = 2 (X); CC = R7 == R1; IF !CC JUMP next;
	P1.L = 0x3404; P1.H = 0xffc0; R0 = 0x10 (X); W[P1] = R0;
	R0 = 0x104 (Z);
	P1.L = 0x4ec8; P1.H = 0xffa0; CALL (P1);
	JUMP next;
blocks:
	R0 = [P5++]; [P4 + 0x100] = P5; [P4 + 0x104] = R0;
bloop:
	R4 = 0 (X);
frame:
	P4.H = 0xff80; P4.L = 0x2890;
	R5 = 0 (X);
	[P4 + -0x20] = R5; [P4 + -0x1c] = R5; [P4 + -0x18] = R5; [P4 + -0x14] = R5;
	P1.H = 0xff90; P1.L = 0x3170;
	[P1 + -0xcc] = R4;
	R1.H = 0xff80; R1.L = 0x0748;
	R0.H = 0xff90; R0.L = 0x0eac;
	[--SP] = R4;
	P1.L = 0x141a; P1.H = 0xffa0; CALL (P1);
	R4 = [SP++];
	R4 += 1; R0 = 4 (X); CC = R4 < R0; IF CC JUMP frame;
	P1.L = 0xe48c; P1.H = 0x01f0; CALL (P1);
	P5.H = 0xff80; P5.L = 0x0054; R0 = [P5]; R0 += 1; [P5] = R0;
	P4.H = 0x0310; P4.L = 0;
	R0 = [P4 + 0x104]; R0 += -1; [P4 + 0x104] = R0;
	CC = R0 == 0; IF !CC JUMP bloop;
	JUMP next;
emit:
	[P4 + 0x100] = P5;
	P1.H = 0xff90; P1.L = 0x30f4;
	R0 = [P1]; [P4 + 0x40] = R0; R0 = [P1 + 4]; [P4 + 0x44] = R0;
	P1.H = 0xff80; P1.L = 0x2890;
	R0 = [P1 + -0x10]; [P4 + 0x48] = R0; R0 = [P1 + -0xc]; [P4 + 0x4c] = R0;
	R0 = 1 (X); [P4 + 32] = R0;
	R0 = P4; R0 += 32; R0 += 32; [P4 + 36] = R0;
	R0 = 16 (X); [P4 + 40] = R0;
	R0 = P4; R0 += 32;
	P0 = 5 (X); EXCPT 0;
	JUMP next;
dump:
	R0 = [P5++]; R1 = [P5++]; [P4 + 0x100] = P5;
	[P4 + 36] = R0; [P4 + 40] = R1;
	R0 = 1 (X); [P4 + 32] = R0;
	R0 = P4; R0 += 32;
	P0 = 5 (X); EXCPT 0;
	JUMP next;
finish:
	R0 = 0 (X); [P4 + 32] = R0; R0 = P4; R0 += 32;
	P0 = 1 (X); EXCPT 0;
