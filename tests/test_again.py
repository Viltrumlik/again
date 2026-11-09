"""Buyruqlar Python orqali quriladi -- `sh` Windows'da yo'q."""

import importlib.util
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "again.py")

spec = importlib.util.spec_from_file_location("again", SCRIPT)
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="again-")
        self.counter = os.path.join(self.tmp, "n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def attempts(self):
        try:
            with open(self.counter) as f:
                return len(f.read().split())
        except OSError:
            return 0

    def failing(self, times, then=0, code=7):
        """`times` marta `code` bilan yiqiladi, keyin `then` qaytaradi."""
        body = (
            "import sys\n"
            "p = %r\n"
            "open(p, 'a').write('x ')\n"
            "n = len(open(p).read().split())\n"
            "sys.exit(%d if n <= %d else %d)\n" % (self.counter, code, times, then)
        )
        return [sys.executable, "-c", body]

    def run_cli(self, *args, **kw):
        command = kw.get("command") or self.failing(0)
        return subprocess.run([sys.executable, SCRIPT, *args, "--", *command],
                              capture_output=True, text=True)


class RetryTest(Base):
    def test_a_command_that_works_runs_once(self):
        out = self.run_cli("--tries", "3", command=self.failing(0))
        self.assertEqual(out.returncode, 0)
        self.assertEqual(self.attempts(), 1)

    def test_it_stops_as_soon_as_the_command_succeeds(self):
        out = self.run_cli("--tries", "5", "--delay", "0.01",
                           command=self.failing(2))
        self.assertEqual(out.returncode, 0)
        self.assertEqual(self.attempts(), 3)

    def test_it_gives_up_after_the_last_try(self):
        out = self.run_cli("--tries", "3", "--delay", "0.01",
                           command=self.failing(99))
        self.assertEqual(out.returncode, 7)
        self.assertEqual(self.attempts(), 3)
        self.assertIn("giving up", out.stderr)

    def test_the_commands_exit_code_is_passed_through(self):
        out = self.run_cli("--tries", "1", command=self.failing(99, code=42))
        self.assertEqual(out.returncode, 42)

    def test_one_try_means_no_retry(self):
        self.run_cli("--tries", "1", command=self.failing(99))
        self.assertEqual(self.attempts(), 1)

    def test_only_the_listed_codes_are_retried(self):
        out = self.run_cli("--tries", "4", "--delay", "0.01", "--on", "7",
                           command=self.failing(99, code=1))
        self.assertEqual(out.returncode, 1)
        self.assertEqual(self.attempts(), 1)

    def test_a_listed_code_is_retried(self):
        self.run_cli("--tries", "3", "--delay", "0.01", "--on", "7,28",
                     command=self.failing(99, code=28))
        self.assertEqual(self.attempts(), 3)

    def test_not_on_wins_over_everything(self):
        out = self.run_cli("--tries", "4", "--delay", "0.01", "--not-on", "7",
                           command=self.failing(99, code=7))
        self.assertEqual(out.returncode, 7)
        self.assertEqual(self.attempts(), 1)

    def test_a_command_that_does_not_exist_gives_127(self):
        out = subprocess.run(
            [sys.executable, SCRIPT, "--tries", "2", "--", "no-such-command-xyz"],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 127)
        self.assertIn("cannot run", out.stderr)

    def test_a_hanging_attempt_times_out_and_is_retried(self):
        hang = [sys.executable, "-c",
                "import time,sys; open(%r,'a').write('x '); time.sleep(30)" % self.counter]
        out = self.run_cli("--tries", "2", "--delay", "0.01", "--timeout", "0.5",
                           command=hang)
        self.assertEqual(out.returncode, 124)
        self.assertEqual(self.attempts(), 2)
        self.assertIn("timed out", out.stderr)

    def test_quiet_says_nothing(self):
        out = self.run_cli("--tries", "2", "--delay", "0.01", "--quiet",
                           command=self.failing(99))
        self.assertEqual(out.stderr.strip(), "")


class DelayTest(unittest.TestCase):
    def test_the_wait_grows_and_is_capped(self):
        self.assertEqual(ag.delays(5, 1, 2, 30, jitter=False), [1, 2, 4, 8])
        self.assertEqual(ag.delays(6, 10, 3, 30, jitter=False), [10, 30, 30, 30, 30])

    def test_there_is_one_wait_fewer_than_attempts(self):
        self.assertEqual(len(ag.delays(3, 1, 2, 30, jitter=False)), 2)
        self.assertEqual(ag.delays(1, 1, 2, 30, jitter=False), [])

    def test_jitter_stays_between_half_and_the_full_wait(self):
        rng = random.Random(1)
        for wait, full in zip(ag.delays(6, 4, 2, 100, jitter=True, rng=rng),
                              [4, 8, 16, 32, 64]):
            self.assertGreaterEqual(wait, full / 2.0)
            self.assertLessEqual(wait, full)

    def test_without_jitter_the_wait_is_exact(self):
        self.assertEqual(ag.delays(3, 2.5, 2, 100, jitter=False), [2.5, 5.0])


class ParseTest(unittest.TestCase):
    def test_codes_are_parsed_and_blanks_ignored(self):
        self.assertEqual(ag.parse_codes("7, 28 ,"), {7, 28})
        self.assertEqual(ag.parse_codes(""), set())
        self.assertEqual(ag.parse_codes(None), set())

    def test_nonsense_codes_are_refused(self):
        with self.assertRaises(ValueError):
            ag.parse_codes("7,abc")

    def test_zero_never_retries(self):
        self.assertFalse(ag.should_retry(0, set(), set()))
        self.assertFalse(ag.should_retry(0, {0}, set()))


class UsageTest(Base):
    def run_bare(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args],
                              capture_output=True, text=True)

    def test_no_command_prints_help(self):
        out = self.run_bare()
        self.assertEqual(out.returncode, 2)
        self.assertIn("usage", out.stdout.lower())

    def test_the_separator_is_optional(self):
        out = self.run_bare("--tries", "1", sys.executable, "-c", "pass")
        self.assertEqual(out.returncode, 0)

    def test_impossible_settings_are_refused(self):
        for args in (("--tries", "0"), ("--delay", "0"), ("--factor", "0"),
                     ("--max-delay", "-1"), ("--timeout", "0"), ("--on", "x")):
            out = self.run_bare(*args, "--", sys.executable, "-c", "pass")
            self.assertEqual(out.returncode, 2, args)


if __name__ == "__main__":
    unittest.main()
