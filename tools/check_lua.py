#!/usr/bin/env python3
"""
tools/check_lua.py
==================
Validates block balance (function, if, do, while, repeat vs end, until),
TOC manifest integrity, load order, and luac syntax compilation across aux-addon.
"""

import os
import re
import subprocess
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

def check_blocks(filepath):
    """
    Checks that every block keyword (function, if, do, while, repeat)
    properly pairs with an 'end' or 'until' keyword.
    """
    if not os.path.exists(filepath):
        print(f"  Error: File '{filepath}' not found.")
        return False

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Strip multiline comments
    content = re.sub(r'--\[\[.*?\]\]', '', content, flags=re.DOTALL)
    # Strip single line comments
    content = re.sub(r'--.*', '', content)
    # Strip string literals
    content = re.sub(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'', '""', content)

    stack = []
    lines = content.split('\n')

    for line_idx, line in enumerate(lines, start=1):
        # Match openers: 'function', bare 'if' (not 'elseif'), 'do', 'repeat'
        # Match closers: 'end', 'until'
        for m in re.finditer(r'(?<!else)\bif\b|\b(function|do|repeat|end|until)\b', line):
            t = m.group(0)
            if t in ['function', 'if', 'do']:
                stack.append((t, line_idx))
            elif t == 'repeat':
                stack.append((t, line_idx))
            elif t == 'end':
                if not stack:
                    print(f"  Unmatched 'end' at line {line_idx} in {filepath}")
                    return False
                top_token, top_line = stack.pop()
                if top_token == 'repeat':
                    print(f"  Mismatched 'end' for 'repeat' at line {line_idx} (opened line {top_line}) in {filepath}")
                    return False
            elif t == 'until':
                if not stack:
                    print(f"  Unmatched 'until' at line {line_idx} in {filepath}")
                    return False
                top_token, top_line = stack.pop()
                if top_token != 'repeat':
                    print(f"  Mismatched 'until' for '{top_token}' at line {line_idx} (opened line {top_line}) in {filepath}")
                    return False

    if stack:
        print(f"  Unclosed blocks in {filepath}: {stack}")
        return False
    return True

def verify_toc_integrity():
    """
    Verifies that all files declared in aux-addon.toc exist, that load order
    respects dependencies, and that no orphaned Lua files exist in the tree.
    """
    print("Verifying aux-addon.toc manifest integrity...")
    toc_path = os.path.join(ADDON_DIR, "aux-addon.toc")
    if not os.path.exists(toc_path):
        print("  ❌ aux-addon.toc not found!")
        return False

    with open(toc_path, "r", encoding="utf-8", errors="ignore") as f:
        toc_lines = f.read().splitlines()

    toc_files = []
    for line in toc_lines:
        line = line.strip()
        if line and not line.startswith('#'):
            norm = os.path.normpath(line)
            toc_files.append(norm)

    print(f"  Found {len(toc_files)} files referenced in aux-addon.toc")

    all_exist = True
    for ref in toc_files:
        full = os.path.join(ADDON_DIR, ref)
        if not os.path.exists(full):
            print(f"  ❌ File in TOC missing on disk: {ref}")
            all_exist = False

    # Check for orphaned .lua files
    disk_lua = set()
    for root, _, files in os.walk(ADDON_DIR):
        if "tools" in root or ".git" in root:
            continue
        for file in files:
            if file.endswith('.lua'):
                rel = os.path.normpath(os.path.relpath(os.path.join(root, file), ADDON_DIR))
                disk_lua.add(rel)

    toc_lua_set = set(f for f in toc_files if f.endswith('.lua'))
    orphaned = disk_lua - toc_lua_set
    if orphaned:
        print(f"  ⚠️ Warning: Found {len(orphaned)} orphaned Lua file(s) not in TOC: {orphaned}")
    else:
        print(f"  ✅ 100% of {len(disk_lua)} Lua files on disk registered in TOC")

    # Dependency check: libs/package.lua and libs/T.lua MUST be loaded first
    first_few = toc_files[:3]
    expected_foundational = os.path.normpath(r'libs\package.lua')
    if expected_foundational not in first_few:
        print(f"  ❌ Dependency violation: {expected_foundational} must be loaded at start of TOC!")
        all_exist = False

    return all_exist

def verify_luac_compilation():
    """
    Runs 'luac -p' on all Lua files to verify syntax compilation.
    """
    print("Verifying luac syntax compilation across all Lua files...")
    all_ok = True
    lua_files = []
    for root, _, files in os.walk(ADDON_DIR):
        if "tools" in root or ".git" in root:
            continue
        for f in files:
            if f.endswith('.lua'):
                lua_files.append(os.path.join(root, f))

    try:
        subprocess.run(["luac", "-v"], capture_output=True)
    except FileNotFoundError:
        print("  ⚠️ 'luac' not found in environment PATH; skipping binary compilation check.")
        return True

    for filepath in sorted(lua_files):
        rel = os.path.relpath(filepath, ADDON_DIR)
        res = subprocess.run(["luac", "-p", filepath], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"  ❌ {rel}: Compilation error: {res.stderr.strip()}")
            all_ok = False

    if all_ok:
        print(f"  ✅ All {len(lua_files)} files compiled cleanly with luac")
    return all_ok

def main():
    print("=" * 65)
    print("  aux-addon Lua Syntax, TOC & Block Balance Verification")
    print("=" * 65)

    toc_ok = verify_toc_integrity()
    luac_ok = verify_luac_compilation()

    print("\nChecking Lua block balance across all files...")
    lua_files = []
    for root, _, files in os.walk(ADDON_DIR):
        if "tools" in root or ".git" in root:
            continue
        for f in files:
            if f.endswith('.lua'):
                lua_files.append(os.path.join(root, f))

    blocks_ok = True
    for filepath in sorted(lua_files):
        if not check_blocks(filepath):
            blocks_ok = False

    if blocks_ok:
        print(f"  ✅ All {len(lua_files)} Lua files have balanced syntax blocks!")

    if toc_ok and luac_ok and blocks_ok:
        print("\nAll syntax, TOC, and block balance checks PASSED!")
        sys.exit(0)
    else:
        print("\nVerification checks FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    main()
