<h1 align="center">again</h1>

<p align="center">
  <b>Retry a command with backoff, and nothing else.</b>
</p>

<p align="center">
  <a href="https://github.com/Viltrumlik/again/actions/workflows/ci.yml"><img src="https://github.com/Viltrumlik/again/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/dependencies-0-brightgreen" alt="Zero dependencies">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT"></a>
</p>

The shell answer is a `while` loop with a `sleep` in it. It works until you want a growing delay, or a cap on that delay, or to stop retrying an assertion error twenty times.

```bash
again -- curl -sf https://flaky.example/api
again --tries 5 -- pytest tests/integration
```

```console
again: attempt 1/3: exit 7, retrying in 0.8s
again: attempt 2/3: exit 7, retrying in 1.7s
again: attempt 3/3: exit 7, giving up
```

## It stays out of the way

**It exits with the command's own exit code.** Not its own. So you can put `again --` in front of a line in an existing script and the script still means what it meant.

**The command's output is not captured.** stdout and stderr go straight through to your terminal, in real time. Only `again`'s own notes go to stderr, and `--quiet` silences those.

## Retry the right failures

A network blip deserves another go. A failing assertion does not — retrying it four times just makes the build four times slower before it fails anyway.

```bash
again --on 7,28 -- curl -sf https://example/api   # connect and timeout only
again --not-on 1 -- ./deploy.sh                   # anything but a plain failure
```

## Options

| | |
|---|---|
| `--tries N` | attempts in total (default 3) |
| `--delay S` | wait before the second attempt (default 1) |
| `--factor N` | multiply the wait each time (default 2) |
| `--max-delay S` | never wait longer than this (default 30) |
| `--timeout S` | give up on one attempt after this long, and retry it |
| `--on CODES` / `--not-on CODES` | which exit codes are worth retrying |
| `--no-jitter` | use the exact delay |
| `-q, --quiet` | no notes |

A hung attempt that hits `--timeout` reports `124`, the same code `timeout(1)` uses. A command that cannot be run at all reports `127`.

## Jitter is on by default

If ten machines fail at the same second and all wait exactly two seconds, they retry at the same second too, and collide again. Each wait is a random amount between half the delay and the full delay, so they spread out.

`--no-jitter` turns it off when you want reproducible timing.

## Install

```bash
pipx install git+https://github.com/Viltrumlik/again
```

Or take the file:

```bash
curl -O https://raw.githubusercontent.com/Viltrumlik/again/main/again.py
python3 again.py -- echo hello
```

## Development

```bash
python3 -m unittest discover -s tests -v
```

21 tests. The test commands are built from `sys.executable` rather than `sh`, so the suite runs on Windows too. CI covers Ubuntu, macOS and Windows with Python 3.9 through 3.13.

## License

[MIT](LICENSE) © Alisher Muhammadaliyev ([@Viltrumlik](https://github.com/Viltrumlik))
