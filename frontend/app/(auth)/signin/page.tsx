"use client";

import { useEffect } from "react";
import Link from "next/link";

import Loading from "@/components/common/loading";

import SigninForm from "./signin-form";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";

export default function AuthenticationPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // Redirect to home if already authenticated
    if (user && !loading) {
      router.push("/");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="flex items-center justify-center w-full h-full">
          <Loading />
        </div>
      </div>
    );
  }

  if (user) {
    return null; // Will redirect via useEffect
  }

  return (
    <>
      <div className="relative mx-auto flex items-center text-lg font-medium sm:mx-0 md:hidden gap-2">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-6 w-6"
        >
          <path d="M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3" />
        </svg>
        ProBTP
      </div>
      <div className="flex flex-col">
        <h1 className="text-slate-12 mb-1.5 mt-8 text-center text-xl font-bold tracking-[-0.16px] sm:text-left md:mt-0">
          Log in to ProBTP
        </h1>
      </div>
      <SigninForm />
      <p className="px-8 text-center text-xs text-muted-foreground">
        By signing in, you agree to our{" "}
        <Link
          href="#"
          className="underline underline-offset-4 hover:text-primary"
          target="_blank"
        >
          Terms of Service
        </Link>{" "}
        and{" "}
        <Link
          href="#"
          className="underline underline-offset-4 hover:text-primary"
          target="_blank"
        >
          Privacy Policy
        </Link>
        .
      </p>
    </>
  );
}
