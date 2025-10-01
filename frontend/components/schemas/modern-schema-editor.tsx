/**
 * Modern Schema Editor
 * Clean, intuitive drag-and-drop schema builder
 */
"use client";

import { useState, useEffect } from "react";
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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface Field {
  id: string;
  name: string;
  type: string;
  description: string;
  required: boolean;
  children?: Field[];
  expanded?: boolean;
}

interface ModernSchemaEditorProps {
  schema: any;
  onChange: (schema: any) => void;
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
        className={`p-4 transition-all ${
          isDragging ? "shadow-xl opacity-50" : "hover:shadow-md"
        } ${level > 0 ? "border-l-2 border-l-muted" : ""}`}
      >
        <div className="flex items-start gap-3">
          {/* Drag handle */}
          <button
            {...attributes}
            {...listeners}
            className={`mt-2 p-1 rounded transition-colors ${
              readOnly
                ? "cursor-default opacity-50"
                : "cursor-grab active:cursor-grabbing hover:bg-muted"
            }`}
            disabled={readOnly}
          >
            <GripVertical className="h-4 w-4 text-muted-foreground" />
          </button>

          {/* Expand/collapse for objects */}
          {isObject && (
            <button
              onClick={() => onUpdate(field.id, { expanded: !field.expanded })}
              className="mt-2 p-1 hover:bg-muted rounded transition-colors"
            >
              {field.expanded ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
            </button>
          )}

          {/* Field content */}
          <div className="flex-1 space-y-3">
            {/* Top row: Name and Type */}
            <div className="flex gap-3">
              <div className="flex-1">
                <Input
                  value={field.name}
                  onChange={(e) => onUpdate(field.id, { name: e.target.value })}
                  placeholder="Field name (e.g., email, age)"
                  className="font-medium"
                  disabled={readOnly}
                />
                {showPath && (
                  <div className="text-xs text-muted-foreground mt-1">
                    Path: {currentPath}
                  </div>
                )}
              </div>

              <Select
                value={field.type}
                onValueChange={(value) => onUpdate(field.id, { type: value })}
                disabled={readOnly}
              >
                <SelectTrigger className="w-[160px]">
                  <SelectValue>
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4" />
                      <span>{fieldType?.label}</span>
                    </div>
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {FIELD_TYPES.map((type) => {
                    const TypeIcon = type.icon;
                    return (
                      <SelectItem key={type.value} value={type.value}>
                        <div className="flex items-center gap-2">
                          <TypeIcon className="h-4 w-4" />
                          <span>{type.label}</span>
                        </div>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>

            {/* Bottom row: Description */}
            <Input
              value={field.description}
              onChange={(e) =>
                onUpdate(field.id, { description: e.target.value })
              }
              placeholder="Description (optional)"
              className="text-sm"
              disabled={readOnly}
            />

            {/* Required badge */}
            <div className="flex items-center gap-2">
              <button
                onClick={() =>
                  onUpdate(field.id, { required: !field.required })
                }
                className={`text-xs px-2 py-1 rounded-md transition-colors ${
                  field.required
                    ? "bg-orange-100 text-orange-700 hover:bg-orange-200"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                } ${readOnly ? "cursor-default opacity-75" : ""}`}
                disabled={readOnly}
              >
                {field.required ? "Required" : "Optional"}
              </button>
              {field.required && level > 0 && (
                <div className="text-xs text-muted-foreground">
                  in {parentPath || "parent"}
                </div>
              )}
            </div>
          </div>

          {/* Delete button */}
          {!readOnly && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onDelete(field.id)}
              className="opacity-0 group-hover:opacity-100 transition-opacity mt-1 hover:bg-destructive/10 hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* Add nested field button for objects */}
        {isObject && !readOnly && (
          <div className="mt-3 pt-3 border-t">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onAddChild?.(field.id)}
              className="w-full text-xs"
            >
              <Plus className="h-3 w-3 mr-1" />
              Add nested field
            </Button>
          </div>
        )}
      </Card>

      {/* Nested fields */}
      {isObject && field.expanded && hasChildren && (
        <div className="mt-2 space-y-2">
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
  const convertSchemaToFields = (schema: any): Field[] => {
    if (!schema?.properties) return [];

    return Object.entries(schema.properties).map(
      ([name, prop]: [string, any]) => ({
        id: `field_${Date.now()}_${Math.random()}`,
        name,
        type: prop.type || "string",
        description: prop.description || "",
        required: schema.required?.includes(name) || false,
        children:
          prop.type === "object" && prop.properties
            ? convertSchemaToFields(prop)
            : undefined,
        expanded: true,
      })
    );
  };

  // Initialize from schema
  useEffect(() => {
    if (!schema?.properties) {
      setFields([]);
      return;
    }

    const loadedFields = convertSchemaToFields(schema);
    setFields(loadedFields);
  }, []);

  // Convert fields to schema (recursive for nested objects)
  const convertFieldsToSchema = (fields: Field[]): any => {
    const properties: any = {};
    const required: string[] = [];

    fields.forEach((field) => {
      if (field.name) {
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
          const nestedSchema = convertFieldsToSchema(field.children);
          properties[field.name].properties = nestedSchema.properties;
          if (nestedSchema.required) {
            properties[field.name].required = nestedSchema.required;
          }
        }
      }
    });

    return {
      type: "object",
      properties,
      required: required.length > 0 ? required : undefined,
    };
  };

  // Update parent when fields change
  useEffect(() => {
    const newSchema = convertFieldsToSchema(fields);
    onChange(newSchema);
  }, [fields, onChange]);

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

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Fields</h3>
          <p className="text-sm text-muted-foreground">
            Define the structure of your data
          </p>
        </div>
        <Badge variant="secondary" className="text-xs">
          {fields.length} {fields.length === 1 ? "field" : "fields"}
        </Badge>
      </div>

      {/* Fields list */}
      {fields.length === 0 ? (
        <Card className="p-12 text-center border-dashed">
          <div className="flex flex-col items-center gap-4">
            <div className="p-3 rounded-full bg-muted">
              <Package className="h-8 w-8 text-muted-foreground" />
            </div>
            <div>
              <h4 className="font-medium mb-1">No fields yet</h4>
              <p className="text-sm text-muted-foreground">
                Add your first field to get started
              </p>
            </div>
            {!readOnly && (
              <Button onClick={addField} size="sm">
                <Plus className="h-4 w-4 mr-2" />
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
            <div className="space-y-3">
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
        <Button onClick={addField} variant="outline" className="w-full">
          <Plus className="h-4 w-4 mr-2" />
          Add Field
        </Button>
      )}
    </div>
  );
}
