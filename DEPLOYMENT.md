# Deployment

This checklist grows with the project. Backend hosting and scheduled-job steps get added as those phases land.

## Set up Supabase (needed for sign-in, even locally)

**Create the project**

- [ ] At [supabase.com/dashboard](https://supabase.com/dashboard), click **New project**. The free plan is enough. Save the database password you choose.

**Create the tables**

- [ ] Open **SQL Editor** and run each file in `supabase/migrations/`, one at a time, oldest first. Never run anything from `supabase/local/`: that folder is only a stand-in for local testing.
- [ ] Open **Table Editor** and confirm that `profiles`, `workspaces` and `saves` exist.

**Configure sign-in**

- [ ] Under **Authentication > URL Configuration**, set **Site URL** to `http://localhost:3000` and add `http://localhost:3000/auth/callback` to **Redirect URLs**. Add the production versions when you deploy.
- [ ] For local testing, consider turning off **Confirm email** under **Authentication > Sign In / Providers > Email**. The built-in email service allows only a few messages an hour.

**Add the keys**

Create these two files. Git ignores both, so neither gets pushed.

`apps/web/.env.local`, with values from **Project Settings > API Keys** and the project URL from **Connect**:

```
NEXT_PUBLIC_SUPABASE_URL=https://YOUR-PROJECT-REF.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=YOUR-PUBLISHABLE-KEY
NEXT_PUBLIC_API_URL=http://localhost:8000
```

`.env` in the project root. Get the database URI from **Connect > Transaction pooler**, then change its start from `postgresql://` to `postgresql+asyncpg://` and fill in your password:

```
SUPABASE_URL=https://YOUR-PROJECT-REF.supabase.co
DATABASE_URL=postgresql+asyncpg://USER:YOUR-DB-PASSWORD@YOUR-POOLER-HOST:6543/postgres
CORS_ORIGINS=http://localhost:3000
```

**Try it**

- [ ] Run `make dev-api` and `make dev-web` in two terminals, then sign up at http://localhost:3000/signup. You should land on a dashboard that greets you by name.

**Optional: Google sign-in**

- [ ] In [Google Cloud Console](https://console.cloud.google.com/apis/credentials), create an **OAuth client ID** of type **Web application**. Under **Authorized redirect URIs**, add the callback URL shown in Supabase under **Authentication > Sign In / Providers > Google**.
- [ ] Paste the client ID and secret into that Supabase page and enable the provider.

**Optional: the demo account**

- [ ] Under **Authentication > Users**, click **Add user** and create a demo login with a long random password. Tick **Auto Confirm User**.
- [ ] Add `DEMO_EMAIL` and `DEMO_PASSWORD` to `apps/web/.env.local`, and later to Vercel. They're server-only: don't give them a `NEXT_PUBLIC_` prefix.

## 1. Push the code to GitHub

- [ ] Create an **empty** repository at [github.com/new](https://github.com/new). Don't add a README, license or `.gitignore`, since the project already has them. You can make it public or private; a portfolio project is usually public.
- [ ] From the project folder, connect and push, replacing `YOUR-USERNAME`:

```bash
git remote add origin https://github.com/YOUR-USERNAME/recall.git
```

```bash
git push -u origin main
```

- [ ] Open the repository's **Actions** tab and confirm the **CI** workflow passes.

## 2. Deploy the web app on Vercel

- [ ] Sign in at [vercel.com](https://vercel.com) with GitHub. The free Hobby plan is enough.
- [ ] Click **Add New… > Project** and import the `recall` repository.
- [ ] Next to **Root Directory**, click **Edit** and choose `apps/web`. Vercel detects Next.js and the npm workspace from there, so leave the build settings on their defaults.
- [ ] Optional: under **Environment Variables**, add `NEXT_PUBLIC_GITHUB_URL` set to your repository URL, so the footer links to it.
- [ ] Click **Deploy**. Every later push to `main` redeploys automatically.

| Variable | Needed for | Value |
|---|---|---|
| `NEXT_PUBLIC_GITHUB_URL` | Footer GitHub link (optional) | Your repository URL |
| `NEXT_PUBLIC_SITE_URL` | A custom domain (optional) | e.g. `https://recall.example.com`. Without it, Vercel's production domain is used. |

## 3. Check the live site

- [ ] Open the production URL. The hero card should build itself in both light and dark mode.
- [ ] Run [PageSpeed Insights](https://pagespeed.web.dev) on the URL and confirm every category scores 90 or above on mobile.
- [ ] Paste the URL into a messaging app to check the Open Graph preview image.
