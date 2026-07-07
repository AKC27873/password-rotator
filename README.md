# rotate_password.py

Generate cryptographically strong random passwords and apply them to Linux user
accounts — either a single user, or a whole batch of users listed in a text file.
Each user gets a unique password, and the results are printed to the screen so
they can be handed out (and then changed).

## Features

- Uses Python's `secrets` module (cryptographically secure) — never `random`.
- Single-user mode (`--user`) or batch mode (`--file`).
- A **unique** password per user in batch mode.
- Guarantees at least one character from every selected character class.
- Applies passwords via `chpasswd` reading from stdin, so passwords never appear
  in the process list (`ps` / `argv`).
- Batch mode is resilient: a missing user or a failed update is reported and the
  run continues with the remaining users.
- `--no-apply` dry-run mode for generating passwords without touching any account.

## Requirements

- Python 3.6+
- A Linux system with the `chpasswd` and `id` utilities (standard on virtually
  all distributions).
- Root privileges (`sudo`) to actually change account passwords.

## Installation

```bash
chmod +x rotate_password.py
```

Optionally place it on your `PATH`:

```bash
sudo cp rotate_password.py /usr/local/sbin/rotate-password
```

## Usage

```
rotate_password.py (-u USER | -f FILE) [-l LENGTH] [-c CHARSET]
                   [--custom-chars CHARS] [--exclude-ambiguous] [--no-apply]
```

Exactly one of `-u/--user` or `-f/--file` is required.

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `-u`, `--user` | *(one of -u/-f required)* | A single target Linux username. |
| `-f`, `--file` | *(one of -u/-f required)* | Path to a text file listing usernames (one per line). |
| `-l`, `--length` | `24` | Password length. |
| `-c`, `--charset` | `lower,upper,digits,symbols` | Comma-separated character classes to draw from. Valid classes: `lower`, `upper`, `digits`, `symbols`. |
| `--custom-chars` | *(none)* | Use this explicit set of characters instead of the `--charset` classes. |
| `--exclude-ambiguous` | off | Remove visually confusable characters (`O 0 o I l 1 |` etc.). |
| `--no-apply` | off | Only generate and print passwords; do **not** change any account. Does not require root. |

## User file format

- One username per line.
- Blank lines are ignored.
- Lines beginning with `#` are treated as comments and ignored.
- Duplicate usernames are automatically skipped, so no account is rotated twice.

Example `users.txt`:

```
# Engineering team
alice
bob
carol

# Ops team
dave
```

## Examples

Rotate a single user's password to 32 characters:

```bash
sudo python3 rotate_password.py -u alice -l 32
```

Rotate everyone listed in a file, using all character classes:

```bash
sudo python3 rotate_password.py -f users.txt
```

Dry run for a whole file — generate and print, change nothing (no root needed):

```bash
python3 rotate_password.py -f users.txt --no-apply
```

A 16-character alphanumeric password with ambiguous characters removed:

```bash
sudo python3 rotate_password.py -u bob -l 16 -c lower,upper,digits --exclude-ambiguous
```

## Example output

```
USER    PASSWORD
-----   --------------------
alice   vMGi>{Rq*1N2wr]d
bob     [ghB[?k=Hp{E-4Fq
carol   M7P-MnZ+o}O+Y.Z0
dave    5m+2[BOWepNMs,Hg

4 updated, 0 failed/skipped, 4 total.
```

If a user cannot be updated, that row shows the reason and the run continues:

```
USER      PASSWORD
-------   --------------------
alice     vMGi>{Rq*1N2wr]d
ghost     <SKIPPED (user does not exist)>

1 updated, 1 failed/skipped, 2 total.
```

## Exit behavior

The script exits **non-zero** when:

- `--length` is less than 1.
- `--length` is too short to include one character from every selected class.
- An unknown character class is passed to `--charset`.
- The resulting character pool is empty.
- The apply step is requested without root privileges.
- The user file cannot be read or contains no usernames.
- In batch mode, one or more users were skipped or failed (the rest still get
  rotated; the non-zero exit signals that not everything succeeded).

## Security notes

- **Screen / scrollback exposure.** Passwords are printed to stdout by design.
  They may end up in terminal scrollback, terminal logging, or your shell history
  if pasted into another command. Treat the output as sensitive and clear it once
  the passwords have been delivered. In batch mode consider redirecting output to
  a file with restrictive permissions (e.g. `umask 077`) instead of leaving it on
  screen.
- **Delivery.** Hand each password to its user over a secure channel and have them
  change it at first login.
- **Privileges.** Only root can change other users' passwords, which is why the
  apply step checks `euid == 0`.

## License

Provided as-is, without warranty. Adapt freely for your environment.
