from django import template
from django.utils.timesince import timesince
from datetime import datetime, timedelta

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


@register.filter
def rounded_timesince(value):
    """
    Return a rounded, simplified time since string.
    Examples:
    - "1 day, 5 hours ago" -> "1 day ago"
    - "1 week, 2 days ago" -> "1 week ago"
    - "2 months, 1 week ago" -> "2 months ago"
    """
    if not value:
        return ""
    
    # Get the full timesince string
    time_str = timesince(value)
    
    if not time_str or time_str == "0 minutes":
        return "just now"
    
    # Split the time string and take only the first part
    parts = time_str.split(", ")
    if parts:
        first_part = parts[0]
        
        # Handle pluralization
        if first_part.startswith("1 "):
            return f"{first_part} ago"
        else:
            return f"{first_part} ago"
    
    return f"{time_str} ago"


@register.filter  
def rounded_timesince_js(value):
    """
    Return a rounded time since string for JavaScript (without 'ago').
    Used for JSON responses.
    """
    if not value:
        return ""
        
    time_str = timesince(value)
    
    if not time_str or time_str == "0 minutes":
        return "just now"
    
    parts = time_str.split(", ")
    if parts:
        return parts[0]
    
    return time_str

