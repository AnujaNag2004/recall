import type { Metadata } from "next";
import Link from "next/link";
import { Contact, LAST_UPDATED } from "../contact";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "What Recall stores, why, who processes it, and how to export or delete it.",
};

export default function PrivacyPage() {
  return (
    <article>
      <h1>Privacy Policy</h1>
      <p>Last updated {LAST_UPDATED}.</p>
      <p>
        Recall turns the links, videos, documents and notes you save into summaries, tasks and
        reminders. This page explains what that involves for your data, in plain language.
      </p>

      <h2>What we store</h2>
      <ul>
        <li>
          <strong>Your account:</strong> your email address and name. If you sign in with Google,
          we receive your name, email address and profile picture from Google, and nothing else.
        </li>
        <li>
          <strong>What you save:</strong> the links, files and notes you add, the text we extract
          from them, and what Recall generates from them, such as summaries, tasks, recall cards and
          answers.
        </li>
        <li>
          <strong>How you use it:</strong> your settings, completed tasks and review history, which
          power your insights and schedules.
        </li>
        <li>
          <strong>Google Calendar, only if you connect it:</strong> an encrypted access token, used
          only to add the events you ask for. You can disconnect it at any time.
        </li>
      </ul>

      <h2>How we use it</h2>
      <p>
        Only to run Recall for you. We don&apos;t sell your data, show you ads, or train our own
        models on it.
      </p>

      <h2>Who processes it</h2>
      <p>Recall relies on these services to work:</p>
      <ul>
        <li>Supabase, for sign-in, the database and file storage</li>
        <li>Vercel and Render, which host the website and the server</li>
        <li>
          Google Gemini and Groq, which read the content you save to produce summaries, tasks and
          answers
        </li>
        <li>Tavily, which looks up official links for things mentioned in your saves</li>
      </ul>
      <p>
        Each handles data under its own terms. Content you save is sent to the AI providers so
        they can process it, and on free plans a provider may use what it receives to improve its
        own services. Avoid saving anything you wouldn&apos;t want processed this way.
      </p>

      <h2>Who can see it</h2>
      <p>
        Only you, and the members of any shared workspace you create or join. Access rules are
        enforced by the database itself, not just by the app.
      </p>

      <h2>Your choices</h2>
      <ul>
        <li>
          <strong>Export:</strong> download all your data as JSON from{" "}
          <Link href="/settings">Settings</Link>.
        </li>
        <li>
          <strong>Delete:</strong> deleting your account in Settings permanently removes your
          account, every workspace you own, and the saves and files in them.
        </li>
        <li>
          <strong>Cookies:</strong> we use only the cookies needed to keep you signed in. There are
          no tracking or advertising cookies.
        </li>
      </ul>

      <h2>Changes and contact</h2>
      <p>
        If this policy changes, the date above will change too. For questions or requests, contact{" "}
        <Contact />.
      </p>
    </article>
  );
}
