"""Calculate contribution per sold unit from a UTF-8 JSON file (Python 3)."""
import json
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path


COSTS = (
    "product_cost", "inbound_freight", "duty", "packaging", "marketplace_fee",
    "fulfillment", "expected_return_loss", "other_variable", "ads",
)


def money(value, name):
    if value is None or value == "" or value == "未获取":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative number or null")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{name} must be a non-negative number or null") from None
    if not number.is_finite() or number < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return number


def rounded(value):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate(record):
    if not isinstance(record, dict):
        raise ValueError("input must be one JSON object")
    currency = record.get("currency")
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency must be a three-letter uppercase code")
    fields = ("net_price",) + COSTS
    unknown = sorted(set(record) - set(fields) - {"currency"})
    if unknown:
        raise ValueError("unrecognized fields: " + ", ".join(unknown))
    values = {key: money(record.get(key), key) for key in fields}
    if values["net_price"] == 0:
        raise ValueError("net_price must be greater than zero")
    missing = [key for key in fields if values[key] is None]
    result = dict(currency=currency, missing=missing, before_ads=None,
                  break_even_ads_per_unit=None, contribution=None, margin_pct=None)
    if any(key != "ads" for key in missing):
        return result

    price = values["net_price"]
    before = price - sum(values[key] for key in COSTS if key != "ads")
    result["before_ads"] = rounded(before)
    # A negative pre-ad contribution cannot reach break-even through ad cuts.
    if before >= 0:
        result["break_even_ads_per_unit"] = rounded(before)
    if values["ads"] is not None:
        contribution = before - values["ads"]
        result["contribution"] = rounded(contribution)
        result["margin_pct"] = rounded(100 * contribution / price)
    return result


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: python unit_economics.py unit-input.json")
    try:
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"),
                          parse_float=Decimal)
        with localcontext() as context:
            context.prec = 60
            result = calculate(data)
    except (OSError, UnicodeError, ValueError, InvalidOperation) as exc:
        raise SystemExit(f"Invalid unit input: {exc}") from None
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
