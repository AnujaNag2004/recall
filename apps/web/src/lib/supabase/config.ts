export const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
/** Safe to expose: row-level security protects the data, not this key. */
export const supabasePublishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";

/** The landing page deploys fine without Supabase; auth pages then show "opening soon". */
export const isSupabaseConfigured = Boolean(supabaseUrl && supabasePublishableKey);
