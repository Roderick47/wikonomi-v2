# Wikonomi Brand & Typography System
Version 1.0 • 20 October 2026

## Identity

**Promise:** Clear, community-reported prices for Papua New Guinea.

**Personality:** Forward-looking, trustworthy, approachable, bold in the details that matter. Use **Space Grotesk** as the sole UI family to create a recognizable identity while keeping dense product views readable.

The existing green → blue → purple gradient is retained as a signature accent, not used behind important small text.

## Logo and typography

- **Font family:** `"Space Grotesk", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`.
- **Google Fonts:** 400 / 500 / 600 / 700. Space Grotesk does **not** have a true 800 weight; `font-extrabold`/ `font-black` are mapped to 700 in the current Tailwind runtime configuration.
- **Wordmark:** lowercase “wikonomi”, 700, tracking -0.045em. Preserve current multicolor text gradient.
- **Hero/display:** 36px small screens → 56px large, 700, line-height 1.06, tracking -0.045em.
- **Page title:** 30px → 48px, 700, line-height 1.13, tracking -0.035em.
- **Section title:** 24px → 32px, 700, line-height 1.2.
- **Card/product name:** 16px, 600, line-height 1.35.
- **Body:** 16px, 400, line-height 1.55. Long-form Guides: line-height 1.7 with ~68-character measure.
- **Supporting copy:** 14px, 400, line-height 1.55.
- **Metadata:** 12px, 400–500, line-height 1.5; never use tiny low-contrast text.
- **Buttons/navigation:** 14–16px, 600–700; sentence case (not all caps).
- **Prices:** 20px default, 24–32px featured, 700; tabular lining numerals, tight line-height, avoid extra letterspacing.
- **Labels/chips:** 12px, 700, +0.07em tracking; uppercase only for concise eyebrows/status.

### Implementation hooks

- Global font is defined in `wikonomi/core/templates/base.html` and `wikonomi/core/static/css/brand.css`.
- Tailwind `fontFamily.sans` / `fontFamily.display` use Space Grotesk; display/heading/body/price size tokens are available.
- Reusable CSS: `.wk-wordmark`, `.wk-display`, `.wk-page-title`, `.wk-section-title`, `.wk-card-title`, `.wk-body-lg`, `.wk-reading-copy`, `.wk-price`, `.wk-price-lg`, `.wk-price-sm`, `.wk-stat`, `.wk-eyebrow`, `.wk-meta`, `.wk-button`, `.wk-focus-ring`.
- Existing Tailwind text classes still work; semantic classes are for consistent new screens and gradually migrated key elements.
- Font delivery uses Google Fonts with `display=swap` and the system stack as fallback. For later performance/privacy needs, self-host audited WOFF2 assets under Django staticfiles after testing caching/licensing.

## Color palette

| Role | Token | Hex | Usage |
| --- | --- | --- | --- |
| Primary | `brand.purple` | **#4B2798** | Main buttons, navigational accents, links |
| Primary hover | `brand.purpleDark` | #351A70 | Hover/pressed |
| Primary tint | `brand.purpleTint` | #F2ECFC | Subtle selected/featured background |
| Accent sky | `brand.blue` | **#4DB8FF** | Brand gradient, decoration, map highlights |
| Accessible blue text | `brand.blueDark` | #075B85 | Links/information on white |
| Blue tint | `brand.blueTint` | #E8F6FF | Informational backgrounds |
| Accent green | `brand.green` | **#66D17E** | Brand gradient, decoration, positive visuals |
| Accessible green text | `brand.greenDark` | #17683F | Success/verified/positive text on white |
| Green tint | `brand.greenTint` | #EAF9EE | Positive/verified backgrounds |
| Ink | `brand.ink` | #162235 | Main foreground, headings |
| Muted | `brand.muted` | #516174 | Secondary copy and metadata |
| Canvas | `brand.canvas` | #F7F9FC | Page background |
| Surface | `brand.surface` | #FFFFFF | Cards and forms |
| Border | `brand.line` | #DDE4ED | Dividers/cards |
| Error | CSS `--wk-danger` | #B42318 | Errors and destructive alerts |
| Warning | CSS `--wk-warning` | #9A4D00 | Warning text on pale backgrounds |

These semantic shades are also exposed as CSS custom properties in `brand.css`.

### Accessibility / contrast decisions (WCAG 2.2 AA target)

- Purple **#4B2798** against white: approximately **10.28:1**. White text on the same purple: approximately **10.28:1**.
- Dark blue **#075B85** on white: approximately **7.38:1**. The brighter #4DB8FF on white is only **2.18:1**: use dark blue for small text.
- Dark green **#17683F** on white: approximately **6.80:1**. Bright green #66D17E on white is only **1.91:1**: use dark green for small text.
- Muted copy **#516174** against white: approximately **6.34:1**.
- Never rely solely on color to indicate a new/old/unverified price. Use explicit labels and freshness indicators as well.
- Target WCAG 2.2 AA: at least 4.5:1 for normal text, 3:1 for large text and necessary component boundaries/focus indicators. Validate additional foreground/background combinations, keyboard focus, and 200% zoom during review; these spot checks are not a substitute for an automated/manual accessibility audit.

## Page recipes

| Surface | Use |
| --- | --- |
| Homepage | `.wk-display` for hero; muted explanatory copy; purple CTAs; gradient reserved for the wordmark and accents |
| Product directory | `.wk-page-title`; `.wk-card-title` for product names; `.wk-price` for observed prices; meta labels for dates and source |
| Product detail | `.wk-page-title` product heading; `.wk-price-lg` for featured comparable prices; `.wk-stat` for summary metrics |
| Guides | `.wk-page-title` title; `.wk-section-title` major sections; readable text/step spacing |
| Forms | 16px input text on mobile (avoids Safari input auto-zoom), 14px labels, 700 primary CTA |
| Map / freshness | Dark-text-on-bright accent labels or white-on-dark; never white text on raw sky/green backgrounds |

## Component conventions

- **Primary button:** purple background, white text, 700 font weight. Hover: dark purple. Focus-visible: 3px purple outline with offset.
- **Secondary button:** white or purple tint, purple label, purple border.
- **Card:** white, subtle border, plenty of whitespace, product title 600, price 700.
- **Status chip:** green tint/dark green for verified; blue tint/dark blue for information; gray for stale; amber/danger only for genuine warnings.
- **Price formatting:** `K68.50` or `PGK 68.50` depending on product context. Preserve existing currency formatting in application code. Use tabular numerals on comparisons.
- **Line lengths:** break long guides into sections, paragraphs 60–75 characters where practical; don't squeeze body size below 14px.
- **Voice:** specific, concise, locally understandable English. No exaggerated savings claims or false freshness.

## Gradual rollout

This PR changes the global UI font, defines tokens/styles, and applies the new type roles to representative high-traffic surfaces (header, homepage, product directory, product detail and guide title). Existing domain colors and component behavior are preserved. Future pages should adopt these same roles rather than inventing per-template styles.

## QA checklist before merge

1. Compare mobile widths **320px, 375px, 768px** and desktop **1280px** (heading wraps, wordmark, price overflow).
2. Check font load and fallback with slow or offline network; ensure text remains visible.
3. Verify desktop/mobile navigation, search, forms, price cards, store comparisons, Guide steps, map labels and onboarding.
4. Confirm focus visibility, color contrast, 200% zoom and screen-reader labels.
5. Run existing Django tests and `python manage.py check` in the configured app environment; verify `collectstatic` serves `css/brand.css`.
