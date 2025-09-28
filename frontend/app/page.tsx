"use client";

import { useAuth } from "@/contexts/AuthContext";

import HealthStatus from "@/components/HealthStatus";
import { Badge } from "@/components/ui/badge";
import Footer from "@/components/Footer";
import Loading from "@/components/common/loading";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export default function Home() {
  const { user, loading, signOut } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/signin");
    }
  }, [loading, user]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="flex items-center justify-center w-full h-full">
          <Loading />
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

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

          {/* Sign Out */}
          <div className="flex justify-center">
            <Button onClick={signOut}>Sign Out</Button>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
