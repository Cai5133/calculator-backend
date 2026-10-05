import unittest
from decimal import Decimal

try:
    from backend.calculator import calculate, format_decimal, ExpressionError, DivisionByZeroError
except ImportError:  # Also run when this directory is a standalone repository root.
    from calculator import calculate, format_decimal, ExpressionError, DivisionByZeroError


class CalculatorTests(unittest.TestCase):
    def test_precedence_and_parentheses(self):
        self.assertEqual(calculate("1 + 2 * 3"), Decimal("7"))
        self.assertEqual(calculate("(1 + 2) * 3"), Decimal("9"))
        self.assertEqual(calculate("10 / 2 + 7"), Decimal("12"))
        self.assertEqual(calculate("(2 + 3) × 4"), Decimal("20"))
        self.assertEqual(calculate("9 ÷ 3 − 1"), Decimal("2"))

    def test_unary_signs_and_decimals(self):
        self.assertEqual(calculate("-5 + 8"), Decimal("3"))
        self.assertEqual(calculate("3 * -2"), Decimal("-6"))
        self.assertEqual(calculate("+.5 + 1.25"), Decimal("1.75"))
        self.assertEqual(format_decimal(calculate("1.2500")), "1.25")

    def test_scientific_functions_constants_power_and_factorial(self):
        self.assertEqual(format_decimal(calculate("sqrt(9)")), "3")
        self.assertEqual(format_decimal(calculate("sin(0)")), "0")
        self.assertEqual(format_decimal(calculate("cos(0)")), "1")
        self.assertEqual(format_decimal(calculate("log(100)")), "2")
        self.assertEqual(format_decimal(calculate("ln(e)")), "1")
        self.assertEqual(format_decimal(calculate("pi * 2")), "6.283185307179586")
        self.assertEqual(format_decimal(calculate("2^3 + 4!")), "32")

    def test_division_by_zero(self):
        with self.assertRaises(DivisionByZeroError):
            calculate("8 / (2 - 2)")

    def test_invalid_and_unsafe_input_is_rejected(self):
        for expression in ("", "1 +", "2(3)", "__import__('os').system('whoami')", "1 ** 2", "1 / / 2"):
            with self.subTest(expression=expression):
                with self.assertRaises(ExpressionError):
                    calculate(expression)

    def test_size_and_nesting_limits(self):
        with self.assertRaises(ExpressionError):
            calculate("(" * 33 + "1" + ")" * 33)
        with self.assertRaises(ExpressionError):
            calculate("1" * 257)


if __name__ == "__main__":
    unittest.main()
