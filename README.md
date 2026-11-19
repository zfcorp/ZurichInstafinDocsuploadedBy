# Instafin document lookup

Deploy the static interface on GitHub Pages and the Python API on Render. The API calls the live Zurich Instafin instance. The browser receives report data and a downloadable workbook. Credentials live on the API service. Colab Secrets are available only inside Colab.

## Deploy

1. Extract the ZIP. Upload its contents to a new GitHub repository on the main branch. Keep the docs directory intact. The repository root should contain app.py and requirements.txt.
2. On Render choose New → Web Service, connect this repository, select Python 3, and leave Root Directory empty. Build command is `pip install -r requirements.txt`. Start command is `gunicorn --bind 0.0.0.0:$PORT --timeout 300 app:app`.
3. In the service environment settings add the four variables below. Deploy the service and copy its HTTPS URL.
4. Edit docs/config.js on GitHub. Set API_ORIGIN to the service URL, for example `const API_ORIGIN = "https://your-service.onrender.com";`. Commit to main.
5. In GitHub Settings → Pages choose Deploy from a branch, main, /docs, then Save. Open the published URL after deployment completes.
6. Enter the report access key and a known client or account ID. Compare the preview against Instafin, then select Download Excel.

Opening the API service root redirects to the GitHub Pages interface. The API endpoint used by the interface is `/lookup`.

| API service variable | Value |
| --- | --- |
| INSTAFIN_USERNAME | Your live API username |
| INSTAFIN_PASSWORD | Your live API password |
| APP_ACCESS_KEY | A new long random access key. Generate one locally with python -c "import secrets; print(secrets.token_urlsafe(32))". Give it only to authorized report operators. |
| PAGES_ORIGIN | The exact site origin, e.g. https://YOUR-OWNER.github.io, without the repository path. Use the custom origin if you configure a custom domain. |

Anyone with the report key can query records visible to the configured API user. Use a read-only account with the intended live-data scope. Keep secrets out of Git, config.js, and GitHub Pages. Rotate the report key in the API service settings when access changes.

## Report behavior

Client-only searches send the client filter from the source script. Account searches resolve the owner via SearchAllAccounts and, on no match, ExportAllAccounts. A supplied client/account pair is checked for the same owner. The report includes client-level documents and documents linked to the selected account, with duplicates removed by document and file ID. Blank account IDs identify client-level files. The preview shows 25 files per page. The workbook includes all ten original columns, raw and readable upload times, and active status. Uploader names appear when Instafin supplies them. A blank name with an uploader ID means the API returned only the ID. Readable times keep the API timestamp's local clock and the raw field preserves its offset.

If the page cannot connect, check API_ORIGIN and PAGES_ORIGIN, then check the service deployment logs. An access-key error comes from the web service. An error naming an Instafin endpoint comes from the upstream lookup. A successful search with zero files supports downloading a headers-only workbook.
