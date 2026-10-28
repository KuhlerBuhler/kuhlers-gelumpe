# SPDX-License-Identifier: GPL-2.0-only
"""A kept task result is taken only while its inputs and every file its task used are unchanged (taskcache.py,
parallel.run_tasks with `cache`). Runs without firmware and without Unicorn."""

import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fat32  # noqa: E402
import parallel  # noqa: E402

TOY_A = '''
import uuid
from pathlib import Path

def cases_task(i):
    text = (Path(__file__).parent / "toy_data.txt").read_text()
    return [{"id": f"a{i}", "ok": True, "nonce": uuid.uuid4().hex, "text": text}]
'''
TOY_B = '''
import uuid
import fat32

def cases_task():
    return [{"id": "b", "ok": True, "nonce": uuid.uuid4().hex, "clock": fat32.clock()}]
'''
TOY_C = '''
def cases_task():
    raise RuntimeError("broken")
'''


class TaskCacheTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.code = self.folder / "code"
        self.code.mkdir()
        for name, text in (("toy_a", TOY_A), ("toy_b", TOY_B), ("toy_c", TOY_C)):
            (self.code / f"{name}.py").write_text(textwrap.dedent(text))
        (self.code / "toy_data.txt").write_text("one")
        sys.path.insert(0, str(self.code))
        self.env = {k: os.environ.get(k) for k in ("GELUMPE_CACHE_DIR", "GELUMPE_CACHE", "PYTHONDONTWRITEBYTECODE")}
        os.environ["GELUMPE_CACHE_DIR"] = str(self.folder / "cache")
        os.environ.pop("GELUMPE_CACHE", None)
        os.environ.pop("PYTHONDONTWRITEBYTECODE", None)     # the workers write .pyc files, as they do on CI
        self.data = {"payload": b"firmware", "flash": None, "base": b"base"}
        self.tasks = [("toy_a", "cases_task", (1,)), ("toy_b", "cases_task", ())]

    def tearDown(self):
        sys.path.remove(str(self.code))
        for name in ("toy_a", "toy_b", "toy_c"):
            sys.modules.pop(name, None)
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.folder, ignore_errors=True)

    def nonces(self, data=None, jobs=2, tasks=None):
        out = parallel.run_tasks(tasks or self.tasks, data or self.data, jobs, cache="test")
        return [part[0]["nonce"] for part in out], out

    def test_an_unchanged_task_is_taken_from_the_cache(self):
        first, out = self.nonces()
        self.assertEqual(out[0][0]["text"], "one")
        self.assertEqual(self.nonces()[0], first)
        self.assertEqual(self.nonces(jobs=1)[0], first, "the same with the tasks in this process")

    def test_a_changed_file_runs_only_the_task_that_used_it(self):
        first, _ = self.nonces()
        (self.code / "toy_data.txt").write_text("two")
        again, out = self.nonces()
        self.assertNotEqual(again[0], first[0], "toy_a read the file and ran again")
        self.assertEqual(out[0][0]["text"], "two")
        self.assertEqual(again[1], first[1], "toy_b never opened it and was kept")
        (self.code / "toy_b.py").write_text(textwrap.dedent(TOY_B) + "\n# changed\n")
        third, _ = self.nonces()
        self.assertEqual(third[0], again[0])
        self.assertNotEqual(third[1], again[1], "a change to its own module runs toy_b again")

    def test_other_inputs_and_the_switch_run_everything(self):
        first, _ = self.nonces()
        other, _ = self.nonces(data={**self.data, "payload": b"another firmware"})
        self.assertTrue(all(a != b for a, b in zip(first, other)))
        os.environ["GELUMPE_CACHE"] = "off"
        off, _ = self.nonces()
        self.assertTrue(all(a != b for a, b in zip(first, off)))
        os.environ.pop("GELUMPE_CACHE")
        self.assertEqual(self.nonces()[0], first, "with the cache back on the kept results are there again")

    def test_what_the_main_script_imports_is_not_what_a_worker_used(self):
        # check.py imports every case module; a worker started by spawn would run it again and list them all
        import subprocess
        here = Path(__file__).resolve().parent
        (self.code / "main.py").write_text(textwrap.dedent(f'''
            import sys
            sys.path[:0] = [{str(here)!r}, {str(self.code)!r}]
            import toy_b  # noqa: F401
            import parallel
            if __name__ == "__main__":
                out = parallel.run_tasks([("toy_a", "cases_task", (1,)), ("toy_a", "cases_task", (2,))], {{"payload": b"x"}}, 2, cache="test")
                print(out[0][0]["nonce"])
        '''))

        def nonce():
            run = subprocess.run([sys.executable, str(self.code / "main.py")], capture_output=True, text=True, env=os.environ, timeout=120)
            self.assertEqual(run.returncode, 0, run.stderr)
            return run.stdout.strip()

        first = nonce()
        (self.code / "toy_b.py").write_text(textwrap.dedent(TOY_B) + "\n# changed\n")
        self.assertEqual(nonce(), first, "toy_a never imported toy_b")

    def test_a_task_that_stopped_with_an_exception_is_not_kept(self):
        tasks = [("toy_c", "cases_task", ())]
        for _ in range(2):
            out = parallel.run_tasks(tasks, self.data, 1, cache="test")
            self.assertFalse(out[0][0]["ok"])
        self.assertFalse((self.folder / "cache" / "task").exists() and any((self.folder / "cache" / "task").iterdir()))

    def test_the_card_clock_stands_while_a_task_runs(self):
        _, out = self.nonces(jobs=1)
        self.assertEqual(out[1][0]["clock"], parallel.CARD_CLOCK)
        self.assertNotEqual(fat32.clock(), parallel.CARD_CLOCK, "and runs again after it")


if __name__ == "__main__":
    unittest.main()
