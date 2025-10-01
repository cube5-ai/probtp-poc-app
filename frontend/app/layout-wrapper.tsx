"use client";

import { usePathname } from "next/navigation";
import { Navbar } from "@/components/navbar";
import Footer from "@/components/Footer";
import {
  BreadcrumbProvider,
  useBreadcrumbs,
} from "@/contexts/BreadcrumbContext";

// Inner wrapper that has access to breadcrumb context
function LayoutContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { breadcrumbs } = useBreadcrumbs();

  // Check if we're on an auth page (signin, signup, etc.)
  const isAuthPage =
    pathname?.startsWith("/signin") || pathname?.startsWith("/signup");

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
