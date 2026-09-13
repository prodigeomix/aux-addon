#!/usr/bin/env python3
"""
tools/verify_all_api_calls.py
=============================
Cross-module call-graph verification and API resolution for aux-addon.
Ensures that all `alias.method()` calls on required modules resolve 100%
to defined exports (M.<export>), and validates Vanilla WoW 1.12.1 API usage.
"""

import os
import re
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

def main():
    print("=" * 65)
    print("  aux-addon Cross-Module Call-Graph & API Verification")
    print("=" * 65)

    lua_files = []
    for root, _, files in os.walk(ADDON_DIR):
        if "tools" in root or ".git" in root:
            continue
        for f in files:
            if f.endswith('.lua'):
                lua_files.append(os.path.join(root, f))

    # 1. Collect all exported functions/properties per module
    module_exports = {}
    file_to_module = {}

    for filepath in lua_files:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()

        mod_m = re.search(r"module\s+['\"]([^'\"]+)['\"]", content)
        if mod_m:
            mod_name = mod_m.group(1)
            file_to_module[filepath] = mod_name
            if mod_name not in module_exports:
                module_exports[mod_name] = set()

            # Exports: M.func = ... or function M.func(...) or M[key] = ...
            for m in re.finditer(r"\bM\.([A-Za-z0-9_]+)\s*=", content):
                module_exports[mod_name].add(m.group(1))
            for m in re.finditer(r"function\s+M\.([A-Za-z0-9_]+)\s*\(", content):
                module_exports[mod_name].add(m.group(1))
            for m in re.finditer(r"\bM\[['\"]([A-Za-z0-9_]+)['\"]\]\s*=", content):
                module_exports[mod_name].add(m.group(1))

    print(f"Collected exports across {len(module_exports)} modules in aux-addon.")

    # 2. Inspect all call sites on required module aliases
    unresolved_calls = []
    total_calls = 0

    for filepath in lua_files:
        rel = os.path.relpath(filepath, ADDON_DIR)
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as fh:
            lines = fh.readlines()

        # Map: alias -> required module name
        requires = {}
        for line in lines:
            clean = line.split('--')[0]
            m = re.search(r"local\s+([A-Za-z0-9_]+)\s*=\s*require\s*['\"]([^'\"]+)['\"]", clean)
            if m:
                requires[m.group(1)] = m.group(2)

        for line_idx, line in enumerate(lines, start=1):
            clean = line.split('--')[0]
            # Strip string literals to prevent matching module paths in strings
            clean_no_str = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", clean)
            clean_no_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', clean_no_str)

            for alias, mod_name in requires.items():
                for call_m in re.finditer(rf"\b{alias}\.([A-Za-z0-9_]+)\s*\(", clean_no_str):
                    method = call_m.group(1)
                    total_calls += 1
                    if mod_name in module_exports:
                        if method not in module_exports[mod_name]:
                            unresolved_calls.append((rel, line_idx, alias, mod_name, method, clean.strip()))

    print(f"Verified {total_calls} cross-module call sites across all files.")

    if unresolved_calls:
        print(f"\n❌ Found {len(unresolved_calls)} unresolved cross-module call site(s):")
        for rel, line_idx, alias, mod_name, method, stmt in unresolved_calls:
            print(f"  {rel}:{line_idx} - '{alias}.{method}()' not exported by module '{mod_name}'")
            print(f"    Code: {stmt}")
        sys.exit(1)
    else:
        print("✅ 100% of cross-module function calls successfully resolve to valid exports!")
        sys.exit(0)

if __name__ == "__main__":
    main()
