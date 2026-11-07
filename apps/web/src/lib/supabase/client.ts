import { createBrowserClient } from "@supabase/ssr";
import { supabasePublishableKey, supabaseUrl } from "./config";

/** The browser Supabase client. `createBrowserClient` reuses one instance per page. */
export function createClient() {
  return createBrowserClient(supabaseUrl, supabasePublishableKey);
}
