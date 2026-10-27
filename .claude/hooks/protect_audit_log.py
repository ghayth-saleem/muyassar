"""PreToolUse hook: keeps the audit log (logs/*.jsonl) append-only.

The audit log is what we show the judges for the transparency criterion, so
Claude must never rewrite, truncate or delete it. The agents append to it at
runtime; that path does not go through Claude's tools and is unaffected.

Exit 2 blocks the tool call and shows stderr to Claude.
"""
import json
import re
import sys

AUDIT_LOG = re.compile(r"(^|[\\/\s\"'=])logs[\\/][^\\/\s\"']+\.jsonl\b", re.IGNORECASE)

# Shell commands that rewrite or remove a file. Reading the log, copying it
# elsewhere and appending with `>>` or `Add-Content` stay allowed.
DESTRUCTIVE = re.compile(
    r"\b(rm|del|erase|rmdir|mv|move|ren|rename|truncate|shred|"
    r"remove-item|move-item|rename-item|set-content|clear-content|out-file)\b"
    r"|\bsed\b[^|;&]*\s-i",
    re.IGNORECASE,
)
# A single `>` whose target is the log itself.
OVERWRITE = re.compile(
    r"(?<![>\d])>(?!>)\s*[\"']?[^\s\"'|;&]*logs[\\/][^\s\"'|;&]+\.jsonl", re.IGNORECASE
)


def block(reason: str) -> None:
    print(
        f"سجل التدقيق محمي (append-only): {reason}\n"
        "السجل بيتكتب من كود الوكلاء وقت التشغيل فقط. "
        "إذا بدك سجل نظيف لسيناريو جديد، ابدأ ملف جديد باسم مختلف.",
        file=sys.stderr,
    )
    sys.exit(2)


def main() -> None:
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return

    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}

    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if AUDIT_LOG.search(path):
            block(f"{tool} على {path}")

    elif tool in ("Bash", "PowerShell"):
        command = tool_input.get("command", "")
        if AUDIT_LOG.search(command) and (DESTRUCTIVE.search(command) or OVERWRITE.search(command)):
            block(f"أمر بيعدّل أو بيحذف السجل: {command[:120]}")


if __name__ == "__main__":
    main()
