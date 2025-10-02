/**
 * Edit schema page
 */
"use client";

import { SchemaEditor } from "@/components/schemas/schema-editor";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { use } from "react";

interface EditSchemaPageProps {
  params: Promise<{ id: string }>;
}

export default function EditSchemaPage({ params }: EditSchemaPageProps) {
  const { id } = use(params);
  return (
    <ProtectedRoute>
      <SchemaEditor schemaId={id} />
    </ProtectedRoute>
  );
}
