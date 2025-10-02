"use client";

import { usePathname } from "next/navigation";
import { Navbar } from "@/components/navbar";
import Footer from "@/components/Footer";
import {
  BreadcrumbProvider,
  useBreadcrumbs,
} from "@/contexts/BreadcrumbContext";
import { useAuth } from "@/contexts/AuthContext";

// Inner wrapper that has access to breadcrumb context
function LayoutContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { breadcrumbs } = useBreadcrumbs();
  const { loading } = useAuth();

  // Check if we're on an auth page (signin, signup, etc.)
  const isAuthPage =
    pathname?.startsWith("/signin") || pathname?.startsWith("/signup");

  // Check if we're on a protected route (settings pages)
  const isProtectedRoute = pathname?.startsWith("/settings");

  // Show loading state for protected routes while auth is loading
  if (loading && isProtectedRoute) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // Don't render navbar/footer on auth pages
  if (isAuthPage) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar breadcrumbs={breadcrumbs} />
      <div className="flex-1">
        <div className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8">
          {children}
        </div>
      </div>
      <Footer />
    </div>
  );
}

// Wrapper component that conditionally renders navbar and footer based on the current route
export function LayoutWrapper({ children }: { children: React.ReactNode }) {
  return (
    <BreadcrumbProvider>
      <LayoutContent>{children}</LayoutContent>
    </BreadcrumbProvider>
  );
}
