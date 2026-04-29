#!/usr/bin/env python3
"""
xv6 Kernel Debugging Assistant
Usage:
    python3 debug.py                          # read panic from stdin
    python3 debug.py panic.txt                # read panic from file
    python3 debug.py panic.txt extra.c foo.c  # include extra source files
    make qemu 2>&1 | python3 debug.py         # pipe QEMU output

Run from inside your xv6 directory so source files can be found.
Set ANTHROPIC_API_KEY environment variable before running.
"""

import sys
import os
import re
import subprocess

# Core xv6 source files always sent for context
CORE_FILES = [
    "syscall.h", "user.h", "usys.S",
    "sysproc.c", "syscall.c"
]

SYSTEM_PROMPT = """You are an expert in xv6 kernel development on x86_64.
You help diagnose kernel panics, triple faults, compiler errors, and runtime bugs.
When given kernel output and source files, you:
1. Identify the root cause clearly and concisely
2. Explain what the error means in the context of xv6
3. Point to the exact file and line number if possible
4. Suggest a specific fix with code
Keep responses focused and practical."""


def get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("Error: ANTHROPIC_API_KEY environment variable not set.")
        print("Run: export ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)
    return key

def read_panic_input(panic_file=None):
    if panic_file:
        try:
            with open(panic_file, "r") as f:
                return f.read()
        except FileNotFoundError:
            print(f"Error: file '{panic_file}' not found.")
            sys.exit(1)
    else:
        print("Paste your kernel panic/error output. Type 'END' on a new line when done:")
        lines = []
        for line in sys.stdin:
            if line.strip() == "END":
                break
            lines.append(line)
        return "".join(lines)

def resolve_addresses(error_text):
    """Use addr2line to resolve stack trace addresses to source filenames."""
    files = set()
    if not os.path.exists("kernel"):
        return files
    addresses = re.findall(r'ffff[0-9a-f]+', error_text)
    for addr in addresses:
        try:
            result = subprocess.run(
                ["addr2line", "-e", "kernel", addr],
                capture_output=True, text=True, timeout=5
            )
            if ":" in result.stdout:
                filename = result.stdout.split(":")[0].strip()
                filename = os.path.basename(filename)
                if os.path.exists(filename) and filename.endswith(".c"):
                    files.add(filename)
        except Exception:
            pass
    return files


def read_source_files(extra_files=None):
    """Read core xv6 source files plus any extras passed by user or resolved from stack trace."""
    to_read = list(CORE_FILES)

    if extra_files:
        for f in extra_files:
            if f not in to_read:
                to_read.append(f)

    sources = []
    for f in to_read:
        if os.path.exists(f):
            with open(f, "r") as fh:
                content = fh.read()
            sources.append(f"=== {f} ===\n{content}")
        else:
            sources.append(f"=== {f} === (not found in current directory)")

    return "\n\n".join(sources)


def ask_claude(error_text, sources, api_key):
    try:
        import requests
    except ImportError:
        print("Error: 'requests' library not installed. Run: pip3 install requests")
        sys.exit(1)

    full_prompt = f"""Here is my xv6 kernel panic or error output:

    {error_text}

Here are the relevant xv6 source files:

    {sources}

Please identify the bug, explain what caused it, and suggest a specific fix."""

    url = "https://api.anthropic.com/v1/messages"
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 5000,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": full_prompt}]
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()["content"][0]["text"]
    except requests.exceptions.HTTPError as e:
        print(f"API error {e.response.status_code}: {e.response.text}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        sys.exit(1)


def main():
    api_key = get_api_key()

    # Parse arguments:
    # First arg (if it ends in .txt or exists as a non-.c file) = panic file
    # Remaining args = extra source files to include
    panic_file = None
    extra_files = []

    args = sys.argv[1:]
    if args and (args[0].endswith(".txt") or (os.path.exists(args[0]) and not args[0].endswith(".c"))):
        panic_file = args[0]
        extra_files = args[1:]
    else:
        extra_files = args

    # Read the panic/error input
    error_text = read_panic_input(panic_file)
    if not error_text.strip():
        print("Error: no input provided.")
        sys.exit(1)

    # Resolve stack addresses to filenames and add those files too
    resolved = resolve_addresses(error_text)
    for f in resolved:
        if f not in extra_files and f not in CORE_FILES:
            extra_files.append(f)
            print(f"Auto-detected source file from stack trace: {f}")

    # Read all source files
    sources = read_source_files(extra_files)

    print("\n--- Sending to Claude for analysis ---\n")
    response = ask_claude(error_text, sources, api_key)
    print(response)
    print("\n--- End of analysis ---\n")


if __name__ == "__main__":
    main()
