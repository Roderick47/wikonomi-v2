# Wikonomi MCP — Business and Branch Intelligence

MCP v0.6 adds read-only business and branch intelligence on top of Wikonomi's current-price semantics.

## Tools

### `get_business`

Use after `search_wikonomi` resolves a business. The tool returns:

- business profile and subcategory;
- all known branches with IDs, address/contact/location, main-branch and active flags;
- fresh/current price coverage using the same 90-day stale rule as product comparisons;
- current products grouped across the business's branches, including best current price and branch/location coverage;
- direct business-level observations that were not assigned to a branch, reported separately;
- business-wide imported inventory metadata when requested.

Optional `product_query` narrows the current-product list without changing the business coverage summary. `currency` defaults to PGK.

### `get_branch`

Use a branch ID returned by `search_wikonomi` or `get_business`. The tool returns:

- exact branch profile, address, public contact fields and map coordinates when known;
- price coverage for that branch;
- one latest price observation per product/currency for that branch;
- freshness labels and evidence counts;
- optional stale rows when `include_stale=true`.

By default stale rows are excluded from the returned branch price list. They remain represented in coverage statistics so an AI can distinguish "no current price" from "a price exists, but it is old".

## Business search

Business results inside the existing `search_wikonomi` tool now include current price coverage and matching branch IDs when the query matches a branch name or address. This allows a client to resolve queries such as:

- "RH Vision City"
- "which supermarkets have recent rice price data?"
- "what does this business currently have prices for?"

The recommended sequence is:

1. `search_wikonomi` to resolve the business/branch;
2. `get_business` for business-wide coverage or `get_branch` for exact location evidence;
3. `compare_current_prices` for an exact product across competing stores when needed.

## Current-price semantics

Business and branch coverage follows the same core rules as Wikonomi's product comparison system:

- reports marked for deletion are ignored;
- invalid/non-positive prices are ignored;
- only the latest observation for each product, store/location and currency is considered the latest-known state;
- observations older than 90 days are stale;
- stale latest-known prices do not count as current product coverage;
- historical low prices do not determine current business or branch results.

If a branch reported K5 for a product historically and then K8 recently, the branch's latest current price is K8. The old K5 report remains historical data.

## Inventory is not branch stock

`BusinessInventoryItem` is currently attached to the business, not an individual branch. Therefore MCP v0.6 deliberately labels imported inventory as:

- `scope: business_wide`
- `branch_specific: false`

A client must **not** claim that an imported inventory item is stocked at Vision City, Boroko, Waigani, or any other specific branch solely because the parent business imported it.

Branch-specific evidence currently comes from branch-linked price reports. Future branch-level inventory support can replace this limitation when the data model supports it.

## Safety and permissions

`get_business` and `get_branch`:

- require only `wikonomi:read`;
- are read-only and non-destructive;
- do not publish or modify data;
- do not require write confirmation;
- do not add read queries to the persistent MCP write-audit trail.

No database migration is required for MCP v0.6.
