#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Prüft SHA256 und Firmwarebereichsgrenzen ohne fremde Binärdaten."""
import argparse
import ctypes
import hashlib
from pathlib import Path
import subprocess
import sys
import unittest
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_bootstrap as loader
from artifacts import external_output


class HashState(ctypes.Structure):
    _fields_ = [("h",ctypes.c_uint32*8),("bytes",ctypes.c_uint64),("used",ctypes.c_uint),("block",ctypes.c_ubyte*64)]


class HashTests(unittest.TestCase):
    def test_vectors_and_chunk_boundaries(self):
        for data in [b"",b"abc",b"a"*1_000_000,bytes(range(256))*3,*[b"x"*n for n in [55,56,63,64,65,119,120,127,128,129,4095,4096,4097]]]:
            for chunk in [1,7,64,4096,len(data) or 1]:
                with self.subTest(length=len(data),chunk=chunk):
                    context=HashState(); digest=(ctypes.c_ubyte*32)()
                    LIB.sha256_init(ctypes.byref(context))
                    for i in range(0,len(data),chunk):
                        block=data[i:i+chunk]
                        LIB.sha256_add(ctypes.byref(context),block,len(block))
                    LIB.sha256_finish(ctypes.byref(context),digest)
                    self.assertEqual(bytes(digest),hashlib.sha256(data).digest())


class BoundsTests(unittest.TestCase):
    def setUp(self):
        self.image=bytearray(b"\xff"*0x200100)
        self.site=loader.SITE-0xC0000000+0x100
        self.base=loader.BASE-0xC0000000+0x100
        self.image[self.site:self.site+4]=loader.branch(loader.SITE,0xC002A35C)
        self.previous=loader.SUPPORTED
        loader.SUPPORTED={hashlib.sha256(self.image).hexdigest()}
    def tearDown(self): loader.SUPPORTED=self.previous
    def test_only_site_and_own_bytes_change(self):
        result=loader.patch_image(self.image,b"\0"*128)
        loader.validate_delta(self.image, result)
        actual={i for i,(a,b) in enumerate(zip(self.image,result)) if a!=b}
        self.assertTrue(actual <= set(range(self.site,self.site+4)) | set(range(self.base,self.base+128)))
        self.assertEqual(len(result),len(self.image))
    def test_reference_delta_rejects_changes_outside_current_reservation(self):
        result = bytearray(loader.patch_image(self.image, b"\0" * 128))
        for at in [0, self.site - 1, self.site + 4, 0x173100,
                   self.base - 1, loader.LAYOUT["end"] - 0xC0000000 + 0x100]:
            changed = bytearray(result)
            changed[at] ^= 1
            with self.assertRaisesRegex(ValueError, "Referenzbasis"):
                loader.validate_delta(self.image, changed)
        with self.assertRaisesRegex(ValueError, "Länge"):
            loader.validate_delta(self.image, result[:-1])
        self.assertEqual(result[:256],self.image[:256])
    def test_unknown_firmware_rejected(self):
        self.image[0]^=1
        with self.assertRaisesRegex(ValueError,"Unbekannte Firmware"): loader.patch_image(self.image,b"x")
    def test_v8_whitelist_is_obsolete(self):
        self.assertNotIn("584f5b7a057adf23c04f07da09c8669c5410a68c494bdd19a66245fc8cfab9cb",self.previous)
    def test_truncated_reservation_rejected(self):
        del self.image[self.base+1:]
        loader.SUPPORTED={hashlib.sha256(self.image).hexdigest()}
        with self.assertRaisesRegex(ValueError,"zu kurz"): loader.patch_image(self.image,b"x")
    def test_occupied_reservation_rejected(self):
        self.image[loader.RESERVED_END-0xC0000000+0x100-1]=0
        loader.SUPPORTED={hashlib.sha256(self.image).hexdigest()}
        with self.assertRaisesRegex(ValueError,"belegt"): loader.patch_image(self.image,b"x")
    def test_wrong_site_rejected(self):
        self.image[self.site]^=1
        loader.SUPPORTED={hashlib.sha256(self.image).hexdigest()}
        with self.assertRaisesRegex(ValueError,"Originalaufruf"): loader.patch_image(self.image,b"x")
    def test_empty_and_oversized_bootstrap_rejected(self):
        for data in [b"",b"x"*(loader.LAYOUT["codeEnd"]-loader.BASE+1)]:
            with self.assertRaisesRegex(ValueError,"Codebereich"): loader.patch_image(self.image,data)
    def test_branch_bounds(self):
        for source,target in [(0,1),(0,0x2000008),(0x2000000,0)]:
            with self.assertRaises(ValueError): loader.branch(source,target)
        self.assertEqual(len(loader.branch(0x2000000,8)),4)


class OutputTests(unittest.TestCase):
    def test_repo_and_other_git_directories_are_rejected(self):
        root=HERE.parents[1]
        with self.assertRaisesRegex(ValueError,"außerhalb"): external_output(root/"build/doom")
        folder=Path(tempfile.mkdtemp(prefix="gelumpe-doom-path-"))
        repo=folder/"checkout"; repo.mkdir(); (repo/".git").write_text("gitdir: elsewhere\n")
        link=folder/"link"; link.symlink_to(repo,target_is_directory=True)
        for path in [repo,repo/"output",link/"output"]:
            with self.subTest(path=str(path)):
                with self.assertRaisesRegex(ValueError,"außerhalb"): external_output(path)
        self.assertEqual(external_output(folder/"allowed"),(folder/"allowed").resolve())


class ProgramTests(unittest.TestCase):
    def test_old_engine_shared_address_is_rejected(self):
        blob = b"own engine fixture"
        metadata = dict(sha256=hashlib.sha256(blob).hexdigest(), length=len(blob), entry=0xC1000000)
        for address in [None, 0xC0180000, 0xC019E000]:
            metadata["shared_address"] = address
            with self.assertRaisesRegex(ValueError,"Shared-Adresse"): loader.validate_program(blob, metadata)
        metadata["shared_address"] = loader.LAYOUT["shared"]
        self.assertEqual(loader.validate_program(blob, metadata), metadata["sha256"])


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    a,rest=p.parse_known_args()
    a.output.mkdir(parents=True,exist_ok=True)
    lib=a.output/"sha256.so"
    subprocess.run(["cc","-shared","-fPIC","-O2","-Wall","-Wextra","-Werror",str(HERE/"sha256.c"),"-o",str(lib)],check=True)
    LIB=ctypes.CDLL(str(lib))
    LIB.sha256_init.argtypes=[ctypes.POINTER(HashState)]
    LIB.sha256_add.argtypes=[ctypes.POINTER(HashState),ctypes.c_void_p,ctypes.c_size_t]
    LIB.sha256_finish.argtypes=[ctypes.POINTER(HashState),ctypes.c_void_p]
    unittest.main(argv=[sys.argv[0],*rest])
