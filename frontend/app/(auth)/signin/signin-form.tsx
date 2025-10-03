"use client";

import React from "react";
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

const DEFAULT_AUTH_ERROR_MESSAGE =
  "Unable to sign in. Please check your credentials and try again.";

const AUTH_ERROR_MESSAGES: Record<string, string> = {
  "auth/user-not-found": "Email or password is incorrect.",
  "auth/wrong-password": "Email or password is incorrect.",
  "auth/email-already-in-use": "This email is already registered.",
  "auth/weak-password": "Password must meet the minimum strength requirements.",
  "auth/invalid-email": "Please enter a valid email address.",
  "auth/too-many-requests": "Too many attempts. Please wait and try again.",
};

export default function SigninForm({ className, ...props }: SigninFormProps) {
  const [isLoading, setIsLoading] = React.useState<boolean>(false);
  const [fieldErrors, setFieldErrors] = React.useState<
    Partial<Record<keyof SigninFormData, string>>
  >({});
  const { signIn } = useAuth();
  const router = useRouter();

  // Get error message added by next/auth in URL.
  const searchParams = useSearchParams();
  const error = searchParams?.get("error");

  React.useEffect(() => {
    const errorMessage = Array.isArray(error) ? error.pop() : error;
    if (errorMessage && typeof errorMessage === "string") {
      const message =
        AUTH_ERROR_MESSAGES[errorMessage] ?? DEFAULT_AUTH_ERROR_MESSAGE;
      setFieldErrors((prev) => ({ ...prev, password: message }));
    }
  }, [error]);

  return (
    <div className={cn("grid gap-6", className)} {...props}>
      <form
        action={async (formData) => {
          const result = SigninFormSchema.safeParse(
            Object.fromEntries(formData.entries()),
          );

          if (!result.success) {
            const errors: Partial<Record<keyof SigninFormData, string>> = {};
            for (const issue of result.error.issues) {
              const field = issue.path[0];
              if (typeof field === "string" && !errors[field as keyof SigninFormData]) {
                errors[field as keyof SigninFormData] = issue.message;
              }
            }
            setFieldErrors(errors);
            return;
          }

          const { email, password } = result.data;
          setFieldErrors({});

          try {
            setIsLoading(true);
            await signIn(email, password);
            router.push("/");
          } catch (error) {
            const errorCode =
              error && typeof error === "object" && "code" in error
                ? String((error as { code?: string }).code)
                : undefined;
            const message = errorCode
              ? AUTH_ERROR_MESSAGES[errorCode] ?? DEFAULT_AUTH_ERROR_MESSAGE
              : DEFAULT_AUTH_ERROR_MESSAGE;
            setFieldErrors({ password: message });
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
            {fieldErrors.email ? (
              <p className="mt-1 text-sm text-red-500">{fieldErrors.email}</p>
            ) : null}
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
            {fieldErrors.password ? (
              <p className="mt-1 text-sm text-red-500">{fieldErrors.password}</p>
            ) : null}
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
