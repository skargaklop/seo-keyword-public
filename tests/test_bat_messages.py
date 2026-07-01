from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_bat_echo_and_prompt_messages_are_english_first_bilingual() -> None:
    bat_files = sorted(PROJECT_ROOT.glob("*.bat"))
    assert bat_files

    offenders: list[str] = []
    for bat_file in bat_files:
        text = bat_file.read_text(encoding="utf-8")
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            lower = line.lower()
            if not (
                lower.startswith("echo ")
                or lower.startswith("set /p ")
            ):
                continue
            if "rem " in lower:
                continue
            if lower.startswith("echo %%"):
                continue
            if not any(ch.isalpha() for ch in line):
                continue
            body = line
            if lower.startswith("echo "):
                body = line[5:].strip()
            elif "=" in line:
                body = line.split("=", 1)[1].strip().strip('"')
            if not any(ch.isalpha() for ch in body):
                continue
            if not any("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in body):
                offenders.append(f"{bat_file.name}:{line_number}: missing English text: {raw_line}")
                continue
            if not any("\u0400" <= ch <= "\u04ff" for ch in body):
                offenders.append(f"{bat_file.name}:{line_number}: missing Russian text: {raw_line}")
                continue
            slash_index = body.find(" / ")
            if slash_index == -1:
                offenders.append(f"{bat_file.name}:{line_number}: missing bilingual separator: {raw_line}")
                continue
            left = body[:slash_index]
            if not any("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in left):
                offenders.append(f"{bat_file.name}:{line_number}: English must be first: {raw_line}")

    assert not offenders, "\n".join(offenders)


def test_cli_print_messages_are_english_first_bilingual() -> None:
    import ast

    root = Path(__file__).resolve().parent.parent

    def _is_cyrillic(ch: str) -> bool:
        return "Ѐ" <= ch <= "ӿ"

    def _is_latin(ch: str) -> bool:
        return "A" <= ch <= "Z" or "a" <= ch <= "z"

    offenders: list[str] = []
    for rel in ("cli/main.py", "cli/pipeline.py", "generate_refresh_token.py"):
        path = root / rel
        if not path.exists():
            continue
        # utf-8-sig strips a leading BOM (generate_refresh_token.py has one) so ast.parse
        # doesn't choke on the non-printable U+FEFF.
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            # only print(...) user-facing calls
            if not (isinstance(node.func, ast.Name) and node.func.id == "print"):
                continue
            # gather string literals from args (skip non-string). Join the constant segments
            # of a plain Str or an f-string (JoinedStr) so interpolations don't fragment the message.
            for arg in node.args:
                chunks: list[str] = []
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    chunks.append(arg.value)
                elif isinstance(arg, ast.JoinedStr):
                    for val in arg.values:
                        if isinstance(val, ast.Constant) and isinstance(val.value, str):
                            chunks.append(val.value)
                msg = "".join(chunks).strip()
                if not msg or not any(c.isalpha() for c in msg):
                    continue
                # Pure URLs / tokens / env-var names carry no alphabetic message body to translate.
                if "://" in msg or msg.startswith("GOOGLE_ADS_"):
                    continue
                # Strip digits/punctuation: if the only alphabetic content left is the product
                # name "seos-cli", this is a language-neutral identifier (e.g. the version print
                # "seos-cli 0.1.0"), not prose — it has no meaningful translation, so skip it.
                alpha_only = "".join(c for c in msg if _is_latin(c) or _is_cyrillic(c))
                if alpha_only.lower() == "seoscli":
                    continue
                if not any(_is_latin(c) for c in msg):
                    continue  # pure-numeric/format strings are fine
                if not any(_is_cyrillic(c) for c in msg) or " / " not in msg:
                    offenders.append(f"{rel}:{node.lineno}: not EN-first bilingual: {msg!r}")

    assert not offenders, "\n".join(offenders)
