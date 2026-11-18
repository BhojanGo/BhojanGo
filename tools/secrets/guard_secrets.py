"""PreToolUse hook (R13): a shell command that names a secrets file must mask its output.

Wired in each machine's (git-ignored) .claude/settings.json:
  {"hooks": {"PreToolUse": [{"matcher": "Bash|PowerShell",
    "hooks": [{"type": "command", "command": "python tools/secrets/guard_secrets.py"}]}]}}

The QA logins, Railway tokens and Stripe keys live in three files outside the repo. A command
that reads one of them and prints what it read put three admin passwords in a tool log once
(R12). So any Bash/PowerShell command naming those files is refused unless its output goes
through tools/secrets/mask.py (pipe into it, or `mask.py run -- ...`). Scripts should use
mask.login()/set_password() and print nothing secret. Exit 2 = refuse, with the reason.
"""
import json
import re
import sys

FILES = re.compile(r"BhojanGo_(QA_Logins|Railway_Tokens|Stripe_Keys)", re.I)
MASKED = re.compile(r"tools[/\\]secrets[/\\]mask\.py")


def verdict(command: str) -> str | None:
    if not FILES.search(command or ""):
        return None
    if MASKED.search(command):
        return None
    return ("This command names a secrets file (QA logins, Railway tokens or Stripe keys) but its output "
            "isn't masked. Pipe it through `python tools/secrets/mask.py`, run it as "
            "`python tools/secrets/mask.py run -- <cmd>`, or use mask.login()/set_password() in a script "
            "that prints nothing secret (docs/PLAYBOOK.md rule 67).")


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    why = verdict((event.get("tool_input") or {}).get("command", ""))
    if why:
        print(why, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
