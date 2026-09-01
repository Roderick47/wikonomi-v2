# Wikonomi Mapbox rollout

Nine map views now use Mapbox GL JS when MAPBOX_PUBLIC_TOKEN is configured:
home/search, business, product, price detail, nearby prices, product analysis,
price create, price edit and bulk upload. MAPBOX_STYLE_URL defaults to
mapbox://styles/mapbox/streets-v12 and accepts a custom Mapbox Studio style.

## Activate

1. Create a public Mapbox token (`pk.`), with the default public map scopes, in
   https://account.mapbox.com/access-tokens/ . Restrict allowed URLs to
   https://wikonomi.com/* and https://www.wikonomi.com/*, plus the actual preview
   origin if preview testing is required. Never supply a secret `sk.` token.
2. Add MAPBOX_PUBLIC_TOKEN to the Render web service environment. Configure a
   separate development token for local testing. Do not commit either token.
3. Deploy this branch to a preview and verify the checklist below before merging.
   Changing MAPBOX_STYLE_URL can later apply Wikonomi's own Studio design.
4. Watch Mapbox's account usage. These are GL JS map loads, not raster tile API
   requests. A hidden mobile home map is not initialized until opened; resizing
   or reopening it reuses the same instance. Visitors and browser bots can load
   maps too; registered user counts alone do not establish usage.

## Preserved contracts

- All app coordinates remain latitude/longitude. The shared JS boundary reverses
  them to longitude/latitude only for Mapbox and reverses map click events back.
- No models, migrations, saved coordinates, H3 res8/res9 indexes, grid radius,
  distance calculations, GPS permission/retry logic or search query filters change.
- Click-to-place, business location defaults, editing saved pins and GPS inputs
  still feed the same form fields. No Mapbox geocoding/storage dependency is added.
- Price labels and clusters use Wikonomi data. At close zoom, clicking a cluster
  opens every price at that location. Colours compare the same product ID and
  currency among displayed reports; singleton/equal groups are neutral. They do
  not claim the cheapest price in the city or compare unrelated products.
- The existing 150-report map endpoint limit remains.

## Resilience and rollback

A blank/non-public token, unavailable SDK or unsupported WebGL uses the existing
Leaflet/OpenStreetMap rendering. A secret token is never serialized. For a runtime
Mapbox style/token/network error, show an inline notice; saved data and list view
remain available. Mapbox logo and attribution remain enabled.

Rollback: clear MAPBOX_PUBLIC_TOKEN and redeploy. No data migration is needed.

## Validation

Run `node --test tests/maps.test.cjs` from the repository root. Tests cover
coordinate order (including zero), map-click events, GPS-style pin updates,
map-instance reuse, fallback paths, cluster lifecycle/colocated reports and
same-product/currency price comparisons.

Live browser acceptance requires the owner's working token:

- Mobile: open/close/reopen map, rotate screen, pan/zoom, open a cluster and price.
- Desktop: toggle the side map, resize window, check price label popups and logo.
- Allow/deny GPS; verify unchanged nearby results and URL coordinates.
- Create/edit/bulk-upload forms: choose a business default, click a pin location,
  use GPS and save; confirm the saved coordinates and H3 indexes are unchanged.
- Visit all nine map views; test multiple reports at exactly the same coordinates.
- Check invalid token/style and WebGL-disabled fallback; check no console errors.

Reference: https://docs.mapbox.com/mapbox-gl-js/guides/ and
https://docs.mapbox.com/mapbox-gl-js/guides/pricing/ .
