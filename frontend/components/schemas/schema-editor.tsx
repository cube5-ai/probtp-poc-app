/**
 * Schema Editor Component
 * Uses JSONJoy Builder for visual schema editing
 */
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Save, Copy, Download, Upload, Eye, Edit3, Lock } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getSchema, updateSchema, createSchema } from "@/lib/api/schemas";
import type { Schema, SchemaCreateRequest } from "@/types/schema.types";
import { useBreadcrumbs } from "@/contexts/BreadcrumbContext";
import { useAuth } from "@/contexts/AuthContext";

// Import Modern Schema Editor
import { ModernSchemaEditor } from "./modern-schema-editor";

interface SchemaEditorProps {
  schemaId?: string; // If provided, edit existing schema
  cloneFromId?: string; // If provided, clone from existing schema
}

export function SchemaEditor({ schemaId, cloneFromId }: SchemaEditorProps) {
  const router = useRouter();
  const { setBreadcrumbs } = useBreadcrumbs();
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [schema, setSchema] = useState<Schema | null>(null);
  const [schemaName, setSchemaName] = useState("");
  const [schemaDescription, setSchemaDescription] = useState("");
  const [schemaDefinition, setSchemaDefinition] = useState<any>({});
  const [isTemplate, setIsTemplate] = useState(false);
  const [viewMode, setViewMode] = useState<"builder" | "preview">("builder");

  // Check if user can edit this schema - strict ownership only
  const canEdit = !schemaId || (schema && user && schema.userId === user.uid);
  const isReadOnly = !canEdit;

  // Debug ownership check
  useEffect(() => {
    if (schema && user) {
      console.log("Ownership check debug:", {
        schemaUserId: schema.userId,
        schemaUserIdType: typeof schema.userId,
        currentUserId: user.uid,
        currentUserIdType: typeof user.uid,
        areEqual: schema.userId === user.uid,
        canEdit,
        isReadOnly,
      });
    }
  }, [schema, user, canEdit, isReadOnly]);

  // Set breadcrumbs based on editor mode
  useEffect(() => {
    const breadcrumbLabel = schemaId
      ? "Edit Schema"
      : cloneFromId
      ? "Clone Schema"
      : "New Schema";

    setBreadcrumbs([
      { label: "Home", href: "/" },
      { label: "Settings", href: "/settings" },
      { label: breadcrumbLabel },
    ]);
  }, [schemaId, cloneFromId, setBreadcrumbs]);

  // Load schema data
  useEffect(() => {
    const loadSchema = async () => {
      try {
        setLoading(true);

        if (schemaId) {
          // Load existing schema
          console.log("Loading schema:", schemaId);

          // Debug authentication
          console.log("Current user:", user);

          // Check if API client has auth token
          const { apiClient } = await import("@/lib/api/client");
          console.log(
            "API client auth token:",
            apiClient.getAuthToken() ? "SET" : "NOT SET"
          );

          const existingSchema = await getSchema(schemaId);
          console.log("Schema loaded successfully:", existingSchema);
          setSchema(existingSchema);
          setSchemaName(existingSchema.name);
          setSchemaDescription(existingSchema.description || "");
          setSchemaDefinition(existingSchema.schemaDefinition);
          setIsTemplate(existingSchema.isTemplate);
        } else if (cloneFromId) {
          // Clone from existing schema
          console.log("Cloning schema:", cloneFromId);
          const sourceSchema = await getSchema(cloneFromId);
          setSchemaName(`${sourceSchema.name} (Copy)`);
          setSchemaDescription(sourceSchema.description || "");
          setSchemaDefinition(sourceSchema.schemaDefinition);
          setIsTemplate(false);
        } else {
          // Create new schema
          setSchemaName("");
          setSchemaDescription("");
          setSchemaDefinition({});
          setIsTemplate(false);
        }
      } catch (error: any) {
        console.error("Error loading schema:", error);
        console.error("Error details:", {
          status: error?.response?.status,
          statusText: error?.response?.statusText,
          data: error?.response?.data,
          headers: error?.response?.headers,
        });

        if (error?.response?.status === 401) {
          toast.error("Authentication required to load schema.");
        } else if (error?.response?.status === 403) {
          toast.error("You don't have permission to access this schema.");
        } else if (error?.response?.status === 404) {
          toast.error("Schema not found. It may have been deleted.");
        } else if (error?.response?.data?.detail) {
          toast.error(`Error loading schema: ${error.response.data.detail}`);
        } else {
          toast.error("Failed to load schema. Please try again.");
        }

        router.push("/settings");
      } finally {
        setLoading(false);
      }
    };

    loadSchema();
  }, [schemaId, cloneFromId, router]);

  const handleSave = async () => {
    if (!schemaName.trim()) {
      toast.error("Schema name is required");
      return;
    }

    try {
      setSaving(true);

      const schemaData: SchemaCreateRequest = {
        name: schemaName.trim(),
        description: schemaDescription.trim() || undefined,
        schemaDefinition,
        isTemplate,
      };

      if (schemaId) {
        // Update existing schema
        console.log("Updating schema:", schemaId, schemaData);
        const updatedSchema = await updateSchema(schemaId, schemaData);
        setSchema(updatedSchema); // Update local state with the latest data
        toast.success("Schema updated successfully");
        // Stay on the current page for updates
      } else {
        // Create new schema
        console.log("Creating new schema:", schemaData);
        const newSchema = await createSchema(schemaData);
        toast.success("Schema created successfully");
        // Redirect to edit the newly created schema
        router.push(`/settings/schema/${newSchema.id}`);
      }
    } catch (error: any) {
      console.error("Error saving schema:", error);

      // More detailed error handling
      if (error?.response?.status === 401) {
        toast.error("Authentication required. Please sign in again.");
      } else if (error?.response?.status === 403) {
        toast.error("You don't have permission to modify this schema.");
      } else if (error?.response?.status === 404) {
        toast.error("Schema not found. It may have been deleted.");
      } else if (error?.response?.data?.detail) {
        toast.error(`Error: ${error.response.data.detail}`);
      } else if (error?.message) {
        toast.error(`Failed to save schema: ${error.message}`);
      } else {
        toast.error("Failed to save schema. Please try again.");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleExport = () => {
    const dataStr = JSON.stringify(schemaDefinition, null, 2);
    const dataBlob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${schemaName || "schema"}.json`;
    link.click();
    URL.revokeObjectURL(url);
    toast.success("Schema exported");
  };

  const handleImport = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const imported = JSON.parse(e.target?.result as string);
        setSchemaDefinition(imported);
        toast.success("Schema imported successfully");
      } catch (error) {
        toast.error("Invalid JSON file");
      }
    };
    reader.readAsText(file);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(schemaDefinition, null, 2));
    toast.success("Schema copied to clipboard");
  };

  if (loading) {
    return (
      <div className="py-8">
        <div className="space-y-6">
          <div className="h-8 bg-muted animate-pulse rounded w-48" />
          <div className="h-96 bg-muted animate-pulse rounded" />
        </div>
      </div>
    );
  }

  return (
    <div className="py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold">
                {schemaId
                  ? "Edit Schema"
                  : cloneFromId
                  ? "Clone Schema"
                  : "Create Schema"}
              </h1>
              {isReadOnly && (
                <Badge variant="secondary" className="flex items-center gap-1">
                  <Lock className="h-3 w-3" />
                  Read Only
                </Badge>
              )}
            </div>
            <p className="text-muted-foreground mt-1">
              {isReadOnly
                ? "This schema is read-only. Clone it to make changes."
                : schemaId
                ? "Modify your data extraction schema"
                : "Define a new data extraction schema"}
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          <Button variant="outline" onClick={handleCopy}>
            <Copy className="mr-2 h-4 w-4" />
            Copy JSON
          </Button>
          <Button variant="outline" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
          {!isReadOnly && (
            <>
              <Button
                variant="outline"
                onClick={() => document.getElementById("import-file")?.click()}
              >
                <Upload className="mr-2 h-4 w-4" />
                Import
                <input
                  id="import-file"
                  type="file"
                  accept=".json"
                  onChange={handleImport}
                  className="hidden"
                />
              </Button>
              <Button
                onClick={handleSave}
                disabled={saving || !schemaName.trim()}
              >
                <Save className="mr-2 h-4 w-4" />
                {saving ? "Saving..." : "Save Schema"}
              </Button>
            </>
          )}
          {isReadOnly && (
            <Button
              onClick={() =>
                router.push(`/settings/schema/new?cloneFromId=${schemaId}`)
              }
            >
              <Copy className="mr-2 h-4 w-4" />
              Clone to Edit
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Schema Metadata */}
        <div className="lg:col-span-1 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Schema Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="name">Name *</Label>
                <Input
                  id="name"
                  value={schemaName}
                  onChange={(e) => setSchemaName(e.target.value)}
                  placeholder="Enter schema name"
                  disabled={isReadOnly}
                />
              </div>

              <div>
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={schemaDescription}
                  onChange={(e) => setSchemaDescription(e.target.value)}
                  placeholder="Describe what this schema extracts"
                  rows={3}
                  disabled={isReadOnly}
                />
              </div>

              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="isTemplate"
                  checked={isTemplate}
                  onChange={(e) => setIsTemplate(e.target.checked)}
                  className="rounded"
                  disabled={isReadOnly}
                />
                <Label htmlFor="isTemplate">Save as template</Label>
              </div>

              {schema && (
                <div className="space-y-2">
                  <Separator />
                  <div className="text-sm text-muted-foreground">
                    <div>
                      Created: {new Date(schema.createdAt).toLocaleDateString()}
                    </div>
                    <div>
                      Updated: {new Date(schema.updatedAt).toLocaleDateString()}
                    </div>
                    <div>Version: {schema.version}</div>
                    {schema.isTemplate && (
                      <Badge variant="secondary" className="mt-2">
                        Template
                      </Badge>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Schema Builder and Preview Tabs */}
        <div className="lg:col-span-2">
          <Tabs
            value={viewMode}
            onValueChange={(value) =>
              setViewMode(value as "builder" | "preview")
            }
          >
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="builder" className="flex items-center gap-2">
                <Edit3 className="h-4 w-4" />
                Builder
              </TabsTrigger>
              <TabsTrigger value="preview" className="flex items-center gap-2">
                <Eye className="h-4 w-4" />
                Preview
              </TabsTrigger>
            </TabsList>

            <TabsContent value="builder" className="mt-6">
              <Card>
                <CardHeader>
                  <CardTitle>Schema Builder</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Define the fields you'd like to extract from documents
                  </p>
                </CardHeader>
                <CardContent>
                  <ModernSchemaEditor
                    schema={schemaDefinition}
                    onChange={setSchemaDefinition}
                    readOnly={isReadOnly}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="preview" className="mt-6">
              <Card>
                <CardHeader>
                  <CardTitle>Schema Preview</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Preview the generated JSON schema
                  </p>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="bg-muted p-4 rounded-lg">
                      <pre className="text-sm overflow-auto max-h-96">
                        {JSON.stringify(schemaDefinition, null, 2)}
                      </pre>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      This is the JSON schema that will be used for data
                      extraction
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
