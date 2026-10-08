# Composition upload bucket

Create a private R2 bucket for temporary composition inputs. The bucket must not
have a public development URL or custom domain.

Create an R2 Object Read & Write API token scoped to the primary result
bucket, `gifgloo-composition-upload`, and the private processing bucket below. Set its credentials in the
`R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` GitHub Actions secrets, and set
`R2_UPLOAD_BUCKET_NAME` to `gifgloo-composition-upload`. The backend deployment
syncs all three values to the EC2 `.env`, and the `gifgloo-ai-processor`
deployment passes the same values to Lambda.

Apply [`r2-composition-upload-cors.json`](./r2-composition-upload-cors.json) to
the bucket. Add local and preview origins only while testing; production should
keep only `https://gifgloo.com`.

Configure an object lifecycle rule that deletes objects under
`composition-uploads/` after one day. The Lambda deletes consumed objects
immediately, while the lifecycle rule removes uploads abandoned before a
composition request.

For an initial deployment with no existing composition files:

1. Create the private bucket, CORS policy, lifecycle rule, and API-token access.
2. Add the `R2_UPLOAD_BUCKET_NAME` GitHub Actions secret.
3. Configure the private processing bucket below, then deploy both Lambda functions with `bash lambda/deploy.sh all`.
4. Deploy the backend.
5. Deploy the frontend.

## Private processing files and owner-only photo access

Set `R2_PRIVATE_BUCKET_NAME` to a separate private bucket (suggested name:
`gifgloo-composition-private`) in the backend environment and GitHub Actions
secrets. The deployment passes it to both Lambda functions. The application and
Lambdas reject a missing private bucket or one equal to `R2_BUCKET_NAME`.

Keep public development URLs and custom domains disabled on this bucket. It
does not need browser CORS: the backend and Lambdas access it using their R2
credentials. Verify those credentials can read/write this bucket before
deploying. Keep the temporary-upload bucket's PUT CORS and lifecycle unchanged.

| Location | Bucket | Lifecycle |
| --- | --- | --- |
| `composition-uploads/` | Existing upload bucket | Existing 1 day |
| `compositions/{job_id}/target.png`, `draft.png` | Private processing bucket | No new automatic expiry |
| `temp/{job_id}/` | Private processing bucket | Delete after 1 day |
| Legacy `STATIC/{asset_id}` photo copies | Private processing bucket | No new automatic expiry |
| `compositions/{job_id}/result.gif` | Existing public result bucket | Unchanged |

Do not apply a bucket-wide one-day lifecycle to the private processing bucket.
Target photos must remain available when their owner returns. Expiration makes
objects eligible for deletion and is not a guarantee of destruction within 24
hours. A copy of a temporary frame has a new creation time; review its remaining
retention during cutover. Do not make a private bucket public to fix a failed read.

The backend stores new private locations as `r2://{private_bucket}/{key}` in
existing string columns; no schema migration is needed for this change. For
legacy photo/draft records with CDN URLs, the storage adapter extracts the key
and reads **only the private bucket**. It never falls back to public storage.
Composition/asset lists expose an authenticated `/assets/{asset_id}/content`
endpoint instead of a direct photo location. Existing result URLs are unchanged.
The endpoint verifies the current session, owner and asset status, responds with
`Cache-Control: private, no-store`, and is not used on the public shared page.
The frontend fetches photos with credentials and releases temporary blob URLs
when the detail view closes or its session changes.

## Existing-file cutover (not executed by local tests)

Prepare the following as one maintenance operation. The current CI can deploy
the application and Lambda jobs concurrently; merging alone does not perform
this cutover. Keep generation paused throughout the deployment and data check.

1. Provision the private bucket, only its `temp/` lifecycle, credentials and
   `R2_PRIVATE_BUCKET_NAME`. Confirm no public domain/development URL is enabled.
2. Stop accepting new composition requests at the ingress, let active jobs and
   callbacks finish, and verify there are no queued or retried Lambda writes.
   Stop the backend before changing the readers/writers; keep new submissions
   blocked until both Lambdas and the backend run the new version. Do not
   interrupt a paid/in-flight job and declare it successfully migrated.
3. With reviewed R2 environment variables, create a metadata-only inventory:

   ```sh
   python -m tools.migrate_private_composition_files plan --manifest /private/tmp/gifgloo-private-manifest.json
   ```

   The tool does not load `.env` automatically and refuses to overwrite an
   existing manifest. Review the exact source/destination buckets, file count,
   and `unclassified_keys`. Reconcile additional private copies with Asset
   records. Unknown keys are not silently considered safe or deleted. The
   allowlist includes target/draft PNGs, extracted/composited frames and legacy
   STATIC copies; it never includes result GIFs.
4. Copy and compare SHA-256 digests in memory, without storing images locally:

   ```sh
   python -m tools.migrate_private_composition_files copy --manifest /private/tmp/gifgloo-private-manifest.json
   python -m tools.migrate_private_composition_files verify --manifest /private/tmp/gifgloo-private-manifest.json
   ```

   The tool checks source ETag/size against the inventory, does not overwrite an
   existing destination, and stops on changed sources, permission errors or
   different content. It never deletes a source or purges a cache. Its result
   establishes copy integrity, not private access configuration.
5. Deploy both Lambdas (including their packaged `shared/r2_config.py` and
   `shared/exceptions.py`), backend and frontend while submissions remain blocked.
   Verify the backend's authenticated photo endpoint using controlled test assets.
   Check owner/member/anonymous access, rejected foreign and revoked sessions,
   and unchanged result GIF display/download/share. Avoid inspecting unrelated
   user photos. No database rewrite is required for legacy photo URLs.
6. After copy integrity and application checks pass, remove **only the reviewed
   source keys** in the manifest from the public bucket and purge their exact
   CDN URLs. Do not use recursive deletion of `compositions/` or a bucket-wide
   purge. Check that original object keys are absent and former public URLs no
   longer serve bytes, including CDN cache. A 403 alone does not prove deletion.
   Review unclassified paths before marking public exposure resolved.
7. Confirm no old writer can recreate public private files. Run one controlled
   composition smoke test, inspect object placement, and reopen submissions.
   Align the public privacy wording only after this operational verification.

If verification fails before source retirement, keep submissions paused and fix
the private reader/writer or use the preserved source for another verified copy.
After retirement, do not restore photo files to public storage as a rollback.
Result GIFs and the private verified copies remain available for recovery.

Manual deletion requests must now resolve target/draft/temp/STATIC objects in
the private bucket as well as result objects in the public bucket and staging
uploads. An Asset DELETED state still does not physically delete R2 objects.
