/**
 * Schema card component
 * Displays a single schema in a card format
 */
"use client";

import { useState } from "react";
import { MoreVertical, Copy, Edit, Trash2, FileJson } from "lucide-react";
import { format } from "date-fns";
import type { Schema } from "@/types/schema.types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Spinner } from "@/components/ui/spinner";

interface SchemaCardProps {
  schema: Schema;
  currentUserId?: string; // Current user ID for ownership checks
  onClick?: (schema: Schema) => void;
  onEdit?: (schema: Schema) => void;
  onDelete?: (schemaId: string) => void;
  onClone?: (schema: Schema) => void;
}

export function SchemaCard({
  schema,
  currentUserId,
  onClick,
  onEdit,
  onDelete,
  onClone,
}: SchemaCardProps) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Check if current user owns this schema
  const isOwner = currentUserId && schema.userId === currentUserId;

  // Allow deletion if user owns the schema (even if it's a template)
  const canDelete = isOwner;

  // Count fields in schema definition
  const fieldCount = schema.schemaDefinition?.properties
    ? Object.keys(schema.schemaDefinition.properties).length
    : 0;

  const handleDelete = async () => {
    if (!onDelete) return;

    try {
      setIsDeleting(true);
      await onDelete(schema.id);
      setShowDeleteDialog(false);
    } catch (error) {
      // Error handling is done in the parent component
      console.error("Error deleting schema:", error);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <Card
        className="hover:shadow-lg transition-shadow cursor-pointer"
        onClick={() => onClick?.(schema)}
      >
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <CardTitle className="text-lg truncate flex-1">
                  {schema.name}
                </CardTitle>
                {schema.isTemplate && (
                  <Badge variant="secondary" className="text-xs flex-shrink-0">
                    Template
                  </Badge>
                )}
              </div>
              <CardDescription className="line-clamp-2">
                {schema.description || "No description provided"}
              </CardDescription>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={(e) => e.stopPropagation()}
                >
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {onEdit && (
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      onEdit(schema);
                    }}
                  >
                    <Edit className="mr-2 h-4 w-4" />
                    Edit
                  </DropdownMenuItem>
                )}
                {onClone && (
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      onClone(schema);
                    }}
                  >
                    <Copy className="mr-2 h-4 w-4" />
                    Clone
                  </DropdownMenuItem>
                )}
                {onDelete && canDelete && (
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowDeleteDialog(true);
                    }}
                    className="text-destructive"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </CardHeader>

        <CardContent>
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1">
                <FileJson className="h-4 w-4" />
                <span>{fieldCount} fields</span>
              </div>
              <div>v{schema.version}</div>
            </div>
            <div>{format(new Date(schema.updatedAt), "MMM d, yyyy")}</div>
          </div>
        </CardContent>
      </Card>

      <AlertDialog
        open={showDeleteDialog}
        onOpenChange={(open) =>
          !open && !isDeleting && setShowDeleteDialog(false)
        }
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Schema</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{schema.name}&quot;? This
              action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground"
            >
              {isDeleting && <Spinner className="mr-2 h-4 w-4" />}
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
