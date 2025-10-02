# Development Plan: Custom Data Schema Settings Page

## Project Overview

Create a settings page where users can define, manage, and visualize custom data schemas for extracting structured information from documents in the main application.

## UI Design Reference

The schema builder should follow a **structured table-based design** with the following features:

### Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│ Schema Builder                  [Import] [Edit Schema] [Copy]│
├─────────────────────────────────────────────────────────────┤
│ Define the fields you'd like to extract from the document.  │
├────────┬──────────────┬────────────────────────────────────┤
│ Name   │ Type         │ Description                        │
├────────┼──────────────┼────────────────────────────────────┤
│ :: leaseId           │ [text]  │ Unique identifier...       │
├────────┼──────────────┼────────────────────────────────────┤
│ :: landlord          │ [object]│ Field description          │
│    │ 2 nested fields │         │                            │
│    └─ Name          │ Type    │ Description (optional)     │
│       :: name        │ [text]  │ Full name or company...    │
│       :: contactInfo │ [object]│ Field description          │
│          │ 2 nested fields    │                            │
│          └─ Name    │ Type    │ Description (optional)     │
│             :: email │ [text]  │ Email address...           │
│             :: phone │ [text]  │ Phone number...            │
│             [+ Add field]      │                            │
│       [+ Add field]            │                            │
├────────┼──────────────┼────────────────────────────────────┤
│ :: tenant            │ [object]│ Field description          │
│    │ 3 nested fields │         │                            │
└────────┴──────────────┴────────────────────────────────────┘
```

### Key Features

1. **Drag Handles (::)**: Allow reordering fields at any level
2. **Type Badges**: Visual indicators for field types (text, object, number, etc.)
3. **Nested Indentation**: Clear visual hierarchy for object/array fields
4. **Inline Editing**: Click to edit name, type, description directly in table
5. **Expandable Sections**: Collapse/expand nested fields
6. **Add Field Buttons**: Appear at each nesting level
7. **Clean Layout**: Three-column structure (Name, Type, Description)

## Recommended Libraries

After researching available options, we'll use **jsonjoy-builder** as the primary schema builder component:

### Primary Library (SELECTED) ⭐

#### JSONJoy Builder

- **Package**: `jsonjoy-builder`
- **Version**: 0.1.0 (recently released)
- **Use Case**: Complete visual JSON Schema editor
- **Pros**:
  - ✅ Pre-built structured table-based UI
  - ✅ Real-time JSON preview
  - ✅ Schema inference from JSON data
  - ✅ Built-in JSON validation
  - ✅ Responsive design (mobile/desktop)
  - ✅ Customizable via CSS variables
  - ✅ Multi-language support (EN, DE, FR, RU)
  - ✅ TypeScript support
  - ✅ Significantly faster development
- **Cons**:
  - ⚠️ Very new library (v0.1.0)
  - ⚠️ Limited production track record
- **Installation**: `bun add jsonjoy-builder`
- **GitHub**: https://github.com/lovasoa/jsonjoy-builder

### Supporting Libraries

- **Zod**: Schema validation (`bun add zod`)
- **React Hook Form**: Form management for schema metadata (`bun add react-hook-form @hookform/resolvers`)
- **Shadcn UI Components**: For surrounding UI elements (list, cards, dialogs)
- **@prisma/client**: Database ORM for Cloud SQL (`bun add @prisma/client`)

### Optional Libraries

- **Monaco Editor** (`@monaco-editor/react`): Advanced code editing mode (if needed later)

---

## Architecture Overview

### Frontend (Next.js + React)

```
/frontend
  /app
    /settings
      /page.tsx                 # Main settings page
      /schemas
        /page.tsx               # Schema management page
        /[schemaId]
          /page.tsx             # Edit schema page
        /new
          /page.tsx             # Create new schema page
  /components
    /schemas
      /schema-list.tsx          # List all schemas
      /schema-card.tsx          # Individual schema card
      /schema-builder
        /schema-editor-wrapper.tsx # Wrapper for JSONJoy SchemaVisualEditor
        /schema-metadata-form.tsx  # Form for name/description
        /schema-actions.tsx     # Import/Export/Copy buttons
      /schema-templates
        /template-selector.tsx  # Pre-built schema templates
        /template-preview.tsx   # Template preview component
  /lib
    /schemas
      /schema-validator.ts      # Zod validation schemas
      /schema-converter.ts      # Convert JSONJoy format to our DB format
      /schema-api.ts            # API calls for schemas
      /template-definitions.ts  # Pre-built schema templates
  /hooks
    /useSchemas.ts              # Schema CRUD operations hook
  /types
    /schema.types.ts            # TypeScript types
```

### Backend (FastAPI + Cloud SQL)

```
/backend
  /app
    /api
      /schemas.py               # Schema CRUD endpoints
    /models
      /schema.py                # SQLAlchemy schema model
      /user_schema.py           # User-schema relationship
    /services
      /schema_service.py        # Business logic
      /validation_service.py    # Schema validation
    /schemas
      /pydantic_schemas.py      # Pydantic models
```

### Database (Cloud SQL - PostgreSQL)

```sql
-- Schemas table
CREATE TABLE schemas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR(255) NOT NULL,  -- Firebase UID
  name VARCHAR(255) NOT NULL,
  description TEXT,
  schema_definition JSONB NOT NULL,
  base_schema_id UUID,  -- For templates
  is_template BOOLEAN DEFAULT FALSE,
  version INTEGER DEFAULT 1,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  FOREIGN KEY (base_schema_id) REFERENCES schemas(id)
);

-- Index for faster queries
CREATE INDEX idx_schemas_user_id ON schemas(user_id);
CREATE INDEX idx_schemas_is_template ON schemas(is_template);
```

---

## Development Plan - Step by Step

### Phase 1: Backend Setup (Days 1-3)

#### Task 1.1: Database Setup

- [ ] Set up Cloud SQL PostgreSQL instance in Google Cloud
- [ ] Configure connection from backend
- [ ] Create database migrations folder structure
- [ ] Create initial migration for `schemas` table
- [ ] Add indexes for performance

**Files to create/modify:**

- `/backend/app/db/connection.py` - Database connection
- `/backend/alembic/versions/001_create_schemas_table.py` - Migration
- `/backend/app/core/config.py` - Add Cloud SQL config

#### Task 1.2: Database Models

- [ ] Create SQLAlchemy model for Schema
- [ ] Add model relationships and constraints
- [ ] Create Pydantic schemas for request/response
- [ ] Add validation logic

**Files to create:**

- `/backend/app/models/schema.py`
- `/backend/app/schemas/schema_schemas.py`

#### Task 1.3: Schema Service Layer

- [ ] Create SchemaService class for business logic
- [ ] Implement CRUD operations
- [ ] Add schema validation service
- [ ] Add schema versioning logic
- [ ] Implement template cloning logic

**Files to create:**

- `/backend/app/services/schema_service.py`
- `/backend/app/services/validation_service.py`

#### Task 1.4: API Endpoints

- [ ] `GET /api/schemas` - List all schemas for user
- [ ] `GET /api/schemas/{schema_id}` - Get single schema
- [ ] `POST /api/schemas` - Create new schema
- [ ] `PUT /api/schemas/{schema_id}` - Update schema
- [ ] `DELETE /api/schemas/{schema_id}` - Delete schema
- [ ] `GET /api/schemas/templates` - Get template schemas
- [ ] `POST /api/schemas/{schema_id}/clone` - Clone from template
- [ ] Add Firebase auth middleware to all endpoints

**Files to create:**

- `/backend/app/api/schemas.py`
- `/backend/app/middleware/auth.py` (update)

#### Task 1.5: Testing

- [ ] Write unit tests for services
- [ ] Write integration tests for API endpoints
- [ ] Test with Firebase auth tokens

**Files to create:**

- `/backend/tests/test_schema_service.py`
- `/backend/tests/test_schema_api.py`

---

### Phase 2: Frontend - Core Structure (Days 4-6)

#### Task 2.1: Type Definitions

- [ ] Create TypeScript interfaces for schemas
- [ ] Define field types and validation rules
- [ ] Create enum types for field configurations

**Files to create:**

- `/frontend/types/schema.types.ts`

```typescript
// Example structure
export interface Schema {
  id: string;
  userId: string;
  name: string;
  description?: string;
  schemaDefinition: SchemaDefinition;
  baseSchemaId?: string;
  isTemplate: boolean;
  version: number;
  createdAt: string;
  updatedAt: string;
}

export interface SchemaDefinition {
  fields: SchemaField[];
  metadata?: Record<string, any>;
}

export interface SchemaField {
  id: string;
  name: string;
  type: FieldType;
  required: boolean;
  description?: string;
  validation?: ValidationRule[];
  defaultValue?: any;
}

export enum FieldType {
  TEXT = "text",
  NUMBER = "number",
  DATE = "date",
  BOOLEAN = "boolean",
  EMAIL = "email",
  URL = "url",
  ARRAY = "array",
  OBJECT = "object",
}
```

#### Task 2.2: API Client

- [ ] Create schema API client functions
- [ ] Add error handling
- [ ] Add request/response types
- [ ] Integrate with existing auth context

**Files to create:**

- `/frontend/lib/api/schemas.ts`

#### Task 2.3: Schema State Management

- [ ] Create schema context or hooks
- [ ] Implement optimistic updates
- [ ] Add caching strategy

**Files to create:**

- `/frontend/contexts/SchemaContext.tsx` or
- `/frontend/hooks/useSchemas.ts`

---

### Phase 3: Frontend - Settings Page Layout (Days 7-9)

#### Task 3.1: Main Settings Page

- [ ] Create settings page layout
- [ ] Add navigation tabs (Profile, Schemas, etc.)
- [ ] Update navbar breadcrumbs for settings
- [ ] Add shadcn Tabs component

**Files to create:**

- `/frontend/app/settings/page.tsx`
- `/frontend/app/settings/layout.tsx`

#### Task 3.2: Schema List Page

- [ ] Create schema list view component
- [ ] Display schemas in a grid/list with shadcn Card
- [ ] Add search/filter functionality
- [ ] Add "Create New" button
- [ ] Show empty state when no schemas exist

**Files to create:**

- `/frontend/app/settings/schemas/page.tsx`
- `/frontend/components/schemas/schema-list.tsx`
- `/frontend/components/schemas/schema-card.tsx`
- `/frontend/components/schemas/empty-state.tsx`

#### Task 3.3: Schema Card Component

- [ ] Display schema name, description, field count
- [ ] Add edit and delete buttons
- [ ] Add template badge for base schemas
- [ ] Show last modified date
- [ ] Add confirmation dialog for delete (shadcn AlertDialog)

**Files to create:**

- `/frontend/components/schemas/schema-card.tsx`
- `/frontend/components/schemas/delete-dialog.tsx`

---

### Phase 4: Schema Builder - JSONJoy Integration (Days 10-12)

#### Task 4.1: Install and Setup JSONJoy Builder

- [ ] Install jsonjoy-builder: `bun add jsonjoy-builder`
- [ ] Import styles in global CSS or layout
- [ ] Create basic wrapper component
- [ ] Test basic functionality

**Files to create:**

- `/frontend/components/schemas/schema-builder/schema-editor-wrapper.tsx`

#### Task 4.2: Schema Editor Wrapper Component

- [ ] Create wrapper component for SchemaVisualEditor
- [ ] Set up state management for schema
- [ ] Handle onChange events
- [ ] Add loading states
- [ ] Add error boundaries

**Files to create:**

- `/frontend/components/schemas/schema-builder/schema-editor-wrapper.tsx`
- `/frontend/components/schemas/schema-builder/error-boundary.tsx`

#### Task 4.3: Styling and Theming

- [ ] Customize JSONJoy with CSS variables
- [ ] Match shadcn theme colors
- [ ] Ensure responsive behavior
- [ ] Test dark/light mode compatibility
- [ ] Adjust spacing and typography

**Files to create/modify:**

- `/frontend/app/globals.css` - Add JSONJoy CSS variable overrides
- `/frontend/components/schemas/schema-builder/jsonjoy-theme.css`

#### Task 4.4: Schema Actions Toolbar

- [ ] Import schema from JSON
- [ ] Export schema to JSON
- [ ] Copy schema to clipboard
- [ ] Reset/clear schema
- [ ] Undo/redo if supported

**Files to create:**

- `/frontend/components/schemas/schema-builder/schema-actions.tsx`

#### Task 4.5: Schema Metadata Form

- [ ] Create form for schema name
- [ ] Create form for schema description
- [ ] Integrate with React Hook Form
- [ ] Add validation
- [ ] Link with schema editor state

**Files to create:**

- `/frontend/components/schemas/schema-builder/schema-metadata-form.tsx`

#### Task 4.6: Schema Conversion Logic

- [ ] Convert JSONJoy schema format to database format
- [ ] Convert database format back to JSONJoy format
- [ ] Validate converted schemas
- [ ] Handle edge cases and nested structures

**Files to create:**

- `/frontend/lib/schemas/schema-converter.ts`
- `/frontend/lib/schemas/jsonjoy-adapter.ts`

---

### Phase 5: Schema Templates (Days 13-14)

#### Task 5.1: Template System

- [ ] Create predefined schema templates
- [ ] Templates: Invoice, Resume, Contract, Medical Form, Receipt
- [ ] Store templates as JSON files
- [ ] Convert templates to JSONJoy format
- [ ] Add template preview

**Files to create:**

- `/frontend/lib/schemas/template-definitions.ts`
- `/frontend/components/schemas/schema-templates/template-selector.tsx`
- `/frontend/components/schemas/schema-templates/template-card.tsx`
- `/frontend/components/schemas/schema-templates/template-preview.tsx`

#### Task 5.2: Template Selection UI

- [ ] Create template selector dialog (shadcn Dialog)
- [ ] Show template preview with JSONJoy editor (read-only)
- [ ] "Start from Template" vs "Start from Scratch" option
- [ ] Search/filter templates
- [ ] Template categories/tags

**Files to create:**

- `/frontend/components/schemas/schema-templates/template-dialog.tsx`

---

### Phase 6: Create/Edit Schema Pages (Days 15-17)

#### Task 6.1: New Schema Page

- [ ] Create `/settings/schemas/new` route
- [ ] Integrate schema metadata form
- [ ] Integrate JSONJoy editor wrapper
- [ ] Integrate template selector
- [ ] Add save and cancel buttons
- [ ] Add "Save as Template" option
- [ ] Implement auto-save to local storage (draft)

**Files to create:**

- `/frontend/app/settings/schemas/new/page.tsx`
- `/frontend/components/schemas/schema-form-page.tsx`

#### Task 6.2: Edit Schema Page

- [ ] Create `/settings/schemas/[schemaId]` route
- [ ] Load existing schema data from API
- [ ] Populate JSONJoy editor with existing schema
- [ ] Show version history (optional for MVP)
- [ ] Add "Save" and "Save as New Version" options
- [ ] Add "Duplicate" option
- [ ] Show unsaved changes warning

**Files to create:**

- `/frontend/app/settings/schemas/[schemaId]/page.tsx`
- `/frontend/components/schemas/unsaved-changes-dialog.tsx`

#### Task 6.3: Schema Preview & Export

- [ ] Add JSON preview panel
- [ ] Show example data based on schema (optional)
- [ ] Add copy to clipboard button
- [ ] Add export as JSON file
- [ ] Show field count summary

**Files to create:**

- `/frontend/components/schemas/schema-builder/schema-preview-panel.tsx`

---

### Phase 7: Validation and Error Handling (Days 18-19)

#### Task 7.1: Frontend Validation

- [ ] Create Zod schemas for metadata validation
- [ ] Validate schema name (required, unique)
- [ ] Validate schema description
- [ ] Validate JSONJoy output format
- [ ] Check for duplicate field names in schema
- [ ] Ensure at least one field exists

**Files to create:**

- `/frontend/lib/schemas/schema-validator.ts`

#### Task 7.2: Error Display

- [ ] Show validation errors in UI
- [ ] Show error messages in toasts (shadcn Sonner)
- [ ] Add inline form validation
- [ ] Handle API errors gracefully

#### Task 7.3: Success Feedback

- [ ] Success toast on save
- [ ] Redirect to schema list after creation
- [ ] Show "unsaved changes" warning on navigation
- [ ] Optimistic updates for better UX

---

### Phase 8: UI Polish and Responsive Design (Days 20-21)

#### Task 8.1: Responsive Design

- [ ] Make schema list responsive (grid → list on mobile)
- [ ] Ensure JSONJoy editor is usable on tablets
- [ ] Test all forms on small screens
- [ ] Adjust layouts for mobile

#### Task 8.2: Loading States

- [ ] Add skeleton loaders for schema list
- [ ] Loading spinner for save operations
- [ ] Loading state for JSONJoy editor
- [ ] Shimmer effects while fetching data

**Files to create:**

- `/frontend/components/schemas/schema-skeleton.tsx`
- `/frontend/components/schemas/schema-builder/editor-loading.tsx`

#### Task 8.3: Empty States

- [ ] No schemas empty state with CTA
- [ ] No templates available state
- [ ] No search results state
- [ ] Empty schema builder state

**Files to create:**

- `/frontend/components/schemas/empty-states.tsx`

#### Task 8.4: Accessibility

- [ ] Keyboard navigation support
- [ ] ARIA labels for all interactive elements
- [ ] Focus management in dialogs
- [ ] Screen reader announcements
- [ ] Test JSONJoy editor accessibility

---

### Phase 9: Testing and Documentation (Days 22-24)

#### Task 9.1: Frontend Testing

- [ ] Unit tests for schema converter/adapter
- [ ] Unit tests for validation logic
- [ ] Component tests for wrapper components
- [ ] Integration tests with JSONJoy editor
- [ ] E2E tests for create/edit flows

**Files to create:**

- `/frontend/__tests__/schemas/schema-converter.test.ts`
- `/frontend/__tests__/schemas/jsonjoy-adapter.test.ts`
- `/frontend/__tests__/schemas/schema-validator.test.ts`

#### Task 9.2: Integration Testing

- [ ] Test full create schema flow
- [ ] Test edit and delete flows
- [ ] Test template selection and loading
- [ ] Test import/export functionality
- [ ] Test error scenarios and edge cases

#### Task 9.3: Documentation

- [ ] Add component documentation with JSDoc
- [ ] Create user guide for schema creation
- [ ] Document schema definition format
- [ ] Document JSONJoy integration details
- [ ] Add inline code comments

**Files to create:**

- `/docs/schemas/user-guide.md`
- `/docs/schemas/schema-format.md`
- `/docs/schemas/jsonjoy-integration.md`
- `/docs/schemas/api-reference.md`

---

## Implementation Example

### Using JSONJoy Builder

```tsx
// schema-editor-wrapper.tsx
"use client";

import { useState } from "react";
import "jsonjoy-builder/styles.css";
import { SchemaVisualEditor } from "jsonjoy-builder";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface SchemaEditorWrapperProps {
  initialSchema?: any;
  onChange: (schema: any) => void;
}

export function SchemaEditorWrapper({
  initialSchema = {},
  onChange,
}: SchemaEditorWrapperProps) {
  const [schema, setSchema] = useState(initialSchema);

  const handleSchemaChange = (newSchema: any) => {
    setSchema(newSchema);
    onChange(newSchema);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Schema Builder</CardTitle>
        <p className="text-sm text-muted-foreground">
          Define the fields you'd like to extract from the document.
        </p>
      </CardHeader>
      <CardContent>
        <SchemaVisualEditor schema={schema} onChange={handleSchemaChange} />
      </CardContent>
    </Card>
  );
}
```

### Styling JSONJoy to Match Shadcn Theme

```css
/* globals.css or jsonjoy-theme.css */

/* JSONJoy theme customization */
.jsonjoy {
  /* Colors from shadcn theme */
  --jsonjoy-background: hsl(var(--background));
  --jsonjoy-foreground: hsl(var(--foreground));
  --jsonjoy-card: hsl(var(--card));
  --jsonjoy-card-foreground: hsl(var(--card-foreground));
  --jsonjoy-primary: hsl(var(--primary));
  --jsonjoy-primary-foreground: hsl(var(--primary-foreground));
  --jsonjoy-secondary: hsl(var(--secondary));
  --jsonjoy-secondary-foreground: hsl(var(--secondary-foreground));
  --jsonjoy-muted: hsl(var(--muted));
  --jsonjoy-muted-foreground: hsl(var(--muted-foreground));
  --jsonjoy-accent: hsl(var(--accent));
  --jsonjoy-accent-foreground: hsl(var(--accent-foreground));
  --jsonjoy-border: hsl(var(--border));
  --jsonjoy-input: hsl(var(--input));
  --jsonjoy-ring: hsl(var(--ring));

  /* Spacing and typography */
  font-family: var(--font-sans);
  border-radius: var(--radius);
}
```

### Schema Conversion Adapter

```typescript
// jsonjoy-adapter.ts

import { SchemaDefinition, SchemaField } from "@/types/schema.types";

// Convert JSONJoy schema to our internal format
export function fromJSONJoySchema(jsonJoySchema: any): SchemaDefinition {
  // Implementation depends on JSONJoy's output format
  return {
    fields: convertFields(jsonJoySchema.properties || {}),
    metadata: {
      required: jsonJoySchema.required || [],
    },
  };
}

// Convert our internal format to JSONJoy schema
export function toJSONJoySchema(schemaDefinition: SchemaDefinition): any {
  // Implementation to convert to JSONJoy format
  return {
    type: "object",
    properties: convertFieldsToProperties(schemaDefinition.fields),
    required: schemaDefinition.fields
      .filter((f) => f.required)
      .map((f) => f.name),
  };
}

function convertFields(properties: any): SchemaField[] {
  return Object.entries(properties).map(([key, value]: [string, any]) => ({
    id: crypto.randomUUID(),
    name: key,
    type: mapJSONJoyTypeToOurType(value.type),
    required: false, // Will be set from required array
    description: value.description,
  }));
}

function mapJSONJoyTypeToOurType(jsonJoyType: string): string {
  const typeMap: Record<string, string> = {
    string: "text",
    number: "number",
    integer: "number",
    boolean: "boolean",
    object: "object",
    array: "array",
  };
  return typeMap[jsonJoyType] || "text";
}
```

### Complete Schema Form Page

```tsx
// app/settings/schemas/new/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SchemaEditorWrapper } from "@/components/schemas/schema-builder/schema-editor-wrapper";
import { SchemaMetadataForm } from "@/components/schemas/schema-builder/schema-metadata-form";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { createSchema } from "@/lib/api/schemas";

export default function NewSchemaPage() {
  const router = useRouter();
  const [schemaName, setSchemaName] = useState("");
  const [schemaDescription, setSchemaDescription] = useState("");
  const [schemaDefinition, setSchemaDefinition] = useState({});
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    try {
      setIsSaving(true);

      await createSchema({
        name: schemaName,
        description: schemaDescription,
        schemaDefinition,
      });

      toast.success("Schema created successfully!");
      router.push("/settings/schemas");
    } catch (error) {
      toast.error("Failed to create schema");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Create New Schema</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => router.back()}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!schemaName || isSaving}>
            {isSaving ? "Saving..." : "Save Schema"}
          </Button>
        </div>
      </div>

      <SchemaMetadataForm
        name={schemaName}
        description={schemaDescription}
        onNameChange={setSchemaName}
        onDescriptionChange={setSchemaDescription}
      />

      <SchemaEditorWrapper onChange={setSchemaDefinition} />
    </div>
  );
}
```

---

## Timeline Summary

| Phase                        | Duration    | Tasks                                       |
| ---------------------------- | ----------- | ------------------------------------------- |
| Phase 1: Backend Setup       | 3 days      | Database, models, API endpoints             |
| Phase 2: Frontend Core       | 3 days      | Types, API client, state management         |
| Phase 3: Settings Layout     | 3 days      | Main page, list view, cards                 |
| Phase 4: JSONJoy Integration | 3 days      | Install, wrapper, styling, actions          |
| Phase 5: Templates           | 2 days      | Template system and UI                      |
| Phase 6: CRUD Pages          | 3 days      | Create, edit, preview                       |
| Phase 7: Validation          | 2 days      | Frontend/backend validation                 |
| Phase 8: Polish              | 2 days      | Responsive, loading states, a11y            |
| Phase 9: Testing & Docs      | 3 days      | Unit, integration, e2e tests, documentation |
| **Total**                    | **24 days** | **~3.5 weeks** ⚡                           |

**Time Saved**: 4 days compared to custom implementation! 🎉

---

## Database Schema Design

```sql
-- Main schemas table
CREATE TABLE schemas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  schema_definition JSONB NOT NULL,
  base_schema_id UUID,
  is_template BOOLEAN DEFAULT FALSE,
  version INTEGER DEFAULT 1,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  CONSTRAINT fk_base_schema FOREIGN KEY (base_schema_id)
    REFERENCES schemas(id) ON DELETE SET NULL
);

-- Schema versions (optional, for version history)
CREATE TABLE schema_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  schema_id UUID NOT NULL,
  version INTEGER NOT NULL,
  schema_definition JSONB NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  created_by VARCHAR(255) NOT NULL,
  CONSTRAINT fk_schema FOREIGN KEY (schema_id)
    REFERENCES schemas(id) ON DELETE CASCADE,
  UNIQUE(schema_id, version)
);

-- Indexes
CREATE INDEX idx_schemas_user_id ON schemas(user_id);
CREATE INDEX idx_schemas_is_template ON schemas(is_template);
CREATE INDEX idx_schema_versions_schema_id ON schema_versions(schema_id);
```

---

## Example Schema Definition (JSON)

```json
{
  "name": "Invoice Schema",
  "description": "Extract invoice information from documents",
  "fields": [
    {
      "id": "invoice_number",
      "name": "Invoice Number",
      "type": "text",
      "required": true,
      "description": "Unique invoice identifier",
      "validation": [
        {
          "type": "pattern",
          "value": "^INV-[0-9]{6}$",
          "message": "Must match format INV-XXXXXX"
        }
      ]
    },
    {
      "id": "invoice_date",
      "name": "Invoice Date",
      "type": "date",
      "required": true,
      "description": "Date the invoice was issued"
    },
    {
      "id": "total_amount",
      "name": "Total Amount",
      "type": "number",
      "required": true,
      "validation": [
        {
          "type": "min",
          "value": 0,
          "message": "Amount must be positive"
        }
      ]
    },
    {
      "id": "line_items",
      "name": "Line Items",
      "type": "array",
      "required": false,
      "itemSchema": {
        "type": "object",
        "fields": [
          {
            "id": "description",
            "name": "Description",
            "type": "text",
            "required": true
          },
          {
            "id": "quantity",
            "name": "Quantity",
            "type": "number",
            "required": true
          },
          {
            "id": "unit_price",
            "name": "Unit Price",
            "type": "number",
            "required": true
          }
        ]
      }
    }
  ],
  "metadata": {
    "category": "finance",
    "tags": ["invoice", "billing"]
  }
}
```

---

## Security Considerations

1. **Authentication**: All API endpoints must verify Firebase JWT tokens
2. **Authorization**: Users can only access their own schemas
3. **Input Validation**: Validate all schema definitions on backend
4. **SQL Injection**: Use parameterized queries (SQLAlchemy handles this)
5. **Rate Limiting**: Implement rate limiting on API endpoints
6. **Schema Size Limits**: Limit maximum fields per schema (e.g., 100 fields)

---

## Performance Considerations

1. **Pagination**: Implement pagination for schema list (20 per page)
2. **Caching**: Cache frequently accessed schemas
3. **Indexing**: Proper database indexes on user_id and is_template
4. **Lazy Loading**: Load schema definitions only when needed
5. **Debouncing**: Debounce auto-save functionality

---

## Future Enhancements (Post-MVP)

- [ ] Schema sharing between users
- [ ] Import schemas from popular formats (JSON Schema, OpenAPI)
- [ ] AI-assisted schema generation from sample documents
- [ ] Schema marketplace/community templates
- [ ] Schema testing with sample data
- [ ] Webhook notifications on schema changes
- [ ] Schema analytics (usage, extraction success rate)

---

## Notes

### Library Decision: JSONJoy Builder

We've chosen **jsonjoy-builder** over a custom DnD Kit implementation for the following reasons:

✅ **Advantages:**

- Significantly faster development (saves ~4 days)
- Pre-built structured table UI that matches design requirements
- Built-in features (JSON preview, validation, schema inference)
- Customizable theming via CSS variables
- Active development and TypeScript support

⚠️ **Considerations:**

- New library (v0.1.0) - monitor for stability issues
- May need wrapper/adapter layer for full control
- Theming may require CSS overrides to match shadcn perfectly
- If UI requirements change significantly, may need custom solution

### Migration Path (if needed)

If JSONJoy doesn't meet needs:

1. The wrapper component isolates the dependency
2. Schema data is stored in standardized format in database
3. Can replace with custom DnD Kit implementation without database changes
4. Conversion layer (jsonjoy-adapter.ts) makes switching easier

### Development Guidelines

- All components should use shadcn/ui for consistency (except JSONJoy editor)
- Follow the existing code structure and naming conventions
- Use TypeScript strict mode
- Maintain test coverage above 80%
- Keep files under 500 lines (split if needed)
- Use functional components and hooks
- Follow single responsibility principle
- Isolate JSONJoy integration behind wrapper components
