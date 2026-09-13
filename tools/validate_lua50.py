#!/usr/bin/env python3
"""
Lua 5.0 and WoW 1.12 / Turtle WoW 1.18.1 Compatibility Validator for aux-addon.
Scans .lua files for post-Lua 5.0 syntax, forbidden APIs, and closure upvalue budgets.
Adapted specifically for aux-addon's architecture (permitting aux.select and object:select).
"""

import os
import re
import subprocess
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Banned patterns in strict Lua 5.0 / Vanilla WoW 1.12.1
BANNED_PATTERNS = [
    (r'(?<![A-Za-z0-9_])#\s*[A-Za-z0-9_\{\(\"\']', "Length operator '#' (Lua 5.1+). Use 'table.getn(t)', 'getn(t)', or 'string.len(s)'."),
    (r'(?<![A-Za-z0-9_])%\s*[A-Za-z0-9_\{\(\"\']', "Modulo operator '%' (Lua 5.1+). Use 'math.mod(a, b)' or 'mod(a, b)'."),
    (r'(?<![A-Za-z0-9_])//(?![A-Za-z0-9_])', "Integer division operator '//' (Lua 5.3+). Use 'math.floor(a / b)'."),
    (r'\bgoto\s+[A-Za-z0-9_]+', "'goto' statement (Lua 5.2+)."),
    (r'::[A-Za-z0-9_]+::', "Label marker '::label::' (Lua 5.2+)."),
    (r'\bstring\.match\b', "'string.match' (Lua 5.1+). Use 'string.find' with capture indices."),
    (r'\bstring\.gmatch\b', "'string.gmatch' (Lua 5.1+). Use 'string.gfind'."),
    (r'\btable\.unpack\b', "'table.unpack' (Lua 5.1+). Use global 'unpack()'."),
    (r'\btable\.pack\b', "'table.pack' (Lua 5.1+). Construct a table with { n = arg.n, unpack(arg) }."),
    # Only flag bare global select(...) calls, NOT aux.select(...) or obj:select(...)
    (r'(?<![\.:A-Za-z0-9_])\bselect\s*\(', "'select()' global (Lua 5.1+). Index into 'arg' table or use 'aux.select()'."),
    (r'\bmath\.huge\b', "'math.huge' (Lua 5.1+). Use '1/0' or 'aux.huge'."),
    (r'\bhooksecurefunc\b', "'hooksecurefunc' (WoW 2.0+). Use classic function detouring."),
    (r':HookScript\b', "':HookScript' (WoW 2.0+). Use standard 1.12 hook assignment."),
    (r'\bC_[A-Za-z0-9_]+\b', "Modern WoW API namespace 'C_*' (WoW 6.0+ / Retail). Use Vanilla globals."),
]

def strip_comments_and_strings(code):
    """
    Strips single line comments (-- ...) and string literals from Lua code
    to prevent false positives inside string literals or documentation.
    """
    lines = code.split('\n')
    cleaned_lines = []
    for line in lines:
        comment_idx = line.find('--')
        if comment_idx != -1:
            line = line[:comment_idx]
        line = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', line)
        line = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", line)
        cleaned_lines.append(line)
    return cleaned_lines

def check_upvalues(filepath, max_allowed=30):
    """
    Uses 'luac -l -p' to inspect closure upvalue counts.
    Lua 5.0 client engine has a hard limit of 32 upvalues per closure.
    """
    violations = []
    try:
        res = subprocess.run(["luac", "-l", "-p", filepath], capture_output=True, text=True)
        if res.returncode != 0:
            violations.append((0, res.stderr.strip()[:100], "luac compilation failed"))
            return violations

        lines = res.stdout.split('\n')
        current_fn = None
        for line in lines:
            m = re.match(r'function <.+?:(\d+),(\d+)>', line)
            if m:
                current_fn = (int(m.group(1)), int(m.group(2)))
            m_uv = re.search(r'(\d+)\s+upvalues', line)
            if m_uv and current_fn:
                uv_count = int(m_uv.group(1))
                if uv_count > max_allowed:
                    violations.append((
                        current_fn[0],
                        f"function (lines {current_fn[0]}-{current_fn[1]})",
                        f"Too many upvalues: {uv_count} (Lua 5.0 limit is 32, max allowed is {max_allowed})"
                    ))
                current_fn = None
    except FileNotFoundError:
        pass
    return violations

def validate_file(filepath):
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' does not exist.")
        return False

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    cleaned_lines = strip_comments_and_strings(content)
    violations = []

    for line_num, line in enumerate(cleaned_lines, start=1):
        for pattern, description in BANNED_PATTERNS:
            if re.search(pattern, line):
                original_line = content.split('\n')[line_num - 1].strip()
                violations.append((line_num, original_line, description))

    uv_violations = check_upvalues(filepath, max_allowed=30)
    violations.extend(uv_violations)

    rel = os.path.relpath(filepath, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if violations:
        print(f"❌ {rel}: {len(violations)} compatibility violation(s):")
        for line_num, code_snippet, desc in violations:
            print(f"    Line {line_num}: {desc}")
            print(f"      Code: {code_snippet}")
        return False
    else:
        print(f"  ✅ {rel} (Lua 5.0 clean)")
        return True

def scan_directory(dir_path):
    all_passed = True
    lua_files = []
    for root, _, files in os.walk(dir_path):
        if "tools" in root or ".git" in root:
            continue
        for file in files:
            if file.endswith('.lua'):
                lua_files.append(os.path.join(root, file))

    print(f"Auditing {len(lua_files)} Lua files for strict Lua 5.0 compatibility...")
    for filepath in sorted(lua_files):
        if not validate_file(filepath):
            all_passed = False
    return all_passed

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    addon_dir = os.path.abspath(os.path.join(script_dir, ".."))
    target = sys.argv[1] if len(sys.argv) > 1 else addon_dir

    if os.path.isdir(target):
        success = scan_directory(target)
    else:
        success = validate_file(target)

    sys.exit(0 if success else 1)
