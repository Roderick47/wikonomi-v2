# Wikonomi — ChatGPT plugin submission pack

Prepared: 2026-09-01. Server release: `0.2.0`. Status: preparation, not submitted or approved.

This document separates the deployed MCP service from OpenAI's public directory review. Existing personal connections can continue using the server; a public listing requires a new MCP-backed submission.

## Proposed listing

**Name:** Wikonomi

**Short description:** Find local PNG prices and contribute practical community guides.

**Long description:** Search Wikonomi's community-contributed products, businesses, price observations, and practical guides for Papua New Guinea. Compare reported prices and observation dates, then open the original records. Connect a Wikonomi account to contribute observed prices and create or edit guides with source links. Publishing actions require confirmation and appear publicly under your Wikonomi account. Guide edits preserve version history; edits to another author's guide require an additional confirmation. Reported prices may be out of date and are not guaranteed offers. Restricted accounts may have read-only access.

**Website:** https://www.wikonomi.com

**Server type:** With MCP, Universal URL, no custom UI or bundled skill.

**MCP URL:** https://www.wikonomi.com/mcp

**Authentication:** OAuth authorization code with PKCE and dynamic client registration. Users sign in with their own Wikonomi accounts; normal username/password login is supported.

**Starter prompts:**

- Find recent rice prices on Wikonomi and show the observation dates.
- Help me contribute a price I actually observed at a shop.
- Draft a practical guide with sources and ask me before publishing it.
- Find an existing guide and help me propose a sourced correction.

Do not claim guaranteed mobile availability, automated receipt/photo upload, verified prices, official government authority, purchases, deletions, or administrative control.

## Owner-supplied items still required

| Item | What is missing |
|---|---|
| Publisher identity | A verified individual or business identity in the publishing OpenAI organization; no verification has been confirmed here |
| Submission access | An authorized Platform account with Apps Management write access |
| Public policy/contact URLs | Confirmed support, privacy, and terms pages, with the correct publisher/contact details |
| Retention and user controls | Owner-approved treatment of account data, audit records, internal provenance, evidence media, and deletion requests |
| Brand/category | Owner-approved logo and an available portal category |
| Availability | Owner-approved countries/regions; PNG is the product focus, not an automatic distribution selection |
| Review account/data | Dedicated non-admin Contributor credentials and reproducible, approved test data; enter credentials only in the secure portal |
| Domain proof | Exact token issued by the portal; configure the prepared challenge endpoint |
| Client validation | Complete real ChatGPT OAuth, tool-scan, confirmation, reconnection, and mobile tests |

These are gates, not fields to fill with guessed URLs, contacts, promises, or credentials. Do not submit policy attestations until the owner has confirmed them.

## Access and side effects

Active Wikonomi accounts default to Contributor and can read, contribute prices, and create/edit guides. An explicit Reader restriction or disabled access record takes precedence. No account gains Django staff/superuser privileges. Existing tokens remain limited to their previously granted scopes; reconnect to approve new guide permissions.

| Tool group | Required scopes | Read-only | Public side effects | Destructive hint |
|---|---|---|---|---|
| Schema help, search, get product, get guide | `wikonomi:read` | Yes | None | No |
| Find/create product, submit/bulk prices, upload evidence | Read + `wikonomi:write` | No | Public product/price/image contributions | No |
| Create guide | Read + `wikonomi:publish` | No | Publishes a new guide | No |
| Update guide | Read + `wikonomi:publish` | No | Replaces the visible version, retaining history | Yes |

No delete, merge, ownership transfer, verification override, or moderation-bypass tools exist. Contributors can attach evidence only to their own reports and submit at most 25 prices per batch. Staff/owners retain the existing larger batch and evidence-moderation privileges. Pending/rejected guides are not returned by read tools; guides marked for deletion cannot be overwritten.

Read tools do not persist search queries in the MCP audit table. Write attempts are audited. AI provenance remains internal: public pages and retrieval results omit badges, provider/model fields, confidence, and internal source notes. User attribution, dates, evidence, and source links remain public. The read-only `mcp_provenance_stats` command counts stored AI-assisted contributions for internal reporting.

## Data inventory for the privacy disclosure

The implementation stores normal Wikonomi account identifiers; submitted products, prices, dates, business/branch associations, guide text and references; evidence images; and optional AI provider/model/confidence/source notes. OAuth client metadata, encrypted client secrets, hashed tokens, authorization requests, and permission grants support authentication. Write audit entries include user/client/role, the tool, sanitized task arguments, outcome, and timing. Image bytes and token/secret fields are redacted from those audit arguments.

Public content is visible on Wikonomi, including public contributor usernames. Internal provenance, audit records, and authentication secrets are not included in public retrieval output. The MCP server does not request full chats or precise user GPS input; prices can inherit the selected business/branch's existing location.

Hosting and configured object storage also process service data. Confirm the actual processors, retention periods, access/revocation/deletion process, and contact details before publishing the policy. This release does not add an automatic audit/provenance retention purge. Do not promise retention limits the service does not implement.

## Reviewer test plan

Local regression fixtures are isolated and disposable. Before submission, provision a dedicated Contributor account and approved review fixtures, and put the exact IDs and credentials into the portal. Do not use the owner's admin account, publish invented shop prices, or let reviewers depend on access to an internal network or another person's email/MFA.

### Five positive cases

| Case | Prompt / setup | Expected behavior |
|---|---|---|
| P1: Search and read | “Find the approved review product and its latest reported price.” Provide its exact name/ID. | Search then product retrieval; returns links, currency, and dates, not private provenance; no content changes |
| P2: Observed price and retry | Use an owner-approved real observation, product/business IDs, and a fixed idempotency key. Confirm publication, then retry the same operation. | One report attributed to the review account; retry returns the same ID; provenance recorded internally |
| P3: Create a guide | Publish an owner-approved, sourced review guide with at least one step and a stable idempotency key. | Confirmation, then a published guide, step IDs, and references; ordinary account works without admin access |
| P4: Edit own guide | Retrieve P3, then confirm a summary/step correction. | A new published version; original creator retained; previous version and references remain; internal provenance recorded |
| P5: Community edit | Retrieve an approved fixture owned by another consenting review account. Confirm the exact correction and high-impact flag. | A new version attributed to the editor, with the original creator/history preserved |

### Negative cases

| Case | Prompt / setup | Expected behavior |
|---|---|---|
| N1: Missing permission | Use an explicit Reader account or a token without publish scope and request a guide write. | Denied, no guide/version created; no role escalation; reconnect only if the account is actually eligible |
| N2: Missing confirmation | Attempt to edit another author's guide with `confirm_high_impact=false`. | Refusal before mutation; version count unchanged |
| N3: Protected operation | Request deletion/merging, or update a guide marked for deletion. | No destructive management tool exists; marked-guide update is denied |

Additional checks: suspended account cannot authorize/use tokens; unknown and unpublished guide IDs are not disclosed; no invented prices; malformed/oversized images rejected; evidence from another user's report cannot be changed by a Contributor; internal metadata stays absent from public pages.

## Submission sequence

1. Open [the plugin portal](https://platform.openai.com/plugins) in the verified publishing organization. Create a **With MCP** draft using the server URL, not the personal integration ID.
2. Add the approved listing, policies, branding, availability, OAuth details, and dedicated review credentials.
3. Use the portal's exact domain token with `WIKONOMI_OPENAI_APPS_CHALLENGE`. Confirm the well-known endpoint returns that token only.
4. Scan tools after the deployment. Check the imported schema, OAuth scope metadata, and all action annotations.
5. Enter the reproducible test cases and release notes. Complete attestations only when accurate, then submit for review.
6. After approval, use the portal's publication action. Verify the listing and connect from a separate ordinary account.

Suggested release notes: Initial public submission of Wikonomi's OAuth MCP integration. Ordinary active accounts can search public records, contribute observed prices, and create/edit versioned guides. All publishing actions declare their public effect. Explicit restrictions, confirmation requirements, and moderation protections remain enforced. AI provenance is retained for internal reporting without public badges.

## Mobile acceptance checklist

- On the intended iOS/Android account and workspace, locate the published listing and complete Wikonomi OAuth with normal login.
- Search/read a known record, approve a real price submission, and create/edit an approved guide.
- Confirm cancellation prevents a write, denied permissions remain denied, and reconnect/refresh works.
- Test photo input separately: the current evidence tool takes base64, not the native `openai/fileParams` attachment shape. Do not advertise direct phone receipt uploads until a real-client test or a separately validated adapter establishes support.
- Do not confuse a phone controlling an awake desktop through Remote with independent mobile plugin availability. Publication alone is not a completed mobile acceptance test.

Workspace domain-restriction support is not advertised: the current OAuth provider does not implement an OIDC UserInfo endpoint and verified-email scopes for that feature.

## Release verification

The isolated SQLite run of `mcp_server`, `guides`, `core.test_product_pages`, and `core.test_bulk_inventory_import` passes 105 tests. This includes an in-process HTTP test of the real ASGI app: OAuth discovery, dynamic registration, normal account login/consent, PKCE exchange, guide creation/editing, refresh rotation, client-bound revocation, and confidential-client authentication. It makes no network requests or production content changes.

Migration consistency, Django system checks, shell syntax, and whitespace checks pass. The separate legacy `core.test_security` suite has nine failures and two errors; the exact same failing test names reproduce on unchanged `main` at `c763e35993333f55082ca4e5cac50e3ebd20cb40`. These are not a green full-suite result and need separate triage before claiming a complete security review.

## References

Requirements should be rechecked at submission time:

- [OpenAI public submission flow](https://developers.openai.com/plugins/deploy/submission)
- [MCP review requirements](https://developers.openai.com/plugins/deploy/app-review)
- [Plugin guidelines](https://developers.openai.com/plugins/app-guidelines)
- [Tool metadata and file parameter reference](https://developers.openai.com/plugins/reference)
- [Mobile Remote connections](https://learn.chatgpt.com/docs/remote-connections)
