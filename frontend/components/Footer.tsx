import { Separator } from "@/components/ui/separator";

export default function Footer() {
  return (
    <footer className="mt-auto">
      <Separator />
      <div className="container mx-auto px-4 py-6">
        <div className="text-center text-sm text-muted-foreground">
          © 2025 • Cube5 AI
        </div>
      </div>
    </footer>
  );
}
