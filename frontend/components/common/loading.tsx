import { Loader2Icon } from "lucide-react";

export default function Loading() {
  return (
    <div className="flex w-full items-center justify-center p-4 lg:p-8">
      <Loader2Icon className="h-8 w-8 animate-spin" />
    </div>
  );
}
