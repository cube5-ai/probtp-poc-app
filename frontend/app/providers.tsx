"use client";

import { ThemeProvider } from "next-themes";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { AppProgressProvider as ProgressProvider } from "@bprogress/next";

// import { ReactQueryClientProvider } from "@/components/providers/react-query-client-provider";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from '@/contexts/AuthContext';

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ProgressProvider height="4px" color="#0033cc" options={{ showSpinner: true }} shallowRouting>
      <NuqsAdapter>
        <AuthProvider>
          <ThemeProvider
            attribute="class"
            defaultTheme="system"
            enableSystem
            disableTransitionOnChange
          >
            {/* <ReactQueryClientProvider> */}
            <Toaster />
            {children}
            {/* </ReactQueryClientProvider> */}
          </ThemeProvider>
        </AuthProvider>
      </NuqsAdapter>
    </ProgressProvider>
  );
}
