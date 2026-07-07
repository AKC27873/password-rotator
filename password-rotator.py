#!/usr/bin/env python3
"""
rotate_password.py — Generate strong random passwords and apply them to Linux
user accounts, either for a single user or for a batch of users listed in a file.

Applying a new password to an account requires root privileges (run with sudo).
Use --no-apply to only generate/print without touching any account.
"""

import argparse
import os
import secrets
import string
import subprocess
import sys


# Character class definitions
CHAR_CLASSES = {
    "lower": string.ascii_lowercase,
    "upper": string.ascii_uppercase,
    "digits": string.digits,
    "symbols": "!@#$%^&*()-_=+[]{};:,.<>?",
}

# Visually confusable characters, removed when --exclude-ambiguous is set
AMBIGUOUS = set("O0oIl1|`'\"{}[]()/\\")


def build_pool(charset_arg, custom_chars, exclude_ambiguous):
    """Return (pool_string, classes_dict). classes_dict is None for custom sets."""
    if custom_chars:
        pool = custom_chars
        classes = None
    else:
        selected = [c.strip() for c in charset_arg.split(",") if c.strip()]
        unknown = [c for c in selected if c not in CHAR_CLASSES]
        if unknown:
            sys.exit(
                f"Unknown character class(es): {', '.join(unknown)}. "
                f"Valid classes: {', '.join(CHAR_CLASSES)}"
            )
        classes = {c: CHAR_CLASSES[c] for c in selected}
        pool = "".join(classes.values())

    if exclude_ambiguous:
        pool = "".join(ch for ch in pool if ch not in AMBIGUOUS)
        if classes:
            classes = {
                k: "".join(ch for ch in v if ch not in AMBIGUOUS)
                for k, v in classes.items()
            }
            # Drop any class that became empty
            classes = {k: v for k, v in classes.items() if v}

    # Deduplicate while preserving order
    pool = "".join(dict.fromkeys(pool))
    if not pool:
        sys.exit("Character pool is empty after applying the given options.")
    return pool, classes


def generate_password(length, pool, classes):
    """Generate a password, guaranteeing at least one char from each class."""
    if classes and length < len(classes):
        sys.exit(
            f"Length {length} is too short to include all "
            f"{len(classes)} character classes."
        )

    if classes:
        # Seed one character from each required class, fill the rest from pool
        chars = [secrets.choice(cls_chars) for cls_chars in classes.values()]
        chars += [secrets.choice(pool) for _ in range(length - len(chars))]
        # Cryptographically secure Fisher-Yates shuffle
        for i in range(len(chars) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            chars[i], chars[j] = chars[j], chars[i]
        return "".join(chars)

    return "".join(secrets.choice(pool) for _ in range(length))


def read_user_file(path):
    """Read usernames from a file: one per line, blanks and '#' comments ignored."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        sys.exit(f"Could not read user file '{path}': {exc}")

    users = []
    seen = set()
    for raw in lines:
        name = raw.strip()
        if not name or name.startswith("#"):
            continue
        if name in seen:
            continue  # skip duplicates so we don't rotate the same user twice
        seen.add(name)
        users.append(name)

    if not users:
        sys.exit(f"No usernames found in '{path}'.")
    return users


def user_exists(username):
    result = subprocess.run(["id", "--", username], capture_output=True)
    return result.returncode == 0


def set_password(username, password):
    """Apply the password via chpasswd. Returns (ok, error_message)."""
    proc = subprocess.run(
        ["chpasswd"],
        input=f"{username}:{password}",
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return False, proc.stderr.strip() or "unknown error"
    return True, ""


class HelpfulParser(argparse.ArgumentParser):
    """Show the full help menu (not just the usage line) on any usage error."""

    def error(self, message):
        self.print_help(sys.stderr)
        self.exit(2, f"\nerror: {message}\n")


def main():
    parser = HelpfulParser(
        description="Generate strong passwords and apply them to Linux users.",
        epilog="Examples:\n"
               "  sudo %(prog)s -u alice -l 32\n"
               "  sudo %(prog)s -f users.txt\n"
               "  %(prog)s -u alice --no-apply\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("-u", "--user", help="A single target Linux username.")
    target.add_argument(
        "-f", "--file",
        help="Path to a text file with one username per line "
             "(blank lines and '#' comments are ignored).",
    )
    parser.add_argument(
        "-l", "--length", type=int, default=24,
        help="Password length (default: 24).",
    )
    parser.add_argument(
        "-c", "--charset", default="lower,upper,digits,symbols",
        help="Comma-separated character classes: lower, upper, digits, symbols "
             "(default: all four).",
    )
    parser.add_argument(
        "--custom-chars", default=None,
        help="Use this explicit set of characters instead of --charset classes.",
    )
    parser.add_argument(
        "--exclude-ambiguous", action="store_true",
        help="Remove visually ambiguous characters (O, 0, l, 1, etc.).",
    )
    parser.add_argument(
        "--no-apply", action="store_true",
        help="Only generate and print; do not change any account password.",
    )
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    if args.length < 1:
        sys.exit("Length must be at least 1.")

    pool, classes = build_pool(
        args.charset, args.custom_chars, args.exclude_ambiguous
    )

    users = [args.user] if args.user else read_user_file(args.file)

    applying = not args.no_apply
    if applying and os.geteuid() != 0:
        sys.exit(
            "Changing an account password requires root. "
            "Re-run with sudo, or pass --no-apply to just generate passwords."
        )

    results = []   # (username, password_or_None, status_message)
    failures = 0
    for username in users:
        password = generate_password(args.length, pool, classes)
        if applying:
            if not user_exists(username):
                results.append(
                    (username, None, "SKIPPED (user does not exist)"))
                failures += 1
                continue
            ok, err = set_password(username, password)
            if not ok:
                results.append((username, None, f"FAILED ({err})"))
                failures += 1
                continue
            results.append((username, password, "updated"))
        else:
            results.append((username, password, "generated (not applied)"))

    # Print results in an aligned table
    width = max(len(u) for u, _, _ in results)
    print(f"{'USER'.ljust(width)}   PASSWORD")
    print(f"{'-' * width}   {'-' * 20}")
    for username, password, status in results:
        if password is None:
            print(f"{username.ljust(width)}   <{status}>")
        else:
            print(f"{username.ljust(width)}   {password}")

    if applying and len(users) > 1:
        ok_count = len(users) - failures
        print(f"\n{ok_count} updated, {failures} failed/skipped, "
              f"{len(users)} total.")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
