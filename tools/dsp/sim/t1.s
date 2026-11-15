	.text
_start:
	R1 = 7 (X);
	R2 = -3 (X);
	R1 = R1 + R2;
	P4.H = 0x0310; P4.L = 0;
	[P4] = R1;
	R0 = P4;
	P0 = 1 (X);
	EXCPT 0;
