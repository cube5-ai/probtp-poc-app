"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useBreadcrumbs } from "@/contexts/BreadcrumbContext";

import HealthStatus from "@/components/HealthStatus";
import { Badge } from "@/components/ui/badge";
import Loading from "@/components/common/loading";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { setBreadcrumbs } = useBreadcrumbs();

  // Set breadcrumbs for the home page
  useEffect(() => {
    setBreadcrumbs([{ label: "Projects" }]);
  }, [setBreadcrumbs]);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/signin");
    } else if (!loading && user) {
      // Redirect authenticated users to projects
      router.push("/projects");
    }
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center w-full h-full min-h-[50vh]">
        <Loading />
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="py-12">
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
  );
}
