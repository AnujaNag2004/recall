# Adding your keys

This is the short version: where each key comes from, and exactly where it goes. [DEPLOYMENT.md](DEPLOYMENT.md) covers putting the site online.

**Your keys are private.** Only put them in the two files below, which Git ignores so they can't be pushed. Don't paste them into chat.

## Do I need to create JWT keys?

**No.** Supabase creates and rotates the signing keys for your project. Recall fetches the public half by itself, using your project URL, and checks every token against it. There's no JWT key to generate, copy or look after, and no cluster to run or supervise: Supabase runs the database and sign-in for you.

`SUPABASE_JWT_SECRET` is only for older Supabase projects that still use a shared secret. On a new project, leave it out.

## 1. Create a Supabase project

At [supabase.com/dashboard](https://supabase.com/dashboard), click **New project**. Choose a database password of only letters and numbers, and save it. Then:

- Open **SQL Editor** and run each file in `supabase/migrations/`, oldest first. There are five.
- Open **Storage**, click **New bucket**, name it `saves`, and leave **Public bucket** off.
- Under **Authentication > URL Configuration**, set **Site URL** to `http://localhost:3000` and add `http://localhost:3000/auth/callback` to **Redirect URLs**.
- Under **Authentication > Sign In / Providers > Email**, turn off **Confirm email** while testing.

## 2. Get your AI keys

| Key | Where | Needed? |
|---|---|---|
| Gemini | [aistudio.google.com/apikey](https://aistudio.google.com/apikey): click **Create API key** | Yes. It does the AI work and search embeddings. |
| Groq | [console.groq.com/keys](https://console.groq.com/keys) | For audio and video transcription, and as a backup when Gemini is busy |
| Tavily | [tavily.com](https://tavily.com) | For finding verified links, and web answers |

## 3. Put them in two files

Create **`apps/web/.env.local`**:

```
NEXT_PUBLIC_SUPABASE_URL=https://YOUR-PROJECT-REF.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=your publishable key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Create **`.env`** in the main project folder:

```
SUPABASE_URL=https://YOUR-PROJECT-REF.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your secret key
DATABASE_URL=postgresql+asyncpg://USER:YOUR-DB-PASSWORD@YOUR-POOLER-HOST:6543/postgres
CORS_ORIGINS=http://localhost:3000
GEMINI_API_KEY=your Gemini key
GROQ_API_KEY=your Groq key
TAVILY_API_KEY=your Tavily key
```

| Value | Where in Supabase |
|---|---|
| Project URL | **Connect**, or **Project Settings > API** |
| Publishable key and secret key | **Project Settings > API Keys** |
| `DATABASE_URL` | **Connect > Transaction pooler**. Change the start from `postgresql://` to `postgresql+asyncpg://`, and put in your password. |

## 4. Let Recall choose the models

Model names change often, so this asks Gemini and Groq what your keys can use, and fills in the settings. It never overwrites anything you've set.

```bash
make pick-models
```

Then test each service. You want to see **OK** beside each one:

```bash
make check-ai
```

## 5. Start it

Run these in two terminals:

```bash
make dev-api
```

```bash
make dev-web
```

Sign up at http://localhost:3000/signup, then paste a YouTube link in **Inbox**, and watch the card build itself.

## If something fails

| What you see | What to do |
|---|---|
| The sign-up page says "opening soon" | `apps/web/.env.local` is missing or misnamed. Restart `make dev-web` after creating it. |
| "We can't reach the server" | `make dev-api` isn't running, or `DATABASE_URL` is wrong |
| A save fails, saying a setting "is not set" | Run `make pick-models` again, then restart `make dev-api` |
| `make check-ai` shows FAIL for the LLM | The key is wrong, or the free quota is used up. Try again later, or check [your Gemini usage](https://aistudio.google.com). |

More answers are at the end of [DEPLOYMENT.md](DEPLOYMENT.md).
