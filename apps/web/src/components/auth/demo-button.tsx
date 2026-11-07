import { signInToDemo } from "@/app/(auth)/actions";
import { SubmitButton } from "./fields";

export function DemoButton({ primary = false }: { primary?: boolean }) {
  return (
    <form action={signInToDemo} className={primary ? undefined : "mt-3"}>
      <SubmitButton variant={primary ? "default" : "secondary"}>
        Continue with demo account
      </SubmitButton>
    </form>
  );
}
