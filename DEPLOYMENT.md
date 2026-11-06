# Deployment

This checklist grows with the project. Right now only the landing page is deployed, which needs no API keys. Backend, Supabase and scheduled-job steps get added as those phases land.

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
