# Country-aware Wikonomi

Status: country-level web discovery and submission support on this feature branch.

## Coverage
Every country/territory included in ISO 3166-1 through pycountry is selectable
(249 in the current catalogue). English-language labels and local ISO 4217
currency denominations come from Babel/CLDR. Featured ordering prioritizes PNG,
the Pacific Islands, Asia and other large markets. This is *country catalogue
coverage*, not a claim that price data already exists in every market.

## Detection and preferences
- The Cloudflare-proxied wikonomi.com domain has IP geolocation enabled. Its
  CF-IPCountry header is a country *hint*, not proof of residence.
- Signed-in users' explicit Profile.preferred_country_code choice wins.
- The anonymous visitor's wk_country cookie is next.
- Otherwise use a valid CF-IPCountry value; fall back to PNG if unavailable.
- The navbar globe selector allows overriding or returning to automatic
  detection without GPS permission.
- Country selection never changes the actual prices or converts currencies.

## Data isolation
- PriceReport.country_code is the source of truth for a recorded shop price.
- Business and BusinessBranch carry country codes. Business names are unique
  per country; a global Product remains a single catalogue entry.
- Home feed, infinite scroll, map endpoint, fuel highlights, product and store
  directories, product comparisons, detail maps and price forms use that scope.
- Shared price detail links can still show the original report from any country.
- Date/time localization, regional address structure, province/city selectors,
  tax regimes, international product matching, translations and cross-currency
  conversions are deliberately out of scope.

## Migration and integrity
Existing price and business/branch records receive PG as a data-migration default,
because the current platform was PNG-focused. **Audit any existing foreign
records before or immediately after rollout**, because a pre-existing foreign
record would incorrectly inherit PG. New web price submissions use the selected
country and default to that country's currency. Other integration sources should
set the correct country explicitly, or use the linked business origin. Never
attribute a shop's country based solely on a contributor's IP address.

## Deployment checks
Run:
- python manage.py check
- python manage.py makemigrations --check --dry-run
- python manage.py test core.test_markets core.test_discovery_feed core.test_map_history
- Test PNG and India from Cloudflare geolocation, guest manual selection,
  and saved preference after login/logout; test mobile navbar.
- Test empty country, price submission, current comparisons, map and bulk import.
- Deploy migrations before serving this feature; verify Render and Cloudflare
  headers at the origin without logging raw visitor IPs.

No new geolocation API or currency-exchange service is required.
