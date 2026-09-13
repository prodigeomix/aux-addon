#!/usr/bin/env python3
"""
tools/run_tests.py
==================
Unified verification and diagnostic test suite runner for aux-addon.
Runs:
  1. Lua Syntax Block Balance & TOC Integrity (check_lua.py)
  2. Strict Lua 5.0 & Upvalue Budget Audit (validate_lua50.py)
  3. Scope & Global Variable Leak Scan (scan_global_leaks.py)
  4. Cross-Module API Resolution & Call-Graph (verify_all_api_calls.py)
  5. Algorithmic & Behavioral Unit Tests (test_aux.py)

Returns exit code 0 if all checks pass, 1 if any check fails.
"""

import os
import subprocess
import sys
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

CHECKS = [
    ("TOC Integrity & Block Balance (check_lua.py)", [sys.executable, os.path.join(SCRIPT_DIR, "check_lua.py")]),
    ("Strict Lua 5.0 & Upvalue Audit (validate_lua50.py)", [sys.executable, os.path.join(SCRIPT_DIR, "validate_lua50.py")]),
    ("Scope & Global Leak Scan (scan_global_leaks.py)", [sys.executable, os.path.join(SCRIPT_DIR, "scan_global_leaks.py")]),
    ("Cross-Module API Call-Graph (verify_all_api_calls.py)", [sys.executable, os.path.join(SCRIPT_DIR, "verify_all_api_calls.py")]),
    ("Algorithmic & Behavioral Unit Tests (test_aux.py)", [sys.executable, os.path.join(SCRIPT_DIR, "test_aux.py")]),
]

def main():
    print("=" * 80)
    print("AUX-ADDON AUTOMATED AUDIT & VERIFICATION SUITE")
    print("Vanilla 1.12.1 / Turtle WoW Patch 1.18.1 Client Standards")
    print("=" * 80)

    total_start = time.time()
    all_passed = True
    results = []

    for name, cmd in CHECKS:
        print(f"\n>>> Running {name}...")
        start_t = time.time()
        res = subprocess.run(cmd, cwd=ADDON_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        duration = time.time() - start_t

        output = (res.stdout or "") + (res.stderr or "")
        lines = [l for l in output.strip().splitlines() if l.strip()]
        for l in lines[-6:]:
            print(f"    {l}")

        passed = (res.returncode == 0) and ("FAILED" not in output)
        if not passed:
            all_passed = False
            results.append((name, "FAIL", duration))
            print(f"    --> [FAIL] Exit code: {res.returncode}")
        else:
            results.append((name, "PASS", duration))
            print(f"    --> [PASS] ({duration:.2f}s)")

    print("\n" + "=" * 80)
    print("SUITE EXECUTION SUMMARY")
    print("=" * 80)
    for name, status, duration in results:
        indicator = "[PASS]" if status == "PASS" else "[FAIL]"
        print(f"  {indicator:<8} {name:<55} ({duration:.2f}s)")

    total_time = time.time() - total_start
    print("-" * 80)
    if all_passed:
        print(f"OVERALL RESULT: ALL {len(CHECKS)} AUDIT CHECKS PASSED (Total time: {total_time:.2f}s)")
        print("=" * 80)
        sys.exit(0)
    else:
        print(f"OVERALL RESULT: SOME AUDIT CHECKS FLAGGED ISSUES (Total time: {total_time:.2f}s)")
        print("=" * 80)
        sys.exit(1)

if __name__ == "__main__":
    main()
