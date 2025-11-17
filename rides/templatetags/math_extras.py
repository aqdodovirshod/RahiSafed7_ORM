import re

from django import template

register = template.Library()


@register.filter
def range(value):
    try:
        n = int(value)
        if n < 0:
            return []
        return list(__builtins__["range"](n))
    except Exception:
        return []


@register.filter
def multiply(a, b):
    try:
        return float(a) * float(b)
    except Exception:
        return 0


@register.filter
def divide(a, b):
    try:
        b = float(b)
        if b == 0:
            return 0
        return float(a) / b
    except Exception:
        return 0


@register.filter(name="hasattr")
def has_attr(obj, attr_name):
    try:
        return hasattr(obj, attr_name)
    except Exception:
        return False


@register.filter
def unread_count(notifications_manager):
    try:
        return notifications_manager.filter(is_read=False).count()
    except Exception:
        return 0


@register.filter
def format_plate(value):
    if not value:
        return ''

    plate = re.sub(r'[^0-9a-zA-Z]', '', str(value))
    if len(plate) == 8:
        # Формат: 1234abAB -> 1234 ab AB
        normalized = plate[:6].lower() + plate[6:].upper()
        if re.fullmatch(r'\d{4}[a-z]{2}[A-Z]{2}', normalized):
            return f"{normalized[:4]} {normalized[4:6]} {normalized[6:]}"
    return value


