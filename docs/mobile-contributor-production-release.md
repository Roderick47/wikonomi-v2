# Wikonomi mobile contributor — safe production release checklist

**Status:** PR #164 remains draft and has NOT been merged or deployed to production.

## Separation of environments

- Production: Render service `wikonomi-singapore`, production PostgreSQL,
  production R2 bucket `wikonomi-media`.
- Isolated preview: `wikonomi-mobile-staging`, dedicated staging PostgreSQL
  `wikonomi-mobile-staging-db`, private R2 `wikonomi-mobile-staging`.
- **Never** copy staging DATABASE_URL, R2 credentials, users, or demo products
  into production. Production uses its existing product and shop catalog.
- Staging `mobile.0002_staging_pilot_catalog` intentionally does **nothing**
  outside staging and its strictly verified database name/user.

## Automatic safety gate

Production `settings.py` defaults `MOBILE_CONTRIBUTOR_ENABLED=False`.
Public contributor routes at `/app/`, `/app/submit/`, product/branch
search, and private evidence access are HTTP 404 while disabled.
The MobileSubmission database model, migrations, and admin can exist safely
without opening public contributions. CI and isolated staging explicitly set
`MOBILE_CONTRIBUTOR_ENABLED=True`.

## Before merging the feature branch

1. Review the GitHub CI `Mobile contributor backend validation`: SQLite
   migrations/system checks, PostgreSQL tests (including admin moderation),
   Android-sized Chromium screenshots/offline drafts, and staging public smoke.
2. Review PR #164 changed files and confirm no unexpected modifications to
   production DB models, storage config, production environment or routes.
3. In staging, test installation and camera/photo picker on a physical Android
   Chrome device, especially low-end devices and intermittent connectivity.
4. Review a real staging test submission using a staged **staff reviewer**
   account, if one has been safely provisioned. No reviewer credentials should
   be committed to source code or placed in logs.
5. Obtain an up-to-date production database backup/snapshot and confirm the
   recovery process before deploying any migration.
6. Confirm production GitHub/Render mapping: only `main` deploys to
   `wikonomi-singapore`; never repoint its branch to the feature branch.

## Production deployment (only with user authorization)

1. Merge PR #164 into `main` after approval.
2. Let the normal production pipeline apply *additive* migration
   `mobile.0001_initial` and the no-op-on-production
   `mobile.0002_staging_pilot_catalog`. Do not reset or recreate production DB.
3. Verify existing price search, map, guides, product pages, uploads, and
   existing media still function; verify existing user and price totals.
4. Confirm `/app/` responds HTTP 404 while
   `MOBILE_CONTRIBUTOR_ENABLED=False`. No new user submissions should be
   accepted through the new route before the pilot is approved.
5. Assign a suitable reviewer with Django admin `mobile.change_mobilesubmission`
   permission. Staff can inspect evidence in the Admin list and select
   **Approve selected price contributions** or **Reject selected price
   contributions**. Approval preserves original evidence and generates the
   published JPEG. Test with a small, expressly authorized dummy submission.
6. For an approved limited pilot only: set
   `MOBILE_CONTRIBUTOR_ENABLED=True` on the **production** Render service,
   redeploy, and share the production `https://wikonomi.com/app/` link with
   designated contributors. Existing catalog and business records will then be
   available; no database copying is required.
7. Monitor uploads, review queue, media errors, storage usage, 429 rate limits,
   unauthorized access, and failed deploys over the pilot period.

## Reversible public rollout

To close the mobile contributor pages quickly, reset
`MOBILE_CONTRIBUTOR_ENABLED=False` on production and redeploy.
This switches off the new public endpoints without modifying stored prices,
users, existing media, or moderation history. Do not reverse applied migrations
after real contributions exist. Keep normal Wikonomi website workflows intact.

## Known limitations

- The Chrome PWA is **not** an APK or Play Store app.
- Browser/CI camera tests do not replace a physical Android install/camera
  check. Device validation is a distinct release gate.
- Real staging R2 upload/download and persistence across redeploy were verified;
  real staging staff approval has **not** yet been demonstrated through the
  live Django Admin using a privileged staging account.
- The free staging PostgreSQL instance may expire; do not store production data
  or irreplaceable test data there.
- Moderation has a 20-contribution-per-hour per-user guard, not a fully
  distributed abuse prevention system. Restrict an initial pilot accordingly.
