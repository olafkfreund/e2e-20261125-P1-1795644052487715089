"""Command-line entry point and word frequency helpers for wordfreq."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence

_WORD_PATTERN = re.compile(r"[A-Za-z0-9]+")


def _validate_options(min_len: int, top: int | None) -> None:
    """Raise `ValueError` when the word filters are out of range."""
    if min_len < 1:
        msg = "min_len must be >= 1"
        raise ValueError(msg)
    if top is not None and top < 0:
        msg = "top must be >= 0"
        raise ValueError(msg)


def count_words(
    text: str,
    *,
    min_len: int = 1,
    ignore_case: bool = True,
    top: int | None = None,
) -> list[tuple[str, int]]:
    """Count word occurrences in *text* and return `(word, count)` pairs.

    Words are runs of ASCII letters and digits. Results are ordered by
    descending count, then alphabetically, so output is deterministic.
    """
    _validate_options(min_len, top)
    words = _WORD_PATTERN.findall(text)
    if ignore_case:
        words = [word.lower() for word in words]
    counts = Counter(word for word in words if len(word) >= min_len)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    if top is not None:
        ranked = ranked[:top]
    return ranked


def format_table(rows: Sequence[tuple[str, int]]) -> str:
    """Format `(word, count)` pairs as tab-separated lines."""
    return "\n".join(f"{word}\t{count}" for word, count in rows)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wordfreq",
        description="Deterministically count and rank words in text.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="-",
        help="file to read; '-' or omitted reads from stdin",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        help="show only the N most frequent words",
    )
    parser.add_argument(
        "--min-len",
        type=int,
        default=1,
        help="ignore words shorter than N characters (default: 1)",
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="count words without lowercasing them",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print a JSON array of {word, count} objects",
    )
    return parser


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _fail(message: str) -> int:
    sys.stderr.write(f"wordfreq: error: {message}\n")
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    """Run the wordfreq CLI and return the process exit code."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse exits on usage errors (code 2, message already on stderr)
        # and on --help (code 0); report the code instead of exiting.
        return exc.code if isinstance(exc.code, int) else 2

    try:
        _validate_options(args.min_len, args.top)
    except ValueError as exc:
        return _fail(str(exc))

    source = "stdin" if args.path == "-" else args.path
    try:
        text = _read_input(args.path)
    except OSError as exc:
        return _fail(f"cannot read {source}: {exc.strerror or exc}")
    except UnicodeDecodeError as exc:
        return _fail(f"cannot decode {source} as UTF-8: {exc}")

    rows = count_words(
        text,
        min_len=args.min_len,
        ignore_case=not args.case_sensitive,
        top=args.top,
    )
    if args.json:
        payload = [{"word": word, "count": count} for word, count in rows]
        sys.stdout.write(json.dumps(payload) + "\n")
    else:
        table = format_table(rows)
        if table:
            sys.stdout.write(table + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
