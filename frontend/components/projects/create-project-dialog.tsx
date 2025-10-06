"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";

interface CreateProjectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (name: string, description?: string) => Promise<void>;
}

export function CreateProjectDialog({
  open,
  onOpenChange,
  onSubmit,
}: CreateProjectDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ name?: string }>({});

  // Validate form
  const validate = () => {
    const newErrors: { name?: string } = {};

    if (!name.trim()) {
      newErrors.name = "Project name is required";
    } else if (name.trim().length < 3) {
      newErrors.name = "Project name must be at least 3 characters";
    } else if (name.trim().length > 255) {
      newErrors.name = "Project name must be less than 255 characters";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) return;

    try {
      setIsSubmitting(true);
      await onSubmit(name.trim(), description.trim() || undefined);

      // Reset form
      setName("");
      setDescription("");
      setErrors({});
      onOpenChange(false);
    } catch (error) {
      console.error("Failed to create project:", error);
      // Error toast handled by parent
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle dialog close
  const handleCancel = () => {
    if (!isSubmitting) {
      setName("");
      setDescription("");
      setErrors({});
      onOpenChange(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={handleCancel}>
      <AlertDialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <AlertDialogHeader>
            <AlertDialogTitle>Create New Project</AlertDialogTitle>
            <AlertDialogDescription>
              Create a project to organize and compare your documents.
            </AlertDialogDescription>
          </AlertDialogHeader>

          <div className="space-y-4 py-4">
            {/* Project Name */}
            <div className="space-y-2">
              <Label htmlFor="project-name">
                Project Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="project-name"
                placeholder="e.g., Q4 RFP Proposals"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  if (errors.name) setErrors({ ...errors, name: undefined });
                }}
                disabled={isSubmitting}
                className={errors.name ? "border-red-500" : ""}
                autoFocus
              />
              {errors.name && (
                <p className="text-sm text-red-500">{errors.name}</p>
              )}
            </div>

            {/* Project Description */}
            <div className="space-y-2">
              <Label htmlFor="project-description">
                Description (Optional)
              </Label>
              <Textarea
                id="project-description"
                placeholder="Describe what this project is for..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={isSubmitting}
                rows={3}
                className="resize-none"
              />
              <p className="text-xs text-gray-500">
                Add context to help you remember what this project is about
              </p>
            </div>
          </div>

          <AlertDialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleCancel}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Spinner className="mr-2 h-4 w-4" />}
              {isSubmitting ? "Creating..." : "Create Project"}
            </Button>
          </AlertDialogFooter>
        </form>
      </AlertDialogContent>
    </AlertDialog>
  );
}
