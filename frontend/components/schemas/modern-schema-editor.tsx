/**
 * Modern Schema Editor
 * Clean, intuitive drag-and-drop schema builder
 */
"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  GripVertical,
  Plus,
  Trash2,
  Type,
  Hash,
  ToggleLeft,
  Package,
  List,
  ChevronDown,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface Field {
  id: string;
  name: string;
  type: string;
  description: string;
  required: boolean;
  children?: Field[];
  expanded?: boolean;
}

interface SchemaProperty {
  type: string;
  description?: string;
  properties?: Record<string, SchemaProperty>;
  required?: string[];
}

interface SchemaDefinition {
  type: string;
  properties: Record<string, SchemaProperty>;
  required?: string[];
  "x-order"?: string[]; // Extension property to preserve field order
}

interface ModernSchemaEditorProps {
  schema: SchemaDefinition;
  onChange: (schema: SchemaDefinition) => void;
  readOnly?: boolean;
}

const FIELD_TYPES = [
  { value: "string", label: "Text", icon: Type, color: "blue" },
  { value: "number", label: "Number", icon: Hash, color: "purple" },
  { value: "boolean", label: "Boolean", icon: ToggleLeft, color: "green" },
  { value: "object", label: "Object", icon: Package, color: "orange" },
  { value: "array", label: "Array", icon: List, color: "pink" },
];

// Sortable field row component
function FieldRow({
  field,
  onUpdate,
  onDelete,
  onAddChild,
  onUpdateChild,
  onDeleteChild,
  level = 0,
  parentPath = "",
  readOnly = false,
}: {
  field: Field;
  onUpdate: (id: string, updates: Partial<Field>) => void;
  onDelete: (id: string) => void;
  onAddChild?: (parentId: string) => void;
  onUpdateChild?: (
    parentId: string,
    childId: string,
    updates: Partial<Field>
  ) => void;
  onDeleteChild?: (parentId: string, childId: string) => void;
  level?: number;
  parentPath?: string;
  readOnly?: boolean;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: field.id,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const fieldType = FIELD_TYPES.find((t) => t.value === field.type);
  const Icon = fieldType?.icon || Type;

  const isObject = field.type === "object";
  const hasChildren = isObject && field.children && field.children.length > 0;
  const indentStyle = level > 0 ? { marginLeft: `${level * 2}rem` } : {};
  const currentPath = parentPath ? `${parentPath}.${field.name}` : field.name;
  const showPath = level > 0 && field.name; // Show path for nested fields

  return (
    <div
      ref={setNodeRef}
      style={{ ...style, ...indentStyle }}
      className={`group relative ${isDragging ? "z-50" : ""}`}
    >
      <Card
        className={`p-3 transition-all ${
          isDragging ? "shadow-xl opacity-50" : "hover:shadow-md"
        } ${level > 0 ? "border-l-2 border-l-muted" : ""}`}
      >
        <div className="flex items-center gap-2">
          {/* Drag handle */}
          <button
            {...attributes}
            {...listeners}
            className={`p-1 rounded transition-colors ${
              readOnly
                ? "cursor-default opacity-50"
                : "cursor-grab active:cursor-grabbing hover:bg-muted"
            }`}
            disabled={readOnly}
          >
            <GripVertical className="h-3 w-3 text-muted-foreground" />
          </button>

          {/* Expand/collapse for objects */}
          {isObject && (
            <button
              onClick={() => onUpdate(field.id, { expanded: !field.expanded })}
              className="p-1 hover:bg-muted rounded transition-colors"
            >
              {field.expanded ? (
                <ChevronDown className="h-3 w-3 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-3 w-3 text-muted-foreground" />
              )}
            </button>
          )}

          {/* Field content */}
          <div className="flex-1 space-y-2">
            {/* Top row: Name and Type */}
            <div className="flex gap-2 items-center">
              <div className="flex-1">
                <Input
                  value={field.name}
                  onChange={(e) => onUpdate(field.id, { name: e.target.value })}
                  placeholder="Field name"
                  className="font-medium h-8 text-sm"
                  disabled={readOnly}
                />
                {showPath && (
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {currentPath}
                  </div>
                )}
              </div>

              <Select
                value={field.type}
                onValueChange={(value) => onUpdate(field.id, { type: value })}
                disabled={readOnly}
              >
                <SelectTrigger className="w-[120px] h-8">
                  <SelectValue>
                    <div className="flex items-center gap-1">
                      <Icon className="h-3 w-3" />
                      <span className="text-xs">{fieldType?.label}</span>
                    </div>
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {FIELD_TYPES.map((type) => {
                    const TypeIcon = type.icon;
                    return (
                      <SelectItem key={type.value} value={type.value}>
                        <div className="flex items-center gap-2">
                          <TypeIcon className="h-3 w-3" />
                          <span className="text-xs">{type.label}</span>
                        </div>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>

            {/* Bottom row: Description and Required */}
            <div className="flex gap-2 items-center">
              <Input
                value={field.description}
                onChange={(e) =>
                  onUpdate(field.id, { description: e.target.value })
                }
                placeholder="Description (optional)"
                className="text-xs h-7 flex-1"
                disabled={readOnly}
              />

              <button
                onClick={() =>
                  onUpdate(field.id, { required: !field.required })
                }
                className={`text-xs px-2 py-1 rounded transition-colors ${
                  field.required
                    ? "bg-orange-100 text-orange-700 hover:bg-orange-200"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                } ${readOnly ? "cursor-default opacity-75" : ""}`}
                disabled={readOnly}
              >
                {field.required ? "Required" : "Optional"}
              </button>
            </div>
          </div>

          {/* Delete button */}
          {!readOnly && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onDelete(field.id)}
              className="opacity-0 group-hover:opacity-100 transition-opacity h-6 w-6 hover:bg-destructive/10 hover:text-destructive"
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          )}
        </div>

        {/* Add nested field button for objects */}
        {isObject && !readOnly && (
          <div className="mt-2 pt-2 border-t">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onAddChild?.(field.id)}
              className="w-full text-xs h-7"
            >
              <Plus className="h-3 w-3 mr-1" />
              Add nested field
            </Button>
          </div>
        )}
      </Card>

      {/* Nested fields */}
      {isObject && field.expanded && hasChildren && (
        <div className="mt-1 space-y-1">
          <SortableContext
            items={field.children!.map((child) => child.id)}
            strategy={verticalListSortingStrategy}
          >
            {field.children!.map((child) => (
              <FieldRow
                key={child.id}
                field={child}
                onUpdate={(id, updates) =>
                  onUpdateChild?.(field.id, id, updates)
                }
                onDelete={(id) => onDeleteChild?.(field.id, id)}
                onAddChild={onAddChild}
                onUpdateChild={onUpdateChild}
                onDeleteChild={onDeleteChild}
                level={level + 1}
                parentPath={currentPath}
                readOnly={readOnly}
              />
            ))}
          </SortableContext>
        </div>
      )}
    </div>
  );
}

export function ModernSchemaEditor({
  schema,
  onChange,
  readOnly = false,
}: ModernSchemaEditorProps) {
  const [fields, setFields] = useState<Field[]>([]);
  const isInitialLoadRef = useRef<boolean>(true);
  const hasInitializedRef = useRef<boolean>(false);
  const [aiInstruction, setAiInstruction] = useState("");
  const [isRefining, setIsRefining] = useState(false);
  const [showAiPanel, setShowAiPanel] = useState(true); // Always expanded by default

  // DnD sensors (disabled in read-only mode)
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: readOnly ? 999999 : 8 },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Convert schema to fields (recursive for nested objects)
  const convertSchemaToFields = useCallback(
    (schema: SchemaDefinition): Field[] => {
      if (!schema?.properties) return [];

      const recursiveConvert = (
        properties: Record<string, SchemaProperty>,
        required?: string[],
        order?: string[],
        depth: number = 0
      ): Field[] => {
        // Prevent infinite recursion
        if (depth > 10) {
          console.warn("Max recursion depth reached in schema conversion");
          return [];
        }

        // Use x-order if available, otherwise use Object.entries order
        const propertyNames =
          order && order.length > 0
            ? order.filter((name) => name in properties) // Only include names that exist in properties
            : Object.keys(properties);

        return propertyNames.map((name) => {
          const prop = properties[name];

          // Ensure all values are primitives, not objects
          const field: Field = {
            id: `field_${Date.now()}_${Math.random()}`,
            name: String(name || ""),
            type: String(prop.type || "string"),
            description: String(prop.description || ""),
            required: Boolean(required?.includes(name)),
            expanded: true,
          };

          // Only add children if it's actually an object type with properties
          if (
            prop.type === "object" &&
            prop.properties &&
            typeof prop.properties === "object"
          ) {
            field.children = recursiveConvert(
              prop.properties,
              prop.required,
              (prop as any)["x-order"], // Nested order
              depth + 1
            );
          }

          return field;
        });
      };

      return recursiveConvert(
        schema.properties,
        schema.required,
        schema["x-order"]
      );
    },
    []
  );

  // Initialize from schema - ONLY on first mount (key prop handles schema changes)
  useEffect(() => {
    // Only load once when component mounts - key prop will remount for different schemas
    if (hasInitializedRef.current) return;

    if (!schema?.properties) {
      setFields([]);
      return;
    }

    hasInitializedRef.current = true;
    isInitialLoadRef.current = true;
    const loadedFields = convertSchemaToFields(schema);
    setFields(loadedFields);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Convert fields to schema (recursive for nested objects)
  const convertFieldsToSchema = useCallback(
    (fields: Field[]): SchemaDefinition => {
      const recursiveConvert = (
        flds: Field[]
      ): {
        properties: Record<string, SchemaProperty>;
        required?: string[];
        order?: string[];
      } => {
        const properties: Record<string, SchemaProperty> = {};
        const required: string[] = [];
        const order: string[] = [];

        flds.forEach((field) => {
          if (field.name) {
            // Track field order
            order.push(field.name);

            properties[field.name] = {
              type: field.type,
              description: field.description || undefined,
            };

            if (field.required) {
              required.push(field.name);
            }

            // Handle nested fields for objects
            if (
              field.type === "object" &&
              field.children &&
              field.children.length > 0
            ) {
              const nestedResult = recursiveConvert(field.children);
              properties[field.name].properties = nestedResult.properties;
              if (nestedResult.required && nestedResult.required.length > 0) {
                properties[field.name].required = nestedResult.required;
              }
              // Add nested order
              if (nestedResult.order && nestedResult.order.length > 0) {
                (properties[field.name] as any)["x-order"] = nestedResult.order;
              }
            }
          }
        });

        return {
          properties,
          required: required.length > 0 ? required : undefined,
          order: order.length > 0 ? order : undefined,
        };
      };

      const result = recursiveConvert(fields);
      const schema: SchemaDefinition = {
        type: "object",
        properties: result.properties,
      };

      // Only add required if it has values (to match loaded schema structure)
      if (result.required && result.required.length > 0) {
        schema.required = result.required;
      }

      // Add field order
      if (result.order && result.order.length > 0) {
        schema["x-order"] = result.order;
      }

      return schema;
    },
    []
  );

  // Update parent when fields change (skip during initial load)
  useEffect(() => {
    // Skip onChange during initial load from schema to prevent infinite loop
    if (isInitialLoadRef.current) {
      isInitialLoadRef.current = false;
      return;
    }

    // Only call onChange if fields are not empty (component is initialized)
    if (fields.length === 0) return;

    const newSchema = convertFieldsToSchema(fields);
    onChange(newSchema);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fields]);

  // Add new field
  const addField = () => {
    const newField: Field = {
      id: `field_${Date.now()}_${Math.random()}`,
      name: "",
      type: "string",
      description: "",
      required: false,
    };
    setFields([...fields, newField]);
  };

  // Update field
  const updateField = (id: string, updates: Partial<Field>) => {
    setFields(fields.map((f) => (f.id === id ? { ...f, ...updates } : f)));
  };

  // Delete field
  const deleteField = (id: string) => {
    setFields(fields.filter((f) => f.id !== id));
  };

  // Recursive helper to update fields at any depth
  const updateFieldRecursively = (
    fields: Field[],
    targetId: string,
    updateFn: (field: Field) => Field
  ): Field[] => {
    return fields.map((field) => {
      if (field.id === targetId) {
        return updateFn(field);
      }
      if (field.children) {
        return {
          ...field,
          children: updateFieldRecursively(field.children, targetId, updateFn),
        };
      }
      return field;
    });
  };

  // Add child field to any parent (recursive)
  const addChildField = (parentId: string) => {
    const newChild: Field = {
      id: `field_${Date.now()}_${Math.random()}`,
      name: "",
      type: "string",
      description: "",
      required: false,
    };

    setFields(
      updateFieldRecursively(fields, parentId, (field) => ({
        ...field,
        children: [...(field.children || []), newChild],
        expanded: true,
      }))
    );
  };

  // Update child field (recursive)
  const updateChildField = (
    parentId: string,
    childId: string,
    updates: Partial<Field>
  ) => {
    setFields(
      updateFieldRecursively(fields, parentId, (field) => ({
        ...field,
        children: field.children?.map((c) =>
          c.id === childId ? { ...c, ...updates } : c
        ),
      }))
    );
  };

  // Delete child field (recursive)
  const deleteChildField = (parentId: string, childId: string) => {
    setFields(
      updateFieldRecursively(fields, parentId, (field) => ({
        ...field,
        children: field.children?.filter((c) => c.id !== childId),
      }))
    );
  };

  // Recursive helper to reorder fields at any depth
  const reorderFieldsRecursively = (
    fields: Field[],
    activeId: string,
    overId: string
  ): Field[] => {
    // Check if both items are at this level
    const activeIndex = fields.findIndex((item) => item.id === activeId);
    const overIndex = fields.findIndex((item) => item.id === overId);

    if (activeIndex !== -1 && overIndex !== -1) {
      // Both items are at this level, reorder them
      return arrayMove(fields, activeIndex, overIndex);
    }

    // If not at this level, check children recursively
    return fields.map((field) => {
      if (field.children) {
        return {
          ...field,
          children: reorderFieldsRecursively(field.children, activeId, overId),
        };
      }
      return field;
    });
  };

  // Handle drag end (works at any nesting level)
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      setFields((items) => {
        return reorderFieldsRecursively(
          items,
          active.id as string,
          over.id as string
        );
      });
    }
  };

  // AI-driven schema builder
  const handleAiRefine = async () => {
    if (!aiInstruction.trim()) {
      toast.error("Please enter instructions for AI builder");
      return;
    }

    try {
      setIsRefining(true);
      console.log("=".repeat(80));
      console.log("Starting AI schema refinement...");
      console.log("Current fields:", fields);

      const currentSchema = convertFieldsToSchema(fields);
      console.log("Converted to schema:", currentSchema);
      console.log("Instruction:", aiInstruction);

      // Import API function dynamically
      const { refineSchema } = await import("@/lib/api/schemas");

      console.log("Calling refineSchema API...");
      const refinedSchema = await refineSchema(currentSchema, aiInstruction);
      console.log("Received refined schema:", refinedSchema);

      // Convert refined schema back to fields
      console.log("Converting refined schema back to fields...");
      const refinedFields = convertSchemaToFields(refinedSchema);
      console.log("Refined fields:", refinedFields);
      console.log(`Field count: ${refinedFields.length}`);

      setFields(refinedFields);
      console.log("Fields updated in state");

      toast.success("Schema built successfully!");
      setAiInstruction(""); // Clear instruction after successful build
      console.log("=".repeat(80));
    } catch (error) {
      console.error("=".repeat(80));
      console.error("Error refining schema:", error);
      console.error("Error details:", {
        message: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
      });
      console.error("=".repeat(80));
      toast.error("Failed to build schema. Please try again.");
    } finally {
      setIsRefining(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold">Fields</h3>
          <p className="text-xs text-muted-foreground">
            Define the structure of your data
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">
            {fields.length} {fields.length === 1 ? "field" : "fields"}
          </Badge>
          {!readOnly && fields.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowAiPanel(!showAiPanel)}
              className="gap-1 h-7 text-xs"
            >
              <Sparkles className="h-3 w-3" />
              AI Builder
            </Button>
          )}
        </div>
      </div>

      {/* AI Builder Panel */}
      {!readOnly && showAiPanel && (
        <Collapsible open={showAiPanel} onOpenChange={setShowAiPanel}>
          <CollapsibleContent>
            <Card className="p-3 bg-gradient-to-br from-purple-50 to-blue-50 dark:from-purple-950/20 dark:to-blue-950/20 border-purple-200 dark:border-purple-800">
              <div className="space-y-2">
                <div className="flex items-start gap-2">
                  <Sparkles className="h-4 w-4 text-purple-600 dark:text-purple-400 mt-0.5" />
                  <div className="flex-1">
                    <h4 className="font-semibold text-sm mb-1">
                      AI Schema Builder
                    </h4>
                    <p className="text-xs text-muted-foreground mb-2">
                      Describe how you want to improve or modify your schema.
                    </p>
                    <Textarea
                      value={aiInstruction}
                      onChange={(e) => setAiInstruction(e.target.value)}
                      placeholder="e.g., 'Add address fields with street, city, and postal code'"
                      className="min-h-[60px] resize-none bg-white dark:bg-gray-900 text-xs"
                      disabled={isRefining}
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setShowAiPanel(false);
                      setAiInstruction("");
                    }}
                    disabled={isRefining}
                    className="h-7 text-xs"
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleAiRefine}
                    disabled={isRefining || !aiInstruction.trim()}
                    className="bg-purple-600 hover:bg-purple-700 text-white h-7 text-xs"
                  >
                    {isRefining && <Spinner className="mr-1 h-3 w-3" />}
                    {isRefining ? "Building..." : "Build Schema"}
                  </Button>
                </div>
              </div>
            </Card>
          </CollapsibleContent>
        </Collapsible>
      )}

      {/* Fields list */}
      {fields.length === 0 ? (
        <Card className="p-6 text-center border-dashed">
          <div className="flex flex-col items-center gap-3">
            <div className="p-2 rounded-full bg-muted">
              <Package className="h-6 w-6 text-muted-foreground" />
            </div>
            <div>
              <h4 className="font-medium mb-1 text-sm">No fields yet</h4>
              <p className="text-xs text-muted-foreground">
                Add your first field to get started
              </p>
            </div>
            {!readOnly && (
              <Button onClick={addField} size="sm" className="h-7 text-xs">
                <Plus className="h-3 w-3 mr-1" />
                Add Field
              </Button>
            )}
          </div>
        </Card>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={fields.map((f) => f.id)}
            strategy={verticalListSortingStrategy}
          >
            <div className="space-y-2">
              {fields.map((field) => (
                <FieldRow
                  key={field.id}
                  field={field}
                  onUpdate={updateField}
                  onDelete={deleteField}
                  onAddChild={addChildField}
                  onUpdateChild={updateChildField}
                  onDeleteChild={deleteChildField}
                  readOnly={readOnly}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      {/* Add field button */}
      {fields.length > 0 && !readOnly && (
        <Button
          onClick={addField}
          variant="outline"
          className="w-full h-8 text-xs"
        >
          <Plus className="h-3 w-3 mr-1" />
          Add Field
        </Button>
      )}
    </div>
  );
}
