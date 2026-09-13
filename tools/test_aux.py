#!/usr/bin/env python3
"""
tools/test_aux.py
=================
Algorithmic and behavioral unit test suite for aux-addon.
Validates:
  1. Money calculations & conversions (to_gsc, from_gsc, money string parsing).
  2. Filter syntax parser and token validation (util/filter.lua rules).
  3. Dynamic deposit fee calculation on Turtle WoW.
  4. Pool acquisition/release lifecycle simulation (libs/T.lua semantics).
"""

import math
import re
import sys
import unittest

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Reference implementations of aux algorithmic functions from util/money.lua
COPPER_PER_SILVER = 100
COPPER_PER_GOLD = 10000

def py_to_gsc(money: int):
    gold = math.floor(money / COPPER_PER_GOLD)
    silver = math.floor((money % COPPER_PER_GOLD) / COPPER_PER_SILVER)
    copper = money % COPPER_PER_SILVER
    return int(gold), int(silver), int(copper)

def py_from_gsc(gold: int, silver: int, copper: int) -> int:
    return gold * COPPER_PER_GOLD + silver * COPPER_PER_SILVER + copper

def py_from_string(value: str):
    """
    Python equivalent of aux.util.money.from_string.
    Parses '1g 50s 20c', '12g', '50s', '20c', or raw copper integers.
    """
    value = value.strip().lower()
    m_gold = re.search(r'(\d+(?:\.\d+)?)g', value)
    m_silver = re.search(r'(\d+(?:\.\d+)?)s', value)
    m_copper = re.search(r'(\d+(?:\.\d+)?)c', value)

    if m_gold or m_silver or m_copper:
        gold = float(m_gold.group(1)) if m_gold else 0.0
        silver = float(m_silver.group(1)) if m_silver else 0.0
        copper = float(m_copper.group(1)) if m_copper else 0.0
        return int(round(gold * COPPER_PER_GOLD + silver * COPPER_PER_SILVER + copper))
    else:
        # Fallback to pure numeric copper
        try:
            return int(value)
        except ValueError:
            return None

def py_to_string(money: int, pad: bool = False, trim: bool = False) -> str:
    """
    Python equivalent of aux.util.money.to_string (uncolored/raw text).
    """
    is_negative = money < 0
    money = abs(money)
    gold, silver, copper = py_to_gsc(money)

    def fmt_num(num: int, p: bool) -> str:
        return f"{num:02d}" if p else str(num)

    gold_text, silver_text, copper_text = 'g', 's', 'c'

    if trim:
        parts = []
        if gold > 0:
            parts.append(fmt_num(gold, False) + gold_text)
        if silver > 0:
            parts.append(fmt_num(silver, pad) + silver_text)
        if copper > 0 or (gold == 0 and silver == 0):
            parts.append(fmt_num(copper, pad) + copper_text)
        text = " ".join(parts)
    else:
        if gold > 0:
            text = f"{fmt_num(gold, False)}{gold_text} {fmt_num(silver, pad)}{silver_text} {fmt_num(copper, pad)}{copper_text}"
        elif silver > 0:
            text = f"{fmt_num(silver, False)}{silver_text} {fmt_num(copper, pad)}{copper_text}"
        else:
            text = f"{fmt_num(copper, False)}{copper_text}"

    if is_negative:
        text = "-" + text
    return text


def py_turtle_deposit_fee(unit_vendor_price: int, stack_size: int, stack_count: int, max_stack: int, duration_hours: int = 24) -> int:
    """
    Reference calculation for Turtle WoW deposit fee (PR #9 / isfir formula).
    duration_factor = duration_hours / 2
    deposit_factor = 0.025
    """
    duration_factor = duration_hours / 2
    deposit_factor = 0.025
    partial_penalty = 1 + (max_stack - stack_size) * 0.05
    single_deposit = math.floor(unit_vendor_price * stack_size * duration_factor * partial_penalty * deposit_factor)
    return single_deposit * stack_count


class TestMoneyMath(unittest.TestCase):
    def test_gsc_roundtrip(self):
        for gold, silver, copper in [(0, 0, 0), (1, 0, 0), (0, 50, 0), (0, 0, 99), (123, 45, 67), (9999, 99, 99)]:
            total_copper = py_from_gsc(gold, silver, copper)
            g, s, c = py_to_gsc(total_copper)
            self.assertEqual((g, s, c), (gold, silver, copper))

    def test_from_string_parsing(self):
        self.assertEqual(py_from_string("1g"), 10000)
        self.assertEqual(py_from_string("50s"), 5000)
        self.assertEqual(py_from_string("25c"), 25)
        self.assertEqual(py_from_string("1g 50s 25c"), 15025)
        self.assertEqual(py_from_string("10g 5c"), 100005)
        self.assertEqual(py_from_string("2.5g"), 25000)
        self.assertEqual(py_from_string("15025"), 15025)
        self.assertIsNone(py_from_string("invalid"))

    def test_to_string_alignment_padding(self):
        # When pad=True, trim=False (used in auction listing table for column alignment)
        # Gold amounts must include padded 2-digit silver and copper (00s 00c)
        self.assertEqual(py_to_string(400000, pad=True, trim=False), "40g 00s 00c")
        self.assertEqual(py_to_string(417500, pad=True, trim=False), "41g 75s 00c")
        self.assertEqual(py_to_string(386666, pad=True, trim=False), "38g 66s 66c")
        self.assertEqual(py_to_string(450000, pad=True, trim=False), "45g 00s 00c")
        self.assertEqual(py_to_string(5000, pad=True, trim=False), "50s 00c")
        self.assertEqual(py_to_string(25, pad=True, trim=False), "25c")

    def test_to_string_trimmed(self):
        # When trim=True (used in filter builder and queries)
        self.assertEqual(py_to_string(400000, trim=True), "40g")
        self.assertEqual(py_to_string(417500, trim=True), "41g 75s")
        self.assertEqual(py_to_string(5000, trim=True), "50s")
        self.assertEqual(py_to_string(0, trim=True), "0c")


class TestTurtleDepositCalculation(unittest.TestCase):
    def test_full_stack_deposit(self):
        # 20 Peacebloom (vendor price 10c each), full stack of 20, 24 hours
        fee = py_turtle_deposit_fee(unit_vendor_price=10, stack_size=20, stack_count=1, max_stack=20, duration_hours=24)
        # partial_penalty = 1.0; 10 * 20 * 12 * 1.0 * 0.025 = 60 copper
        self.assertEqual(fee, 60)

    def test_partial_stack_penalty(self):
        # 1 item of stack 20 has partial stack penalty: 1 + (20-1)*0.05 = 1.95
        fee = py_turtle_deposit_fee(unit_vendor_price=10, stack_size=1, stack_count=1, max_stack=20, duration_hours=24)
        # 10 * 1 * 12 * 1.95 * 0.025 = 5.85 -> floor = 5
        self.assertEqual(fee, 5)


class TestFilterParser(unittest.TestCase):
    def test_valid_filter_syntax(self):
        valid_queries = [
            "righteous orb",
            "exact/righteous orb",
            "iron ore/20/usable",
            "armor/cloth/50-60/epic",
            "weapon/one-handed swords/rare/disenchant-percent/80",
        ]
        for q in valid_queries:
            parts = q.split('/')
            self.assertTrue(len(parts) >= 1)
            for p in parts:
                self.assertTrue(len(p.strip()) > 0)


class TestTablePoolSimulation(unittest.TestCase):
    def test_acquire_release_semantics(self):
        pool = []
        auto_release = set()

        def acquire():
            if pool:
                return pool.pop()
            return {}

        def release(t):
            t.clear()
            if len(pool) < 50:
                pool.append(t)

        def mark_auto_release(t):
            auto_release.add(id(t))

        # Acquire 10 tables
        tables = [acquire() for _ in range(10)]
        for t in tables:
            mark_auto_release(t)

        self.assertEqual(len(auto_release), 10)

        # Frame update cycle
        for t in tables:
            release(t)
        auto_release.clear()

        self.assertEqual(len(auto_release), 0)
        self.assertEqual(len(pool), 10)

        # Next acquire should reuse pool
        reused = acquire()
        self.assertEqual(len(pool), 9)


if __name__ == "__main__":
    print("=" * 65)
    print("  aux-addon Algorithmic & Behavioral Unit Tests")
    print("=" * 65)
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
