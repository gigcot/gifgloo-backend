# Composition upload bucket

Create a private R2 bucket for temporary composition inputs. The bucket must not
have a public development URL or custom domain.

Set `R2_UPLOAD_BUCKET_NAME=gifgloo-composition-upload` in the FastAPI environment
and add a GitHub Actions secret named `R2_UPLOAD_BUCKET_NAME` with the same value
for the `gifgloo-ai-processor` deployment. The existing R2 API token must have
object read, write, and delete access to this bucket.

Apply [`r2-composition-upload-cors.json`](./r2-composition-upload-cors.json) to
the bucket. Add local and preview origins only while testing; production should
keep only `https://gifgloo.com`.

Configure an object lifecycle rule that deletes objects under
`composition-uploads/` after one day. The Lambda deletes consumed objects
immediately, while the lifecycle rule removes uploads abandoned before a
composition request.

Deploy in this order:

1. Create the private bucket, CORS policy, lifecycle rule, and API-token access.
2. Set `R2_UPLOAD_BUCKET_NAME` on FastAPI.
3. Deploy `gifgloo-ai-processor` with `bash lambda/deploy.sh ai`.
4. Deploy the backend.
5. Deploy the frontend.
