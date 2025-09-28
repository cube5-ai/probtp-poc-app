import HealthStatus from "@/components/HealthStatus";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-12">
        <div className="max-w-6xl mx-auto space-y-8">
          {/* Header Section */}
          <div className="text-center space-y-4">
            <div className="flex items-center justify-center gap-2 mb-4">
              <Badge variant="outline" className="text-xs font-mono">
                v0.0.1
              </Badge>
              <Badge variant="secondary" className="text-xs">
                Proof of Concept
              </Badge>
            </div>
            <h1 className="text-4xl font-bold tracking-tight">ProBTP POC</h1>
          </div>

          {/* Health Status */}
          <div className="flex justify-center">
            <div className="w-full max-w-md">
              <HealthStatus />
            </div>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
