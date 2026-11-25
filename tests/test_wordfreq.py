"""Tests for the wordfreq package: counting, formatting, and the CLI."""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest

from wordfreq.cli import count_words, format_table, main

ROOT = Path(__file__).resolve().parents[1]


def _run_cli(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def _run_module(args: list[str], stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "wordfreq", *args],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )


# --- count_words -----------------------------------------------------------


def test_count_words_basic_ranking() -> None:
    text = "Apple banana apple, cherry! Banana apple."
    assert count_words(text) == [("apple", 3), ("banana", 2), ("cherry", 1)]


def test_count_words_ties_sorted_alphabetically() -> None:
    assert count_words("pear apple mango") == [("apple", 1), ("mango", 1), ("pear", 1)]


def test_count_words_higher_count_beats_alphabetical_order() -> None:
    assert count_words("zeta zeta alpha") == [("zeta", 2), ("alpha", 1)]


def test_count_words_order_is_independent_of_input_order() -> None:
    assert count_words("b a c a b") == [("a", 2), ("b", 2), ("c", 1)]
    assert count_words("c b a b a") == [("a", 2), ("b", 2), ("c", 1)]


def test_count_words_lowercases_by_default() -> None:
    assert count_words("Apple APPLE apple") == [("apple", 3)]


def test_count_words_ignore_case_false_preserves_case() -> None:
    assert count_words("Apple apple", ignore_case=False) == [("Apple", 1), ("apple", 1)]


def test_count_words_ignore_case_false_counts_case_variants_separately() -> None:
    assert count_words("Apple APPLE apple apple", ignore_case=False) == [
        ("apple", 2),
        ("APPLE", 1),
        ("Apple", 1),
    ]


def test_count_words_uses_ascii_alphanumeric_tokens() -> None:
    words = [word for word, _ in count_words("don't re-use abc123 naïve")]
    assert words == ["abc123", "don", "na", "re", "t", "use", "ve"]


def test_count_words_min_len_filters_short_words() -> None:
    assert count_words("a bb ccc bb", min_len=2) == [("bb", 2), ("ccc", 1)]


def test_count_words_top_limits_results_after_ranking() -> None:
    assert count_words("c b a b a", top=2) == [("a", 2), ("b", 2)]


def test_count_words_top_zero_returns_empty() -> None:
    assert count_words("apple", top=0) == []


def test_count_words_empty_text_returns_empty() -> None:
    assert count_words("") == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"min_len": 0}, "min_len must be >= 1"),
        ({"min_len": -3}, "min_len must be >= 1"),
        ({"top": -1}, "top must be >= 0"),
    ],
)
def test_count_words_rejects_invalid_options(
    kwargs: dict[str, int], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        count_words("apple", **kwargs)


# --- format_table ----------------------------------------------------------


def test_format_table_tsv() -> None:
    assert format_table([("apple", 3), ("banana", 2)]) == "apple\t3\nbanana\t2"


def test_format_table_empty_rows_returns_empty_string() -> None:
    assert format_table([]) == ""


# --- CLI: input sources ----------------------------------------------------


def test_cli_top_and_min_len(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("to be or not to be that is the question", encoding="utf-8")
    rc = main([str(sample), "--min-len", "3", "--top", "2"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.strip().splitlines() == ["not\t1", "question\t1"]


def test_cli_reads_stdin_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("red blue red\n"))
    rc, out, err = _run_cli([], capsys)
    assert rc == 0
    assert out == "red\t2\nblue\t1\n"
    assert err == ""


def test_cli_dash_path_reads_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("one two"))
    rc, out, _ = _run_cli(["-"], capsys)
    assert rc == 0
    assert out == "one\t1\ntwo\t1\n"


# --- CLI: --case-sensitive -------------------------------------------------


def test_cli_lowercases_by_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("Apple apple APPLE", encoding="utf-8")
    rc, out, _ = _run_cli([str(sample)], capsys)
    assert rc == 0
    assert out == "apple\t3\n"


def test_cli_case_sensitive_keeps_original_case(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("Apple apple APPLE", encoding="utf-8")
    rc, out, _ = _run_cli([str(sample), "--case-sensitive"], capsys)
    assert rc == 0
    assert out == "APPLE\t1\nApple\t1\napple\t1\n"


# --- CLI: TSV output -------------------------------------------------------


def test_cli_tsv_output_ends_with_single_newline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("apple banana apple", encoding="utf-8")
    rc, out, _ = _run_cli([str(sample)], capsys)
    assert rc == 0
    assert out == "apple\t2\nbanana\t1\n"


def test_cli_empty_tsv_output_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("!!! ...\n"))
    rc, out, err = _run_cli([], capsys)
    assert rc == 0
    assert out == ""
    assert err == ""


def test_cli_top_zero_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("apple"))
    rc, out, _ = _run_cli(["--top", "0"], capsys)
    assert rc == 0
    assert out == ""


# --- CLI: --json output ----------------------------------------------------


def test_cli_json_output_is_array_with_trailing_newline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("apple banana apple", encoding="utf-8")
    rc, out, _ = _run_cli([str(sample), "--json"], capsys)
    assert rc == 0
    assert out == '[{"word": "apple", "count": 2}, {"word": "banana", "count": 1}]\n'


def test_cli_json_empty_input_prints_empty_array(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    rc, out, _ = _run_cli(["--json"], capsys)
    assert rc == 0
    assert out == "[]\n"


def test_cli_json_respects_top_and_min_len(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("a bb bb cc"))
    rc, out, _ = _run_cli(["--json", "--top", "1", "--min-len", "2"], capsys)
    assert rc == 0
    assert out == '[{"word": "bb", "count": 2}]\n'


# --- CLI: argument validation ----------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["--min-len", "0"],
        ["--min-len", "-1"],
        ["--top", "-1"],
        ["--min-len", "abc"],
        ["--top", "many"],
        ["--no-such-flag"],
    ],
)
def test_cli_invalid_arguments_exit_2_with_stderr(
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("apple"))
    rc, out, err = _run_cli(argv, capsys)
    assert rc == 2
    assert out == ""
    assert err != ""


def test_cli_invalid_arguments_do_not_read_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class _UnreadableStdin(io.StringIO):
        def read(self, size: int | None = -1) -> str:
            msg = "stdin should not be read when arguments are invalid"
            raise AssertionError(msg)

    monkeypatch.setattr(sys, "stdin", _UnreadableStdin("apple"))
    rc, out, err = _run_cli(["--min-len", "0"], capsys)
    assert rc == 2
    assert out == ""
    assert "min_len must be >= 1" in err


def test_cli_help_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    rc, out, _ = _run_cli(["--help"], capsys)
    assert rc == 0
    assert "--case-sensitive" in out


# --- CLI: input errors -----------------------------------------------------


def test_cli_missing_file_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "does-not-exist.txt"
    rc, out, err = _run_cli([str(missing)], capsys)
    assert rc == 2
    assert out == ""
    assert "cannot read" in err
    assert str(missing) in err


def test_cli_directory_path_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, out, err = _run_cli([str(tmp_path)], capsys)
    assert rc == 2
    assert out == ""
    assert err != ""


def test_cli_non_utf8_file_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "binary.txt"
    sample.write_bytes(b"\xff\xfe apple")
    rc, out, err = _run_cli([str(sample)], capsys)
    assert rc == 2
    assert out == ""
    assert "cannot decode" in err


# --- python -m wordfreq ----------------------------------------------------


def test_python_m_wordfreq_reads_stdin_and_prints_tsv() -> None:
    proc = _run_module([], stdin="red blue red\n")
    assert proc.returncode == 0
    assert proc.stdout == "red\t2\nblue\t1\n"
    assert proc.stderr == ""


def test_python_m_wordfreq_json_output_ends_with_newline() -> None:
    proc = _run_module(["--json"], stdin="a b")
    assert proc.returncode == 0
    assert proc.stdout == ('[{"word": "a", "count": 1}, {"word": "b", "count": 1}]\n')


def test_python_m_wordfreq_empty_tsv_writes_nothing() -> None:
    proc = _run_module([], stdin="")
    assert proc.returncode == 0
    assert proc.stdout == ""


def test_python_m_wordfreq_missing_file_exits_2(tmp_path: Path) -> None:
    proc = _run_module([str(tmp_path / "missing.txt")])
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr != ""
