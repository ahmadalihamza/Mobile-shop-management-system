"""Exact financial inputs and safe display/search helpers."""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import unicodedata


class BusinessError(ValueError):
    """A business validation message safe to display to the operator."""


def decimal(value, label='Amount', positive=False, places=6) -> Decimal:
    if isinstance(value, (float, bool)):
        raise BusinessError(f'{label} must be entered as an exact decimal.')
    try:
        d = Decimal(str(value).strip().replace(',', ''))
        if not d.is_finite() or d < 0 or d > Decimal('1000000000'):
            raise ValueError
        if d.as_tuple().exponent < -places or (positive and not d):
            raise ValueError
        return d
    except (InvalidOperation, ValueError, TypeError):
        raise BusinessError(f'Enter a {"positive" if positive else "non-negative"} {label.lower()} with at most {places} decimal places.') from None


def money(value, label='Amount', positive=False) -> int:
    return int(decimal(value, label, positive, 2) * 100)


def rounded_paisa(value: Decimal) -> int:
    return int((value * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def amount_text(paisa: int) -> str:
    return f'{Decimal(paisa) / 100:.2f}'


def currency(paisa: int) -> str:
    if paisa is None:
        return 'Unresolved'
    return f'{Decimal(paisa) / 100:,.2f}'


def quantity(value) -> int:
    d = decimal(value, 'Quantity', True, 0)
    if d > 1000000:
        raise BusinessError('Quantity is too large (maximum 1,000,000).')
    return int(d)


def business_date(value: str) -> str:
    try:
        d = date.fromisoformat(value)
        if d.isoformat() != value or d.year < 1900:
            raise ValueError
        return value
    except (ValueError, TypeError):
        raise BusinessError('Enter a valid date in YYYY-MM-DD format.') from None


def today() -> str:
    return date.today().isoformat()


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def text(value, label='Name', required=False, limit=500) -> str:
    result = str(value or '').strip()
    if (required and not result) or len(result) > limit or '\x00' in result:
        raise BusinessError(f'{label} is required and must be at most {limit} characters.' if required else f'{label} is too long or contains invalid characters.')
    return result


def normalize(value: str) -> str:
    value = unicodedata.normalize('NFKC', value).casefold().replace('+', ' plus ')
    return ' '.join(re.findall(r'[^\W_]+', value, re.UNICODE))


def search_matches(query: str, value: str) -> bool:
    compact = normalize(value).replace(' ', '')
    return all(token in compact for token in normalize(query).split())
