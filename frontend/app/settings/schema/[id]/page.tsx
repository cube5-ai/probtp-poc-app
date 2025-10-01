/**
 * Edit schema page
 */
import { SchemaEditor } from "@/components/schemas/schema-editor";

interface EditSchemaPageProps {
  params: Promise<{ id: string }>;
}

export default async function EditSchemaPage({ params }: EditSchemaPageProps) {
  const { id } = await params;
  return <SchemaEditor schemaId={id} />;
}
