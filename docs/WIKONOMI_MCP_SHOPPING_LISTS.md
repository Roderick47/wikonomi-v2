# Wikonomi MCP — Saved Shopping Lists

MCP v0.7 adds authenticated, user-owned shopping-list access and saved-basket comparison.

## Tool surface

### Read-only

- `list_shopping_lists`
  - lists only shopping lists owned by the authenticated Wikonomi account;
  - returns list IDs, names, update timestamps, checked counts, exact-product counts, and unresolved custom-item counts;
  - does not create a default list.
- `get_shopping_list`
  - reads one owned list and its saved items;
  - returns exact `product_id` values when an item is linked to Wikonomi's catalogue;
  - preserves custom free-text items as unresolved rather than silently matching them.
- `compare_shopping_list`
  - runs the existing current basket-comparison engine against one saved list;
  - includes only unchecked items linked to exact product IDs;
  - excludes checked items;
  - surfaces unresolved custom items separately;
  - never substitutes another product;
  - does not modify the saved list.

### Private account writes

- `add_shopping_list_item`
  - requires an exact Wikonomi `product_id`;
  - accepts the quantity to add;
  - increments an existing product row instead of duplicating it, matching the website's add behavior;
  - makes a previously checked row active again when the user adds that product again;
  - creates `My Shopping List` only when the authenticated user has no list at all;
  - accepts a stable `idempotency_key` so a sequential transport retry does not increment twice.
- `update_shopping_list_item`
  - sets an absolute quantity and/or checked state;
  - does not change or substitute the product identity.
- `remove_shopping_list_item`
  - removes only an item belonging to the authenticated user's own shopping list;
  - is marked destructive because the row is deleted;
  - a repeated remove for an already-absent/non-owned item is a no-op and does not reveal another user's item.

Shopping-list writes use `wikonomi:write`, are private account changes, and are not public contributions. They are still recorded in the MCP write audit trail.

## Ownership and list selection

Every list and item query is scoped to the authenticated Wikonomi user. Supplying another user's list ID cannot expose that list.

If the user has more than one shopping list, callers must first use `list_shopping_lists` and then pass `shopping_list_id` explicitly. MCP deliberately refuses to guess which list to read, change, or compare.

If exactly one list exists, the ID may be omitted. If no list exists, read/compare tools remain side-effect-free and return an error; an explicit `add_shopping_list_item` write may create the normal `My Shopping List` before adding the confirmed product.

## Recommended AI workflow

For a request such as "add two 1 kg Trukai rice bags to my shopping list and tell me where the basket is cheapest":

1. Call `list_shopping_lists` to resolve the target list when necessary.
2. Call `search_products` to identify the exact requested product and package identity.
3. Show the selected product/list/quantity to the user and obtain confirmation for the private account change.
4. Call `add_shopping_list_item` with a stable idempotency key.
5. Call `get_shopping_list` if the user wants the saved state confirmed.
6. Call `compare_shopping_list` to compare the current unchecked exact-product basket.
7. Report missing-current-price products and unresolved custom items instead of inserting substitutes.
8. When showing split-store savings, state that transport, time, delivery, and other shopping costs are not included.

## Current-price behavior

`compare_shopping_list` reuses Wikonomi's existing basket engine:

- PGK is the default currency;
- only latest fresh observations are considered;
- observations older than the configured 90-day stale window cannot win;
- marked-for-deletion and non-positive prices are excluded;
- exact product IDs are compared across stores/branches;
- duplicate saved rows for the same product, if legacy data contains them, are aggregated by quantity by the basket engine;
- a product with no fresh current price is reported as missing rather than replaced with an alternative.

## Privacy and annotations

`list_shopping_lists`, `get_shopping_list`, and `compare_shopping_list` require only `wikonomi:read` and are read-only/non-destructive.

`add_shopping_list_item` and `update_shopping_list_item` require `wikonomi:write`, but their MCP annotations use `open_world_hint=false` because they only change the authenticated user's private Wikonomi account data.

`remove_shopping_list_item` also requires `wikonomi:write`, uses `open_world_hint=false`, and sets `destructive_hint=true`.

This differs intentionally from price/guide publishing tools, whose changes are public contributions.

## Scope limits in v0.7

- MCP does not create or rename additional named shopping lists; users can manage named lists through the website. An add can only create the default list when none exists.
- MCP does not create new custom free-text items. Existing custom items remain readable and visible in comparisons, but an AI must not silently resolve them. Use `search_products`, let the user choose an exact product, then add it explicitly.
- MCP does not replace one product with another through the update tool. Remove the old item and add the confirmed replacement instead.

No database migration is required for v0.7; it uses the existing `ShoppingList`, `ShoppingListItem`, basket engine, and MCP audit log models.
