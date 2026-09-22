# Composition upload bucket

Create a private R2 bucket for temporary composition inputs. The bucket must not
have a public development URL or custom domain.

Add a GitHub Actions secret named `R2_UPLOAD_BUCKET_NAME` with the value
`gifgloo-composition-upload`. The backend deployment syncs it to the EC2 `.env`,
and the `gifgloo-ai-processor` deployment passes the same value to Lambda. The
existing R2 API token must have object read, write, and delete access to this
bucket.

Apply [`r2-composition-upload-cors.json`](./r2-composition-upload-cors.json) to
the bucket. Add local and preview origins only while testing; production should
keep only `https://gifgloo.com`.

Configure an object lifecycle rule that deletes objects under
`composition-uploads/` after one day. The Lambda deletes consumed objects
immediately, while the lifecycle rule removes uploads abandoned before a
composition request.

Deploy in this order:

1. Create the private bucket, CORS policy, lifecycle rule, and API-token access.
2. Add the `R2_UPLOAD_BUCKET_NAME` GitHub Actions secret.
3. Deploy `gifgloo-ai-processor` with `bash lambda/deploy.sh ai`.
4. Deploy the backend.
5. Deploy the frontend.
