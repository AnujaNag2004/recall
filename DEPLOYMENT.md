# Deployment

The whole path, in order, using free plans. Allow about an hour. Everything is on free tiers: Supabase, Render, Vercel, Gemini, Groq and Tavily.

**Keep your keys out of Git and out of chat.** Git ignores `.env` files, so local keys stay local. Everywhere else, keys go in each service's dashboard.

Just want your keys in? [SETUP_KEYS.md](SETUP_KEYS.md) is the short version.

## 1. Make two secrets

In the project folder, generate these and save the output somewhere safe. You'll paste them in step 5.

For `CRON_SECRET`:

```bash
openssl rand -hex 32
```

For `TOKEN_ENCRYPTION_KEY`:

```bash
cd apps/api && uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 2. Set up Supabase

- [ ] At [supabase.com/dashboard](https://supabase.com/dashboard), click **New project**. Save the database password. A password of only letters and numbers avoids URL-encoding trouble.
- [ ] Open **SQL Editor** and run each file in `supabase/migrations/`, one at a time, **oldest first**. There are five. Never run anything from `supabase/local/`, which is a stand-in for local testing and will clash with Supabase's own tables.
- [ ] Open **Table Editor** and confirm that `profiles`, `saves` and `recall_cards` exist.
- [ ] Open **Storage**, click **New bucket**, name it `saves`, and leave **Public bucket** off.
- [ ] Under **Authentication > URL Configuration**, set **Site URL** to `http://localhost:3000` and add `http://localhost:3000/auth/callback` to **Redirect URLs**. You'll add the live address in step 7.
- [ ] Note these down: the project URL and publishable key from **Connect** and **Project Settings > API Keys**, the secret key from the same page, and the **Transaction pooler** URI from **Connect**.

Turning off **Confirm email** under **Authentication > Sign In / Providers > Email** makes testing easier, because the built-in email service allows only a few messages an hour. For a public launch, turn it back on and add a custom SMTP provider.

## 3. Get the AI keys

- [ ] Gemini: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- [ ] Groq: [console.groq.com/keys](https://console.groq.com/keys)
- [ ] Tavily: [tavily.com](https://tavily.com)

## 4. Try it locally

Create `apps/web/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=https://YOUR-PROJECT-REF.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=YOUR-PUBLISHABLE-KEY
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Create `.env` in the project root. In the database URI, change the start from `postgresql://` to `postgresql+asyncpg://`, and fill in your password:

```
SUPABASE_URL=https://YOUR-PROJECT-REF.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR-SECRET-KEY
DATABASE_URL=postgresql+asyncpg://USER:YOUR-DB-PASSWORD@YOUR-POOLER-HOST:6543/postgres
CORS_ORIGINS=http://localhost:3000
GEMINI_API_KEY=YOUR-KEY
GROQ_API_KEY=YOUR-KEY
TAVILY_API_KEY=YOUR-KEY
```

Then let Recall choose models from what your keys can use, which fills in the settings:

```bash
make pick-models
```

Then test each provider:

```bash
make check-ai
```

**OK** next to LLM, Embeddings and Search means they work. Then run these in two terminals:

```bash
make dev-api
```

```bash
make dev-web
```

Sign up at http://localhost:3000/signup and save a YouTube link. This is the first time the real AI has run, so this is the test that matters. If something fails, the Smart Card shows why.

## 5. Put it on GitHub

- [ ] Open the folder in VS Code with **File > Open Folder**.
- [ ] Create an **empty** repository at [github.com/new](https://github.com/new), without a README, license or `.gitignore`. Public suits a portfolio.
- [ ] Bring the work onto `main`:

```bash
git switch main
```

```bash
git merge phase-1-auth-shell
```

- [ ] Connect and push, replacing `YOUR-USERNAME`:

```bash
git remote add origin https://github.com/YOUR-USERNAME/recall.git
```

```bash
git push -u origin main
```

- [ ] On GitHub's **Actions** tab, confirm the **CI** workflow passes.

## 6. Deploy the API on Render

- [ ] At [dashboard.render.com](https://dashboard.render.com), click **New > Blueprint** and connect your repository. Render reads `render.yaml`.
- [ ] Fill in the values it asks for. Leave the Google, Upstash and Langfuse ones empty for now.

| Variable | Value |
|---|---|
| `CORS_ORIGINS` | Your Vercel address from step 7. Use a placeholder for now, and update it afterwards. |
| `DATABASE_URL` | The same `postgresql+asyncpg://` URI as your `.env` |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | From step 2 |
| `GEMINI_*`, `GROQ_*`, `TAVILY_API_KEY` | From your `.env` |
| `CRON_SECRET`, `TOKEN_ENCRYPTION_KEY` | From step 1 |

- [ ] After it deploys, open `https://YOUR-API.onrender.com/health/ready`. You should see `{"status":"ok"}`.

The free plan sleeps after inactivity, and the first request can take about a minute. The app explains this while it waits.

## 7. Deploy the web app on Vercel

- [ ] At [vercel.com](https://vercel.com), choose **Add New > Project** and import your repository.
- [ ] Next to **Root Directory**, click **Edit** and choose `apps/web`. This setting is easy to miss, and the build needs it.
- [ ] Add these under **Environment Variables**, then click **Deploy**:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Your project URL |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Your publishable key |
| `NEXT_PUBLIC_API_URL` | `https://YOUR-API.onrender.com` |
| `NEXT_PUBLIC_GITHUB_URL` | Your repository URL (optional, for the footer) |

**Then connect the pieces, using your Vercel address:**

- [ ] On Render, set `CORS_ORIGINS` to `https://YOUR-SITE.vercel.app`. There's no trailing slash.
- [ ] In Supabase under **Authentication > URL Configuration**, set **Site URL** to your Vercel address, and add `https://YOUR-SITE.vercel.app/auth/callback` to **Redirect URLs**.

## 8. Turn on scheduled jobs

These power follow-ups, just-in-time recall, digests and link checks.

- [ ] In your GitHub repository, open **Settings > Secrets and variables > Actions**, and add:

| Secret | Value |
|---|---|
| `RECALL_API_URL` | `https://YOUR-API.onrender.com` |
| `RECALL_CRON_SECRET` | Your `CRON_SECRET` |

- [ ] On the **Actions** tab, open **Scheduled agents**, click **Run workflow**, and confirm it succeeds.

## 9. Check the live site

- [ ] Sign up, and save a YouTube link and a PDF.
- [ ] Accept a suggested step, mark it done, and confirm your score moves in **Insights**.
- [ ] Ask a question in **Ask**, and confirm it cites your save.
- [ ] Run [PageSpeed Insights](https://pagespeed.web.dev) on the landing page.
- [ ] Paste the address into a messaging app to check the preview image.

## Optional extras

**Google sign-in**

- [ ] In [Google Cloud Console](https://console.cloud.google.com/apis/credentials), create an **OAuth client ID** of type **Web application**. Under **Authorized redirect URIs**, add the callback URL shown in Supabase under **Authentication > Sign In / Providers > Google**.
- [ ] Paste the client ID and secret into that Supabase page, and enable the provider.

**Google Calendar**

- [ ] Enable the **Google Calendar API** in the same Google project, and add this second redirect URI: `https://YOUR-API.onrender.com/api/v1/integrations/google/callback`.
- [ ] On Render, set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and `GOOGLE_REDIRECT_URI` (that same URL).
- [ ] Until Google verifies your app, add yourself as a test user on the OAuth consent screen.

**The demo account**

- [ ] In Supabase under **Authentication > Users**, click **Add user**, create a login with a long random password, and tick **Auto Confirm User**.
- [ ] Add `DEMO_EMAIL` to `.env`, then fill it with sample data. Running this again resets it:

```bash
make seed
```

- [ ] On Vercel, add `DEMO_EMAIL` and `DEMO_PASSWORD`, without a `NEXT_PUBLIC_` prefix, and redeploy. The demo button then appears.

Seeded chunks have no embeddings, so in the demo, Ask finds them through full-text search only.

**Shared rate limits and tracing**

- [ ] For limits that hold across server restarts, set `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` from [upstash.com](https://upstash.com).
- [ ] For agent traces, set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` from [langfuse.com](https://langfuse.com).

## If something goes wrong

| What you see | Likely cause |
|---|---|
| Sign-up works, but the app says it can't reach the server | `NEXT_PUBLIC_API_URL` is wrong, or `CORS_ORIGINS` doesn't exactly match your site's address |
| Every API call returns 401 | `SUPABASE_URL` on Render doesn't match your project |
| Every API call returns 503 | `SUPABASE_URL` isn't set on Render |
| A save fails with "… is not set" | A model ID or key is missing. Run `make check-ai`. |
| YouTube saves fail with a transcript message | YouTube sometimes blocks cloud servers. Upload the audio, or paste the text as a note. |
| Uploads fail | The `saves` bucket is missing, or `SUPABASE_SERVICE_ROLE_KEY` isn't set |
| `/health/ready` shows "unavailable" | `DATABASE_URL` is wrong. Check that it starts with `postgresql+asyncpg://` and uses the pooler address. |
