"""Remove the QA seed passwords from local test logs.

Maestro records every `-e` value (QA_PASSWORDS among them) in its run logs and
commands.json under ~/.maestro/tests. Replace each password with <redacted>.
Prints counts only.

    python tools/railway/redact_logins.py <logins file> <dir> [<dir> ...]
"""
import os
import sys

logins, dirs = sys.argv[1], sys.argv[2:]
passwords = [r[3] for r in (line.rstrip("\n").split("\t") for line in open(logins, encoding="utf-8"))
             if len(r) == 4 and "@" in r[2] and len(r[3]) >= 12]
changed = scanned = 0
for d in dirs:
    for root, _, files in os.walk(d):
        for name in files:
            path = os.path.join(root, name)
            if name.endswith((".png", ".mp4", ".jpg")) or os.path.getsize(path) > 50_000_000:
                continue
            scanned += 1
            try:
                with open(path, encoding="utf-8", errors="surrogateescape") as f:
                    text = f.read()
            except OSError:
                continue
            new = text
            for p in passwords:
                new = new.replace(p, "<redacted>")
            if new != text:
                with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
                    f.write(new)
                changed += 1
print(f"redacted QA passwords in {changed} of {scanned} files")
