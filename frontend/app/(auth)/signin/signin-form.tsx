"use client";

import React from "react";
import { toast } from "sonner";
import { useRouter, useSearchParams } from "next/navigation";
import { LoaderCircleIcon } from "lucide-react";
import * as z from "zod";

import { cn } from "@/lib/utils";

import { useAuth } from "@/contexts/AuthContext";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const SigninFormSchema = z.object({
  email: z.email({
    message: "Invalid email address.",
  }),
  password: z.string().min(6, {
    message: "Password must be at least 6 characters.",
  }),
});

type SigninFormData = z.infer<typeof SigninFormSchema>;

type SigninFormProps = React.HTMLAttributes<HTMLDivElement>

export default function SigninForm({ className, ...props }: SigninFormProps) {
  const [isLoading, setIsLoading] = React.useState<boolean>(false);
  const { signIn } = useAuth();
  const router = useRouter();

  // Get error message added by next/auth in URL.
  const searchParams = useSearchParams();
  const error = searchParams?.get("error");

  React.useEffect(() => {
    const errorMessage = Array.isArray(error) ? error.pop() : error;
    if (errorMessage && typeof errorMessage === "string") {
      switch (errorMessage) {
        case 'auth/user-not-found':
          toast.error('No account found with this email');
          break;
        case 'auth/wrong-password':
          toast.error('Incorrect password');
          break;
        case 'auth/email-already-in-use':
          toast.error('Email is already registered');
          break;
        case 'auth/weak-password':
          toast.error('Password is too weak');
          break;
        case 'auth/invalid-email':
          toast.error('Invalid email address');
          break;
        case 'auth/too-many-requests':
          toast.error('Too many failed attempts. Please try again later');
          break;
        default:
          toast.error(errorMessage || 'Authentication failed');
          break;
      }
    }
  }, [error]);

  return (
    <div className={cn("grid gap-6", className)} {...props}>
      <form
        action={async (formData) => {
          const { email, password } = SigninFormSchema.parse(
            Object.fromEntries(formData.entries()),
          ) satisfies SigninFormData;

          try {
            setIsLoading(true);
            await signIn(email, password);
            router.push("/");
          } catch (error) {
            if (error instanceof Error && 'code' in error) {
              router.replace(`?error=${error.code}`);
            }
          } finally {
            setIsLoading(false);
          }
        }}
      >
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-full">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              name="email"
              className="mt-2"
              placeholder="jay.raven@example.com"
              type="email"
              autoCapitalize="none"
              autoComplete="email"
              autoCorrect="off"
              disabled={isLoading}
            />
          </div>
          <div className="col-span-full">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              name="password"
              className="mt-2"
              placeholder="••••••••••••"
              type="password"
              autoCapitalize="none"
              autoComplete="password"
              autoCorrect="off"
              disabled={isLoading}
            />
          </div>
          <Button className="col-span-full mt-4" disabled={isLoading}>
            {isLoading && <LoaderCircleIcon className="h-4 w-4 animate-spin" />}
            Sign In
          </Button>
        </div>
      </form>
    </div>
  );
}
