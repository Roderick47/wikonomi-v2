# Wikonomi contributor Android staging pilot

Staging: https://wikonomi-mobile-staging.onrender.com/app/

## Isolation and safety

- Staging is NOT wikonomi.com; do not sign in with production credentials.
- Use a new staging-only username, email and strong password at
  https://wikonomi-mobile-staging.onrender.com/users/signup/?next=/app/
- A staging-only migration seeds **Wikonomi Demo Rice 1kg** and
  **Wikonomi Demo Shop**. Never submit real customer data or private images.
- Only the private `wikonomi-mobile-staging` R2 bucket may be enabled for
  persistent photos. Until configured, staging images remain ephemeral.
- Staging database is a free instance and expires on November 14, 2026.
  Renew/upgrade it or export test data before expiration.

## Android Chrome checks

1. On an Android phone, open the staging URL in current Chrome.
2. Sign up for a new **staging-only** account. Finish the welcome page.
3. Open /app/; confirm bottom Home/Submit/My prices tabs, and **Snap a price**.
4. In Chrome's menu, choose **Install app** (or **Add to Home screen**).
   Confirm an app icon and standalone launch. Android/Chrome vary in UI labels.
5. Tap **Snap a price**. Use the rear camera to photograph a **non-sensitive demo
   price tag**, or select a synthetic image.
6. Search for **Wikonomi Demo Rice** and choose that product. Search for
   **Wikonomi Demo Shop** and select that branch. Enter **K12.50**.
7. Tap **Save draft**, navigate to Home and open the draft. Check that the
   photo, product, store and PGK amount survive navigation.
8. Turn on Airplane mode. From the form tap Submit; the draft should save,
   not attempt an upload. Turn data back on, reopen and submit.
9. Verify confirmation, status **Pending review**, and **View price-tag
   photo** displays the correct original for this account.
10. Leave/close and reopen the installed app. Ensure navigation, offline
    fallback when disconnected, and sign-in behavior are understandable.
11. If available, have an authorized staging reviewer approve the pending
    contribution in Django Admin. Confirm approved amount and JPG output.
12. With persistent staging R2 enabled, verify the uploaded photo still opens
    after a staging service restart.

## Separate private Cloudflare R2 storage (needs your Cloudflare access)

1. Cloudflare Dashboard > R2 Object Storage > Create bucket:
   `wikonomi-mobile-staging`. Keep public bucket access **disabled**.
2. R2 > Manage R2 API tokens > create a token with **Object Read & Write**
   limited **only** to this bucket. Do not use the production API token.
3. Render Dashboard > `wikonomi-mobile-staging` > Environment, add all four
   variables together:
   - `STAGING_R2_ACCESS_KEY_ID` — from the new staging-only R2 token
   - `STAGING_R2_SECRET_ACCESS_KEY` — from the new staging-only R2 token
   - `STAGING_R2_ENDPOINT_URL` — `https://<CLOUDFLARE_ACCOUNT_ID>.r2.cloudflarestorage.com`
   - `STAGING_R2_BUCKET_NAME` — exactly `wikonomi-mobile-staging`
4. Save and redeploy the **staging** Render service only. Never copy production
   AWS credentials, production bucket name, or public media domain.
5. Review /app/staging-db-status/: `staging_media_configured` should become
   true. This flag only confirms configuration; complete an actual image
   upload/download and service restart to verify bucket access and persistence.
6. Keep secrets in Render environment variables, never in GitHub or chat.

## QA evidence

GitHub Actions workflow `mobile-checks.yml` validates isolated SQLite and
PostgreSQL flows, mocked S3 storage, Android-sized Chromium browser submission,
and public staging endpoints. Screenshots are attached to each browser test run.

**No native APK exists yet.** This is an installable Android browser PWA;
a Play Store release / TWA package comes later after the pilot.
