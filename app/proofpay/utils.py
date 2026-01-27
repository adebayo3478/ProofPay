from __future__ import annotations

def normalize_address(addr: str) -> str:
    return (addr or "").strip().lower()


def amount_to_units(amount_str: str, decimals: int) -> str:
    """
    Convert a decimal string to integer units (as string).
    Raises ValueError if amount has more precision than token decimals.
    """
    s = (amount_str or "").strip()
    if not s:
        raise ValueError("amount is required")
    if s.startswith("+"):
        s = s[1:]
    if "." in s:
        whole, frac = s.split(".", 1)
    else:
        whole, frac = s, ""
    if whole == "":
        whole = "0"
    if not whole.isdigit() or not frac.isdigit():
        raise ValueError("amount must be a decimal string")
    if len(frac) > decimals:
        raise ValueError("amount has too many decimal places")
    frac = frac.ljust(decimals, "0")
    units = (whole + frac).lstrip("0")
    return units if units != "" else "0"


def units_to_amount(units: str, decimals: int) -> str:
    """
    Convert integer units string to decimal string.
    """
    u = (units or "").strip()
    if not u.isdigit():
        raise ValueError("units must be a string of digits")
    if decimals == 0:
        return u
    if len(u) <= decimals:
        return "0." + u.rjust(decimals, "0")
    return u[:-decimals] + "." + u[-decimals:]
