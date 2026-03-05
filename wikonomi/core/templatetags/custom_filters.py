from django import template

register = template.Library()


@register.filter
def intcomma(value):
    """
    Convert a number to a string with commas as thousands separators.
    Handles integers and decimals.
    Example: 1200 -> "1,200", 1200.50 -> "1,200.50"
    """
    try:
        value = float(value)
        # Check if it's a whole number
        if value == int(value):
            return "{:,}".format(int(value))
        return "{:,.2f}".format(value)
    except (ValueError, TypeError):
        return value


@register.filter
def split(value, delimiter=','):
    """Split a string by a delimiter."""
    if not value:
        return []
    return [item.strip() for item in value.split(delimiter) if item.strip()]

