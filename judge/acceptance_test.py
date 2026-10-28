"""The judge: acceptance tests for all five rules in spec.md.

GIVEN CODE. Do not change it. It sits outside every workspace, so the agent can neither
read it nor edit it. judge() in agent/reflexion.py runs it against a workspace.
"""

import unittest
from datetime import date

from discounts import apply_discount

NOV_1 = date(2026, 11, 1)


class TestSpec(unittest.TestCase):
    def test_rule_1_empty_code_leaves_total(self):
        self.assertEqual(apply_discount(2500, "", NOV_1), 2500)

    def test_rule_2_codes_ignore_case(self):
        self.assertEqual(apply_discount(2000, "save10", NOV_1), 1800)
        self.assertEqual(apply_discount(2000, "Welcome5", NOV_1), 1900)

    def test_rule_3_unknown_code_is_rejected(self):
        with self.assertRaises(ValueError):
            apply_discount(2000, "FREE100", NOV_1)

    def test_rule_4_code_works_on_its_last_day(self):
        self.assertEqual(apply_discount(1000, "WELCOME5", date(2026, 11, 30)), 950)

    def test_rule_4_code_is_rejected_after_its_last_day(self):
        with self.assertRaises(ValueError):
            apply_discount(1000, "WELCOME5", date(2026, 12, 1))

    def test_rule_5_discount_rounds_down(self):
        self.assertEqual(apply_discount(1999, "SAVE10", NOV_1), 1800)
        self.assertEqual(apply_discount(999, "WELCOME5", NOV_1), 950)


if __name__ == "__main__":
    unittest.main()
