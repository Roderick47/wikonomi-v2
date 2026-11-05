# Wikonomi SVG icon system

Approved soft-duotone icon assets: `find-price`, `compare-prices`, `nearby-prices`, `stores`, `record-price`, `guides`, `price-history`, `saved-items`.

The 24×24 standalone SVGs live under `wikonomi/core/static/img/icons/`. A neutral icon badge with a soft tint and accent dot is provided by `wikonomi/core/static/css/icons.css`. Color meanings follow `docs/BRAND_SYSTEM.md`: blue for discovery, green for contribution and purple for organization.

Include the shared icon template (decorative by default) next to readable text:

```django
{% include "includes/wk_icon.html" with name="find-price" intent="blue" size="sm" %}
{% include "includes/wk_icon.html" with name="record-price" intent="green" size="lg" %}
```

Sizes: default 40px, `sm` 26px, `lg` 48px. Keep parent text or an accessible name on icon-only controls; the badge has `aria-hidden=true` and its child has `alt=""`. To add icons, include the literal static path in the central template so ManifestStaticFilesStorage can resolve the hashed file name. Do not dynamically concatenate paths using `{% static 'img/icons/' %}`.

Validate at 320/375px and 200% zoom, check `python manage.py check` and `collectstatic`, and check key user flows before shipping. No additional JavaScript is required.
