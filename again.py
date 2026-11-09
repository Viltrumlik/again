#!/usr/bin/env python3
"""again - retry a command, with backoff, and nothing else.

The shell answer is a while loop with a sleep in it. It works until you
want a growing delay, or a cap on that delay, or to give up on a real
failure instead of retrying an assertion error twenty times.

    again -- curl -sf https://flaky.example/api
    again --tries 5 --on 7,28 -- curl -sf https://flaky.example/api

`again` exits with the command's own exit code, so it drops into an
existing script without changing what the script means.

Zero dependencies. Python 3.9+.
"""

import argparse
import random
import subprocess
import sys
import time

VERSION = "0.1.0"
EXIT_USAGE = 2


def parse_codes(text):
    codes = set()
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        if not part.lstrip("-").isdigit():
            raise ValueError("exit codes must be numbers: %r" % part)
        codes.add(int(part))
    return codes


def delays(tries, first, factor, cap, jitter, rng=random):
    """Urinishlar orasidagi kutish vaqtlari.

    Jitter sukut bo'yicha yoqilgan: o'nta mashina bir vaqtda yiqilib, bir
    xil kechikishdan keyin qayta urinsa, ular yana bir vaqtda uriladi.
    Tasodifiy tarqatish shuni oldini oladi.
    """
    out = []
    wait = first
    for _ in range(max(0, tries - 1)):
        actual = min(wait, cap)
        if jitter:
            actual = rng.uniform(actual / 2.0, actual)
        out.append(round(actual, 3))
        wait = min(wait * factor, cap)
    return out


def should_retry(code, only, never):
    if code == 0:
        return False
    if never and code in never:
        return False
    if only:
        return code in only
    return True


def run(command, tries, waits, only, never, timeout, say):
    """Buyruqni ishga tushiradi va kerak bo'lsa qaytadan uradi.

    Buyruqning chiqishi to'sib qolinmaydi -- u to'g'ridan-to'g'ri
    terminalga boradi, aks holda `again` ni bor skriptga qo'yib
    bo'lmasdi.
    """
    for attempt in range(1, tries + 1):
        try:
            done = subprocess.run(command, timeout=timeout)
            code = done.returncode
        except subprocess.TimeoutExpired:
            code = 124                      # timeout(1) shu kodni beradi
            say("attempt %d/%d: timed out after %gs" % (attempt, tries, timeout))
        except OSError as e:
            say("cannot run: %s" % e)
            return 127                      # buyruq topilmadi
        if not should_retry(code, only, never):
            if code and attempt > 1:
                say("attempt %d/%d: exit %d, not retrying" % (attempt, tries, code))
            return code
        if attempt == tries:
            say("attempt %d/%d: exit %d, giving up" % (attempt, tries, code))
            return code
        wait = waits[attempt - 1]
        say("attempt %d/%d: exit %d, retrying in %gs" % (attempt, tries, code, wait))
        time.sleep(wait)
    return code


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="again",
        description="Retry a command with backoff.",
        epilog="example: again --tries 5 --on 7,28 -- curl -sf https://example/api")
    p.add_argument("--tries", type=int, default=3, metavar="N",
                   help="how many attempts in total (default 3)")
    p.add_argument("--delay", type=float, default=1.0, metavar="SECONDS",
                   help="wait before the second attempt (default 1)")
    p.add_argument("--factor", type=float, default=2.0, metavar="N",
                   help="multiply the wait by this each time (default 2)")
    p.add_argument("--max-delay", type=float, default=30.0, metavar="SECONDS",
                   help="never wait longer than this (default 30)")
    p.add_argument("--no-jitter", action="store_true",
                   help="use the exact delay instead of a random part of it")
    p.add_argument("--on", metavar="CODES",
                   help="retry only these exit codes, comma separated")
    p.add_argument("--not-on", dest="not_on", metavar="CODES",
                   help="never retry these exit codes")
    p.add_argument("--timeout", type=float, metavar="SECONDS",
                   help="give up on a single attempt after this long")
    p.add_argument("-q", "--quiet", action="store_true")
    p.add_argument("--version", action="version", version="again " + VERSION)
    p.add_argument("command", nargs=argparse.REMAINDER, metavar="-- COMMAND")
    args = p.parse_args(argv)

    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        p.print_help()
        return EXIT_USAGE

    if args.tries < 1:
        print("error: --tries must be at least 1", file=sys.stderr)
        return EXIT_USAGE
    for name, value in (("--delay", args.delay), ("--max-delay", args.max_delay),
                        ("--factor", args.factor)):
        if value <= 0:
            print("error: %s must be positive" % name, file=sys.stderr)
            return EXIT_USAGE
    if args.timeout is not None and args.timeout <= 0:
        print("error: --timeout must be positive", file=sys.stderr)
        return EXIT_USAGE
    try:
        only = parse_codes(args.on)
        never = parse_codes(args.not_on)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return EXIT_USAGE

    def say(message):
        if not args.quiet:
            print("again: " + message, file=sys.stderr)

    waits = delays(args.tries, args.delay, args.factor, args.max_delay,
                   not args.no_jitter)
    try:
        return run(command, args.tries, waits, only, never, args.timeout, say)
    except KeyboardInterrupt:
        say("interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
