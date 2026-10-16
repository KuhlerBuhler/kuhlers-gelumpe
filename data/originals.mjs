/**
 * Fingerprints of the factory slots in a Hacktribe release, one per slot.
 *
 * A factory slot that is byte for byte the release counts as "original": a
 * linter error found there already shipped and is a gap in what we know,
 * not a mistake of the user, so it is reported as a warning. Fatal and
 * silent findings stay blocked regardless.
 *
 * The first 16 hex digits of the SHA-256 of each 0x20C-byte record. Hashes,
 * not data: nothing of the firmware can be read back from them.
 */
export default [
  {
    release: "sampler-2.02-hacktribe",
    note: "the image on the SD card before any edit of ours, file hash 755d025f..., menus 32 master and 49 insert",
    mfx: ["4f1f7cb32a3279c5","828c9f6f64a02c37","54c647400373fa12","82b1e12a6c3d336a","3bf3be582564f151","8d7fc1a3b1405801","98b69541db4efe38","68adc865cec49692","16202704263ef8d5","5403c900b031d888","7e686fbc5095a1b6","c702c9283097edf2","a3897f369fb2d3cb","70b110613ea76f58","a96d4990a0629d43","b27979b0553d8c07","55007d09fc627883","2a16b1787e97e9bd","bd762881fb72c554","2f62f7999f676fbe","d1a9cc7d0e8851b8","b3cb3bb102fc7700","f281c5b07260e20a","ec27f0ccd29e9844","5df84cf9af77af44","e571d12d8b4f350f","de3640761504c98d","d8b0378fcb5fadb8","b23f564a3f280359","26157321b335aabd","44ce44ba0beea1f0","ddea27eb563a3609"],
    ifx: ["48a090d6b233e861","826b709e37e78362","fec3ff3a5e49b4d1","beb4d80b463e5630","a14176ed7218f257","00e04eff86f15645","fc6c41c80c72934d","3b37494c674819b6","5ab9aefbd0b9ed2c","662c13543fa439d4","b16eef129896a42b","9878751e6a1ea006","96c24047eacbd2e9","7091aae3128121fe","5a9b74c2b7f17e1e","6dc47c262fcfe680","c0f44aaae8e186d1","39a67e47ad91bd0e","256847e38e7ba031","e77a3165b19e9322","7c86073bf476fc04","c08dce2471f625f3","710525bc01b78783","a2e3d77fe71879ec","5d4184057f2ae071","a6535d5b53f17d58","77a76657421a8954","6b8ea6bae98388a7","45ca27ae656a301d","beb93921789129df","d47b2c685146d31d","399057e20bc9d182","26ec99da865e6722","ad91058bc9226a26","145ab8a9cebb3e63","df37450882f171b0","b6d601e3335550f8","5bb6f74646a02241","7ccc9b3f3181e68b","c4f2d211dc06f4d8","0dad6459a2c9887a","d3c8371e69686f43","d18d80bfd78eda78","75f8414599564565","eb852f0e6bc2464e","a7808963e1631fe4","35337a5b52104750","da50c611d8c6b8eb","435c2b0d40d3f366"],
  },
];
