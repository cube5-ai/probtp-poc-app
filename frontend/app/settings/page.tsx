/**
 * Settings page
 * Main settings page with schema management
 */
"use client";

import { useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SchemaList } from "@/components/schemas/schema-list";
import { useBreadcrumbs } from "@/contexts/BreadcrumbContext";

export default function SettingsPage() {
  const { setBreadcrumbs } = useBreadcrumbs();

  // Set breadcrumbs for the settings page
  useEffect(() => {
    setBreadcrumbs([{ label: "Home", href: "/" }, { label: "Settings" }]);
  }, [setBreadcrumbs]);

  return (
    <div className="py-8">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Settings</h1>
          <p className="text-muted-foreground mt-1">
            Manage your application settings and data extraction schemas
          </p>
        </div>

        <Tabs defaultValue="schemas" className="space-y-6">
          <TabsList>
            <TabsTrigger value="schemas">Data Schemas</TabsTrigger>
            <TabsTrigger value="preferences" disabled>
              Preferences
            </TabsTrigger>
          </TabsList>

          <TabsContent value="schemas" className="space-y-6">
            <SchemaList />
          </TabsContent>

          <TabsContent value="profile" className="space-y-6">
            <div className="text-center py-12">
              <h3 className="text-lg font-semibold mb-2">Profile Settings</h3>
              <p className="text-muted-foreground">Coming soon...</p>
            </div>
          </TabsContent>

          <TabsContent value="preferences" className="space-y-6">
            <div className="text-center py-12">
              <h3 className="text-lg font-semibold mb-2">Preferences</h3>
              <p className="text-muted-foreground">Coming soon...</p>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
