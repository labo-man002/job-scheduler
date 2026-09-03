import { Loader2 } from "lucide-react";

export function LoadingState({ text }: { text: string }) {
  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="size-3.5 animate-spin" />
      {text}
    </p>
  );
}
