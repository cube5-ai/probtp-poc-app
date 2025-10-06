"use client";

import { useEffect, useRef, useState } from "react";
import * as z from "zod";
import { LoaderCircleIcon, Mail } from "lucide-react";

import { ProtectedRoute } from "@/components/auth/protected-route";
import { useAuth } from "@/contexts/AuthContext";
import { useBreadcrumbs } from "@/contexts/BreadcrumbContext";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

const PasswordSchema = z
  .object({
    currentPassword: z
      .string()
      .min(6, { message: "Current password must be at least 6 characters." }),
    newPassword: z
      .string()
      .min(8, {
        message: "New password must be at least 8 characters.",
      }),
    confirmPassword: z.string(),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    path: ["confirmPassword"],
    message: "New passwords do not match.",
  });

type PasswordFormData = z.infer<typeof PasswordSchema>;

type FieldErrors = Partial<Record<keyof PasswordFormData, string>>;

const PASSWORD_ERROR_MESSAGES: Record<string, string> = {
  "auth/wrong-password": "The current password you entered is incorrect.",
  "auth/weak-password": "Choose a stronger password with at least 8 characters.",
  "auth/requires-recent-login":
    "For security reasons, please sign in again before changing your password.",
  "auth/too-many-requests":
    "Too many attempts. Please wait a moment and try again.",
};

const DEFAULT_ERROR_MESSAGE =
  "We couldn't update your password. Please try again or contact support if the issue persists.";

export default function ProfilePage() {
  const { user, changePassword } = useAuth();
  const { setBreadcrumbs } = useBreadcrumbs();
  const formRef = useRef<HTMLFormElement>(null);

  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formMessage, setFormMessage] = useState<
    { type: "success" | "error"; text: string } | undefined
  >(undefined);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setBreadcrumbs([
      { label: "Projects", href: "/projects" },
      { label: "Profile" },
    ]);
  }, [setBreadcrumbs]);

  const handleSubmit = async (formData: FormData) => {
    const result = PasswordSchema.safeParse(
      Object.fromEntries(formData.entries())
    );

    if (!result.success) {
      const errors: FieldErrors = {};
      result.error.issues.forEach((issue) => {
        const field = issue.path[0];
        if (typeof field === "string" && !errors[field as keyof PasswordFormData]) {
          errors[field as keyof PasswordFormData] = issue.message;
        }
      });
      setFieldErrors(errors);
      setFormMessage(undefined);
      return;
    }

    const { currentPassword, newPassword } = result.data;

    setIsSubmitting(true);
    setFieldErrors({});
    setFormMessage(undefined);

    try {
      await changePassword(currentPassword, newPassword);
      setFormMessage({
        type: "success",
        text: "Your password has been updated successfully.",
      });
      formRef.current?.reset();
    } catch (error) {
      const errorCode =
        error && typeof error === "object" && "code" in error
          ? String((error as { code?: string }).code)
          : undefined;

      const message =
        (errorCode && PASSWORD_ERROR_MESSAGES[errorCode]) || DEFAULT_ERROR_MESSAGE;

      setFormMessage({ type: "error", text: message });

      if (errorCode === "auth/wrong-password") {
        setFieldErrors({ currentPassword: PASSWORD_ERROR_MESSAGES[errorCode] });
      } else if (errorCode === "auth/weak-password") {
        setFieldErrors({ newPassword: PASSWORD_ERROR_MESSAGES[errorCode] });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <ProtectedRoute>
      <div className="py-8 space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Profile</h1>
          <p className="text-muted-foreground mt-1">
            Manage your account details and update your password.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Account Information</CardTitle>
              <CardDescription>Your current sign-in details.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-xs uppercase text-muted-foreground">
                  Email
                </Label>
                <div className="mt-2 flex items-center gap-2 rounded-md border px-3 py-2 bg-muted/50">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">
                    {user?.email ?? "Not available"}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Change Password</CardTitle>
              <CardDescription>
                Enter your current password and choose a new one.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {formMessage ? (
                <div
                  className={`mb-4 rounded-md border px-4 py-3 text-sm ${
                    formMessage.type === "success"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : "border-red-200 bg-red-50 text-red-700"
                  }`}
                >
                  {formMessage.text}
                </div>
              ) : null}

              <form
                ref={formRef}
                action={async (formData) => {
                  await handleSubmit(formData);
                }}
              >
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="currentPassword">Current password</Label>
                    <Input
                      id="currentPassword"
                      name="currentPassword"
                      type="password"
                      className="mt-2"
                      autoComplete="current-password"
                      disabled={isSubmitting}
                    />
                    {fieldErrors.currentPassword ? (
                      <p className="mt-1 text-sm text-red-500">
                        {fieldErrors.currentPassword}
                      </p>
                    ) : null}
                  </div>

                  <div>
                    <Label htmlFor="newPassword">New password</Label>
                    <Input
                      id="newPassword"
                      name="newPassword"
                      type="password"
                      className="mt-2"
                      autoComplete="new-password"
                      disabled={isSubmitting}
                    />
                    {fieldErrors.newPassword ? (
                      <p className="mt-1 text-sm text-red-500">
                        {fieldErrors.newPassword}
                      </p>
                    ) : null}
                  </div>

                  <div>
                    <Label htmlFor="confirmPassword">Confirm new password</Label>
                    <Input
                      id="confirmPassword"
                      name="confirmPassword"
                      type="password"
                      className="mt-2"
                      autoComplete="new-password"
                      disabled={isSubmitting}
                    />
                    {fieldErrors.confirmPassword ? (
                      <p className="mt-1 text-sm text-red-500">
                        {fieldErrors.confirmPassword}
                      </p>
                    ) : null}
                  </div>

                  <Button type="submit" disabled={isSubmitting} className="w-full">
                    {isSubmitting && (
                      <LoaderCircleIcon className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    Update password
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </ProtectedRoute>
  );
}

