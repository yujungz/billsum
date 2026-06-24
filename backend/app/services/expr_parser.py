"""Expression parser for the `expr_b64` pricing formula.

The `expr_b64` field in the logs table is a Base64-encoded string that, when
decoded, yields a pricing formula.  There are two forms:

Simple (no tiering):
    tier("base", p * 5 + c * 25 + cr * 6.5 + cc1h * 10 + cc5m * 6.25)

Tiered:
    USD: cond1 ? tier("base", expr1) : cond2 ? tier("tier2", expr2) : tier("last", exprN)

Variable → table field mapping:
    p     → prompt_tokens
    c     → completion_tokens
    cr    → cache_tokens
    cc5m  → cache_creation_tokens_5m
    cc1h  → GREATEST(0, cache_creation_tokens - cache_creation_tokens_5m)
"""

import base64
import re
import logging

log = logging.getLogger(__name__)

# Variables that may appear in a pricing expression, and their DB column names
VAR_LIST = ["p", "c", "cr", "cc5m", "cc1h"]

VAR_TO_DB = {
    "p": "prompt_tokens",
    "c": "completion_tokens",
    "cr": "cache_tokens",
    "cc5m": "cache_creation_tokens_5m",
    "cc1h": "GREATEST(0, cache_creation_tokens - cache_creation_tokens_5m)",
}

# Price field names — written directly from coefficients
PRICE_FIELDS = {
    "p": "prompt_price",
    "c": "completion_price",
    "cr": "cache_price",
    "cc5m": "cache_creation_5M_price",
    "cc1h": "cache_creation_price",
}

# Ratio field expressions — derived from prices
# (computed in Python after we know model_ratio)
RATIO_EXPR = {
    "model_ratio": "prompt_price / 2",
    "completion_ratio": "completion_price / (model_ratio * 2) if model_ratio else 0",
    "cache_ratio": "cache_price / (model_ratio * 2) if model_ratio else 0",
    "cache_creation_ratio": "cache_creation_price / (model_ratio * 2) if model_ratio else 0",
    "cache_creation_ratio_5m": "cache_creation_5M_price / (model_ratio * 2) if model_ratio else 0",
}


def decode(b64_str: str) -> str:
    """Base64-decode the expression string."""
    try:
        return base64.b64decode(b64_str).decode("utf-8")
    except Exception as e:
        raise ValueError(f"Base64 decode failed: {e}")


def strip_currency(formula: str) -> tuple[str, str]:
    """Strip currency prefix ('USD:' or 'CNY:'), default to USD."""
    f = formula.strip()
    if f.startswith("USD:"):
        return "USD", f[4:].strip()
    if f.startswith("CNY:"):
        return "CNY", f[4:].strip()
    return "USD", f


def _top_level_split(s: str) -> list[str]:
    """Split a ternary-operator string at the top level (outside parens).
    Returns tokens like [cond, '?', expr, ':', cond, '?', expr, ':', expr]
    """
    tokens = []
    depth = 0
    cur = ""
    for ch in s:
        if ch in "([{":
            depth += 1
            cur += ch
        elif ch in ")]}":
            depth -= 1
            cur += ch
        elif ch == "?" and depth == 0:
            tokens.append(cur.strip())
            tokens.append("?")
            cur = ""
        elif ch == ":" and depth == 0:
            tokens.append(cur.strip())
            tokens.append(":")
            cur = ""
        else:
            cur += ch
    rest = cur.strip()
    if rest:
        tokens.append(rest)
    return tokens


def parse_tier(text: str) -> tuple[str, str]:
    """Parse 'tier("name", expression)' → (name, expression)."""
    m = re.match(
        r'tier\s*\(\s*"([^"]*)"\s*,\s*(.+?)\s*\)\s*$', text, re.DOTALL
    )
    if not m:
        raise ValueError(f"Cannot parse tier expression: {text[:120]}")
    return m.group(1), m.group(2).strip()


def extract_coefficients(expr: str) -> dict[str, float]:
    """Extract coefficients from an arithmetic expression.
    E.g. 'p * 5 + c * 25 + cr * 6.5' → {'p': 5.0, 'c': 25.0, 'cr': 6.5, 'cc5m': 0.0, 'cc1h': 0.0}
    """
    coeffs = {v: 0.0 for v in VAR_LIST}
    # Normalize whitespace around + and *
    expr = expr.strip()
    terms = re.split(r"\s*\+\s*", expr)
    for term in terms:
        term = term.strip()
        m = re.match(r"(\w+)\s*\*\s*([\d.]+(?:e[+-]?\d+)?)", term)
        if m:
            var, val = m.group(1), float(m.group(2))
            if var in coeffs:
                coeffs[var] = val
    return coeffs


def _translate_condition(cond_str: str) -> str:
    """Translate a Python-style condition into a SQL expression.
    E.g. 'p <= 32000 && c <= 200' → 'prompt_tokens <= 32000 AND completion_tokens <= 200'
    """
    result = cond_str
    for var, db_col in VAR_TO_DB.items():
        # Replace whole-word occurrences of the variable name
        result = re.sub(rf"\b{re.escape(var)}\b", db_col, result)
    # Translate operators
    result = result.replace("&&", "AND").replace("||", "OR")
    result = result.replace("==", "=")
    result = result.replace("!=", "<>")
    return result


class PricingTier:
    """One tier in a pricing formula."""
    __slots__ = ("condition", "tier_name", "coefficients")

    def __init__(self, condition: str | None, tier_name: str, coefficients: dict[str, float]):
        self.condition = condition       # None → ELSE (last)
        self.tier_name = tier_name
        self.coefficients = coefficients

    def __repr__(self):
        return f"PricingTier(cond={self.condition!r}, name={self.tier_name!r}, coeffs={self.coefficients})"


class ParsedFormula:
    """Result of parsing an expr_b64 string."""
    def __init__(self, currency: str, tiers: list[PricingTier]):
        self.currency = currency
        self.tiers = tiers

    @property
    def is_tiered(self) -> bool:
        return len(self.tiers) > 1 or (len(self.tiers) == 1 and self.tiers[0].condition is not None)


def parse(b64_str: str) -> ParsedFormula:
    """Parse an expr_b64 string into a ParsedFormula."""
    formula = decode(b64_str)
    currency, formula = strip_currency(formula)

    # Remove trailing semicolons etc.
    formula = formula.strip().rstrip(";")

    if "?" not in formula:
        # Simple: single tier("name", expression)
        tier_name, expression = parse_tier(formula)
        coeffs = extract_coefficients(expression)
        return ParsedFormula(currency, [PricingTier(None, tier_name, coeffs)])

    # Tiered formula
    tokens = _top_level_split(formula)
    tiers: list[PricingTier] = []

    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and tokens[i + 1] == "?":
            # tokens[i] = condition, tokens[i+2] = tier(...)
            condition = tokens[i]
            tier_text = tokens[i + 2]
            tier_name, expression = parse_tier(tier_text)
            coeffs = extract_coefficients(expression)
            tiers.append(PricingTier(condition, tier_name, coeffs))
            i += 3
            # skip the ':' separator
            if i < len(tokens) and tokens[i] == ":":
                i += 1
        else:
            # Last tier (no condition before it)
            tier_text = tokens[i]
            tier_name, expression = parse_tier(tier_text)
            coeffs = extract_coefficients(expression)
            tiers.append(PricingTier(None, tier_name, coeffs))
            break

    if not tiers:
        raise ValueError(f"No tiers parsed from formula: {formula[:200]}")

    return ParsedFormula(currency, tiers)


def _coeff_to_str(v: float) -> str:
    """Format coefficient as SQL-safe literal."""
    return f"{v:.10f}".rstrip("0").rstrip(".")


def generate_update_sql(table: str, b64_str: str, formula: ParsedFormula) -> str:
    """Generate a single UPDATE SQL for all rows with the given expr_b64.

    For simple formulas: flat SET.
    For tiered formulas: CASE WHEN per price field.
    """
    if not formula.tiers:
        return ""

    # Security check: table name must be alphanumeric/underscore only
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table):
        raise ValueError(f"Invalid table name: {table}")

    price_vars = ["p", "c", "cr", "cc5m", "cc1h"]

    def build_case(price_var: str) -> str:
        """Build CASE WHEN ... END for one price field."""
        if not formula.is_tiered:
            # Simple: just the value
            val = formula.tiers[0].coefficients.get(price_var, 0.0)
            return _coeff_to_str(val)

        whens: list[str] = []
        for t in formula.tiers:
            if t.condition is not None:
                sql_cond = _translate_condition(t.condition)
                val = t.coefficients.get(price_var, 0.0)
                whens.append(f"WHEN {sql_cond} THEN {_coeff_to_str(val)}")
            else:
                val = t.coefficients.get(price_var, 0.0)
                whens.append(f"ELSE {_coeff_to_str(val)}")
        return "CASE " + " ".join(whens) + " END"

    assignments: list[str] = []
    for pv in price_vars:
        db_col = PRICE_FIELDS[pv]
        assignments.append(f"`{db_col}` = {build_case(pv)}")

    # For ratios: they are derived from a single flat set per tier (not row data).
    # For simple formulas: compute from the single tier's coefficients.
    # For tiered formulas: compute from each tier separately.
    #
    # We re-use the tier coefficients; model_ratio and ratios differ per tier.
    # Build a CASE per ratio field.

    ratio_vars = [
        ("model_ratio", lambda c: c["p"] / 2.0 if c["p"] else 0),
        ("completion_ratio", lambda c: c["c"] / (c["p"]) if c["p"] else 0),
        ("cache_ratio", lambda c: c["cr"] / c["p"] if c["p"] else 0),
        ("cache_creation_ratio", lambda c: c["cc1h"] / c["p"] if c["p"] else 0),
        ("cache_creation_ratio_5m", lambda c: c["cc5m"] / c["p"] if c["p"] else 0),
    ]

    for ratio_col, ratio_fn in ratio_vars:
        if not formula.is_tiered:
            val = ratio_fn(formula.tiers[0].coefficients)
            assignments.append(f"`{ratio_col}` = {_coeff_to_str(val)}")
        else:
            whens: list[str] = []
            for t in formula.tiers:
                val = ratio_fn(t.coefficients)
                if t.condition is not None:
                    sql_cond = _translate_condition(t.condition)
                    whens.append(f"WHEN {sql_cond} THEN {_coeff_to_str(val)}")
                else:
                    whens.append(f"ELSE {_coeff_to_str(val)}")
            assignments.append(f"`{ratio_col}` = CASE " + " ".join(whens) + " END")

    sql = (
        f"UPDATE `{table}` SET\n  " + ",\n  ".join(assignments) +
        f"\nWHERE expr_b64 IS NOT NULL AND expr_b64 != '' AND expr_b64 = %s"
    )
    return sql
