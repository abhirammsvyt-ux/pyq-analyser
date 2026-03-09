"""Custom template tags for analytics."""
from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Get item from dictionary by key.
    Usage: {{ my_dict|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key, [])


@register.filter(name='priority_emoji')
def priority_emoji(tier):
    """Return emoji for priority tier."""
    emojis = {
        'TIER_1': '🔥🔥🔥',
        'tier_1': '🔥🔥🔥',
        'TIER_2': '🔥🔥',
        'tier_2': '🔥🔥',
        'TIER_3': '🔥',
        'tier_3': '🔥',
        'TIER_4': '✓',
        'tier_4': '✓',
    }
    return emojis.get(tier, '✓')


@register.filter(name='priority_label')
def priority_label(tier):
    """Return label for priority tier."""
    labels = {
        'TIER_1': 'TOP PRIORITY',
        'tier_1': 'TOP PRIORITY',
        'TIER_2': 'HIGH PRIORITY',
        'tier_2': 'HIGH PRIORITY',
        'TIER_3': 'MEDIUM PRIORITY',
        'tier_3': 'MEDIUM PRIORITY',
        'TIER_4': 'LOW PRIORITY',
        'tier_4': 'LOW PRIORITY',
    }
    return labels.get(tier, 'LOW PRIORITY')
