/**
 * Create new schema page
 */
"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { SchemaEditor } from "@/components/schemas/schema-editor";
import { ProtectedRoute } from "@/components/auth/protected-route";

function NewSchemaContent() {
  const searchParams = useSearchParams();
  const cloneFromId = searchParams.get("cloneFromId") || undefined;

  return <SchemaEditor cloneFromId={cloneFromId} />;
}

export default function NewSchemaPage() {
  return (
    <ProtectedRoute>
      <Suspense fallback={<div>Loading...</div>}>
        <NewSchemaContent />
      </Suspense>
    </ProtectedRoute>
  );
}
