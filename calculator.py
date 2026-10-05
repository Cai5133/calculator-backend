"""A deliberately small recursive-descent parser for calculator expressions.

Decimal numbers, parentheses, unary signs, arithmetic operators and a small
allowlist of scientific functions are accepted. User input is never evaluated
as Python or another general-purpose language.
"""

from decimal import Decimal, DecimalException, localcontext
import math
import re


class ExpressionError(ValueError):
    """An invalid or unsupported mathematical expression."""


class DivisionByZeroError(ExpressionError):
    """The expression attempts to divide by zero."""


_TOKEN = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z]+|[()+*/^!,.-]")
MAX_EXPRESSION_LENGTH = 256
MAX_TOKENS = 128
MAX_NESTING = 32


def _tokenize(expression: str) -> list[str]:
    if not isinstance(expression, str) or not expression.strip():
        raise ExpressionError("Please enter an expression.")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise ExpressionError(f"Expression is too long (maximum {MAX_EXPRESSION_LENGTH} characters).")

    # Accept the symbols shown in the UI as well as their ASCII API forms.
    expression = expression.translate(str.maketrans({"×": "*", "÷": "/", "−": "-", "–": "-", "π": "pi"}))

    tokens: list[str] = []
    position = 0
    while position < len(expression):
        if expression[position].isspace():
            position += 1
            continue
        match = _TOKEN.match(expression, position)
        if not match:
            raise ExpressionError(f"Unsupported character at position {position + 1}.")
        tokens.append(match.group())
        position = match.end()
        if len(tokens) > MAX_TOKENS:
            raise ExpressionError(f"Expression has too many parts (maximum {MAX_TOKENS}).")
    return tokens


class _Parser:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.position = 0
        self.depth = 0

    def peek(self) -> str | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self) -> str:
        token = self.peek()
        if token is None:
            raise ExpressionError("The expression ends unexpectedly.")
        self.position += 1
        return token

    def parse(self) -> Decimal:
        value = self.expression()
        if self.peek() is not None:
            raise ExpressionError(f"Unexpected token '{self.peek()}'.")
        return value

    def expression(self) -> Decimal:
        value = self.term()
        while self.peek() in ("+", "-"):
            operator = self.take()
            right = self.term()
            value = value + right if operator == "+" else value - right
        return value

    def term(self) -> Decimal:
        value = self.power()
        while self.peek() in ("*", "/"):
            operator = self.take()
            right = self.power()
            if operator == "/" and right == 0:
                raise DivisionByZeroError("Cannot divide by zero.")
            value = value * right if operator == "*" else value / right
        return value

    def power(self) -> Decimal:
        value = self.unary()
        if self.peek() == "^":
            self.take()
            exponent = self.power()
            if exponent != exponent.to_integral_value() or abs(exponent) > 1000:
                raise ExpressionError("Power exponent must be an integer between -1000 and 1000.")
            try:
                value = value ** int(exponent)
            except (DecimalException, OverflowError) as error:
                raise ExpressionError("Power result is outside the supported range.") from error
        return value

    def unary(self) -> Decimal:
        token = self.peek()
        if token in ("+", "-"):
            self.take()
            value = self.unary()
            return value if token == "+" else -value
        return self.primary()

    def primary(self) -> Decimal:
        token = self.peek()
        if token == "(":
            self.take()
            self.depth += 1
            if self.depth > MAX_NESTING:
                raise ExpressionError(f"Parentheses are nested too deeply (maximum {MAX_NESTING}).")
            value = self.expression()
            if self.take() != ")":
                raise ExpressionError("Missing closing parenthesis.")
            self.depth -= 1
            return value
        if token is None or token in ("+", "-", "*", "/", "^", ")", ",", "!"):
            raise ExpressionError("A number or opening parenthesis was expected.")
        if token in ("sin", "cos", "tan", "sqrt", "log", "ln", "abs"):
            function = self.take()
            if self.take() != "(":
                raise ExpressionError(f"Function {function} requires parentheses.")
            argument = self.expression()
            if self.take() != ")":
                raise ExpressionError("Missing closing parenthesis.")
            try:
                if function == "sqrt":
                    if argument < 0: raise ExpressionError("Square root requires a non-negative value.")
                    value = Decimal(str(math.sqrt(float(argument))))
                elif function == "abs": value = abs(argument)
                elif function == "ln":
                    if argument <= 0: raise ExpressionError("ln requires a positive value.")
                    value = Decimal(str(math.log(float(argument))))
                elif function == "log":
                    if argument <= 0: raise ExpressionError("log requires a positive value.")
                    value = Decimal(str(math.log10(float(argument))))
                elif function == "sin": value = Decimal(str(math.sin(float(argument))))
                elif function == "cos": value = Decimal(str(math.cos(float(argument))))
                else: value = Decimal(str(math.tan(float(argument))))
            except (ValueError, OverflowError) as error:
                raise ExpressionError(f"{function} is outside the supported range.") from error
            return value
        if token in ("pi", "e"):
            self.take()
            return Decimal(str(math.pi if token == "pi" else math.e))
        self.take()
        try:
            value = Decimal(token)
        except DecimalException as error:
            raise ExpressionError("Invalid number.") from error
        if not value.is_finite():
            raise ExpressionError("Numbers must be finite.")
        if self.peek() == "!":
            self.take()
            if value != value.to_integral_value() or value < 0 or value > 1000:
                raise ExpressionError("Factorial requires an integer from 0 to 1000.")
            value = Decimal(math.factorial(int(value)))
        return value


def format_decimal(value: Decimal) -> str:
    if value == 0:
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def calculate(expression: str) -> Decimal:
    """Parse and calculate an expression using Decimal arithmetic."""
    tokens = _tokenize(expression)
    try:
        with localcontext() as context:
            context.prec = 28
            result = _Parser(tokens).parse()
            if not result.is_finite():
                raise ExpressionError("The result is outside the supported range.")
            return result
    except DivisionByZeroError:
        raise
    except ExpressionError:
        raise
    except (DecimalException, OverflowError) as error:
        raise ExpressionError("The expression is outside the supported numeric range.") from error
