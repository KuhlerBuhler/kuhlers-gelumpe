	.text
_start:
	SP.L = 0x4600; SP.H = 0xff90;
	USP = SP; FP = SP; SP += -12;
	R0 = 0x400 (X); R0 <<= 5;
	P1.L = 0x0878; P1.H = 0x01f1;
	CALL (P1);
	R0 = 0x3b (X);
	P1.L = 0x95f0; P1.H = 0xffa0;
	CALL (P1);
	R7 = 1 (X); CALL done;
	P1.L = 0xec38; P1.H = 0x01f0;
	CALL (P1);
	R7 = 2 (X); CALL done;
	P1.L = 0x08c8; P1.H = 0x01f1;
	CALL (P1);
	R7 = 3 (X); CALL done;
	P2.H = 0xff80; P2.L = 0; R1 = 0x8000 (Z); CALL dump;
	P2.H = 0xff90; P2.L = 0; R1 = 0x8000 (Z); CALL dump;
	R0 = 0 (X); CALL ex;
dump:	/* write(1, P2, R1) */
	P4.H = 0x0310; P4.L = 0;
	R0 = 1 (X); [P4 + 32] = R0;
	R0 = P2; [P4 + 36] = R0;
	[P4 + 40] = R1;
	R0 = P4; R0 += 32;
	P0 = 5 (X);
	EXCPT 0;
	RTS;
done:	/* write marker R7 as one byte to stdout: write(1, buf, 1) */
	[--SP] = RETS;
	P4.H = 0x0310; P4.L = 0;
	B[P4 + 48] = R7;
	R0 = 1 (X); [P4 + 32] = R0;
	R0 = P4; R0 += 48; [P4 + 36] = R0;
	R0 = 1 (X); [P4 + 40] = R0;
	R0 = P4; R0 += 32;
	P0 = 5 (X);
	EXCPT 0;
	RETS = [SP++];
	RTS;
ex:	P4.H = 0x0310; P4.L = 0;
	[P4 + 32] = R0; R0 = P4; R0 += 32;
	P0 = 1 (X);
	EXCPT 0;
