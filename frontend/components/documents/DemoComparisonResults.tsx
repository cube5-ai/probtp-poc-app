"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { Download, Share, Trophy, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { makeIsGreen } from "@/lib/report/isBest";
import demoComparison from "@/fixtures/comparison-demo.json";

const demoJsonString = JSON.stringify(demoComparison, null, 2);

type DemoComparisonResult = typeof demoComparison;

interface DemoComparisonResultsProps {
  data: DemoComparisonResult;
  onShare?: () => void;
}

const toArray = (value: unknown): string[] => {
  if (!value) {
    return [];
  }

  if (Array.isArray(value)) {
    return value
      .map((entry) => (typeof entry === "string" ? entry.trim() : String(entry)))
      .filter(Boolean);
  }

  if (typeof value === "string") {
    return value
      .split(/\n+/)
      .map((entry) => entry.trim())
      .filter(Boolean);
  }

  return [String(value)];
};

const DemoComparisonResults = ({ data, onShare }: DemoComparisonResultsProps) => {
  const {
    analyses,
    general_summary: generalSummary,
    comparison_tables: comparisonTables,
  } = data;

  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({});

  const categorySummary = useMemo(
    () =>
      analyses.map((analysis) => ({
        category: analysis.category,
        winner: analysis.objective_assessment.overall_winner,
        confidence: analysis.objective_assessment.confidence,
        keyDifferences: toArray(analysis.key_differences),
        talkingPoints: toArray(analysis.salesperson_talking_points),
      })),
    [analyses]
  );

  const isGreen = useMemo(() => makeIsGreen(data), [data]);

  const normalizedTables = useMemo(() => {
    if (!Array.isArray(comparisonTables)) {
      return [];
    }

    return comparisonTables.map((table, tableIndex) => {
      const headers = Array.isArray(table.template_row) ? table.template_row : [];
      const rows = Array.isArray(table.rows) ? table.rows : [];
      const metadata = table.metadata ?? {};
      const columnOrder = Array.isArray(metadata.column_labels)
        ? metadata.column_labels
        : headers.map((_, headerIndex) => String.fromCharCode(65 + headerIndex));
      const dataRows = rows.filter((_, rowIndex) => rowIndex !== 0);
      const displayCategory = metadata.category ?? "Comparison Table";
      const id = `${displayCategory}-${tableIndex}`;

      return {
        id,
        displayCategory,
        headers,
        dataRows,
        metadata,
        columnOrder,
        originalIndex: tableIndex,
      };
    });
  }, [comparisonTables]);

  const handleDownloadJson = () => {
    try {
      const blob = new Blob([demoJsonString], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "comparison-demo-results.json";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to download comparison json", error);
      toast.error("Unable to download the comparison file in demo mode");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
        <div className="flex gap-2 justify-end">
          <Button variant="outline" size="sm" onClick={handleDownloadJson}>
            <Download className="mr-2 h-4 w-4" />
            Download JSON
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              onShare?.();
            }}
          >
            <Share className="mr-2 h-4 w-4" />
            Share
          </Button>
        </div>
      </div>

      <Tabs
        defaultValue={generalSummary ? "recommendation" : "analysis"}
        className="space-y-4"
      >
        <TabsList className="w-full max-w-2xl">
          <TabsTrigger
            value="recommendation"
            className="flex-1"
            disabled={!generalSummary}
          >
            Overall Recommendation
          </TabsTrigger>
          <TabsTrigger value="analysis" className="flex-1">
            Category Insights
          </TabsTrigger>
          <TabsTrigger value="tables" className="flex-1">
            Comparison Tables
          </TabsTrigger>
        </TabsList>

        {generalSummary && (
          <TabsContent value="recommendation" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Trophy className="h-5 w-5 text-primary" />
                  Overall Recommendation
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground whitespace-pre-line">
                  {generalSummary.key_differences}
                </p>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <h3 className="text-sm font-semibold uppercase text-muted-foreground">
                      ProBTP Strengths
                    </h3>
                    <ul className="mt-2 space-y-1 text-sm list-disc pl-4">
                      {toArray(generalSummary.probtp_overall_strengths).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold uppercase text-muted-foreground">
                      AXA Strengths
                    </h3>
                    <ul className="mt-2 space-y-1 text-sm list-disc pl-4">
                      {toArray(generalSummary.axa_overall_strengths).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {!generalSummary && (
          <TabsContent value="recommendation" className="space-y-4">
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                Overall recommendation data is not available for this comparison.
              </CardContent>
            </Card>
          </TabsContent>
        )}

        <TabsContent value="analysis" className="space-y-4">
          {categorySummary.map((category, index) => {
            const stateKey = `${category.category || "category"}-${index}`;
            const isExpanded = expandedCategories[stateKey] ?? index === 0;
            const panelId = `category-panel-${index}`;

            const toggleCategory = () => {
              setExpandedCategories((prev) => ({
                ...prev,
                [stateKey]: !(prev[stateKey] ?? index === 0),
              }));
            };

            return (
              <Card key={stateKey}>
                <CardHeader
                  className="flex flex-col gap-2 cursor-pointer"
                  role="button"
                  tabIndex={0}
                  aria-expanded={isExpanded}
                  aria-controls={panelId}
                  onClick={toggleCategory}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      toggleCategory();
                    }
                  }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="flex flex-wrap items-center gap-2">
                      {category.category}
                      <Badge variant={category.winner === "probtp" ? "default" : "secondary"}>
                        Winner: {category.winner.toUpperCase()}
                      </Badge>
                      <Badge variant="outline">Confidence: {category.confidence}</Badge>
                    </CardTitle>
                    <ChevronDown
                      className={`h-4 w-4 transition-transform ${
                        isExpanded ? "rotate-0" : "-rotate-90"
                      }`}
                    />
                  </div>
                </CardHeader>
                {isExpanded && (
                  <CardContent
                    id={panelId}
                    className="space-y-4 text-sm"
                  >
                    <div>
                      <h4 className="font-semibold text-muted-foreground">
                        Key Differences
                      </h4>
                      <ul className="mt-2 space-y-1 list-disc pl-4">
                        {category.keyDifferences.slice(0, 4).map((diff) => (
                          <li key={diff}>{diff}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <h4 className="font-semibold text-muted-foreground">
                        Talking Points
                      </h4>
                      <ul className="mt-2 space-y-1 list-disc pl-4">
                        {category.talkingPoints.slice(0, 4).map((point) => (
                          <li key={point}>{point}</li>
                        ))}
                      </ul>
                    </div>
                  </CardContent>
                )}
              </Card>
            );
          })}
        </TabsContent>

        <TabsContent value="tables" className="space-y-4">
          {normalizedTables.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                No structured comparison tables were provided in this demo dataset.
              </CardContent>
            </Card>
          ) : (
            <Tabs
              defaultValue={normalizedTables[0].id}
              className="space-y-4"
            >
              <TabsList className="w-full overflow-x-auto">
                {normalizedTables.map((table) => (
                  <TabsTrigger
                    key={`table-tab-${table.id}`}
                    value={table.id}
                    className="whitespace-nowrap"
                  >
                    {table.displayCategory}
                  </TabsTrigger>
                ))}
              </TabsList>

              {normalizedTables.map((table) => {
                const category =
                  table.metadata?.category?.trim() ??
                  analyses?.[table.originalIndex]?.category?.trim();
                const columnIndex = (cellId?: string) => {
                  if (!cellId) return Number.MAX_SAFE_INTEGER;
                  const match = cellId.match(/[A-Za-z]+/);
                  const columnLabel = match ? match[0].toUpperCase() : null;
                  if (!columnLabel) return Number.MAX_SAFE_INTEGER;
                  const lookupIndex = table.columnOrder.findIndex(
                    (label) => label.toUpperCase() === columnLabel
                  );
                  return lookupIndex === -1 ? Number.MAX_SAFE_INTEGER : lookupIndex;
                };

                return (
                  <TabsContent key={`table-content-${table.id}`} value={table.id}>
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-lg">
                          <span>{table.displayCategory}</span>
                          <span className="text-sm font-normal text-muted-foreground">
                            ProBTP: {table.metadata?.policy_levels?.probtp?.join(", ") ?? "N/A"} · AXA: {table.metadata?.policy_levels?.axa?.join(", ") ?? "N/A"}
                          </span>
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="w-full overflow-x-auto">
                          <table className="min-w-full border text-sm">
                            <thead>
                              <tr className="bg-muted/60">
                                {table.headers.map((header, headerIndex) => {
                                  const label = typeof header === "string" && header.trim().length > 0 ? header : "\u00A0";
                                  return (
                                    <th
                                      key={`header-${table.id}-${headerIndex}`}
                                      className="border px-3 py-2 text-left font-semibold"
                                    >
                                      {label}
                                    </th>
                                  );
                                })}
                              </tr>
                            </thead>
                            <tbody>
                              {table.dataRows.map((row, rowIndex) => {
                                const visibleCells = Array.isArray(row.cells)
                                  ? row.cells.filter((cell) => !("ref" in cell))
                                  : [];
                                const sortedCells = [...visibleCells].sort(
                                  (a, b) => columnIndex(a.id) - columnIndex(b.id)
                                );

                                return (
                                  <tr
                                    key={`row-${table.id}-${rowIndex}`}
                                    className="odd:bg-muted/30"
                                  >
                                    {sortedCells.map((cell, cellIndex) => {
                                      const cellRecord = cell as {
                                        id?: string;
                                        is_best?: boolean | null;
                                        colspan?: number;
                                        rowspan?: number;
                                        type?: string;
                                      };
                                      const cellIsGreen = isGreen(category, {
                                        id: cellRecord.id ?? "",
                                        is_best: cellRecord.is_best,
                                      });

                                      const cellValue =
                                        cell.value != null ? String(cell.value) : "";
                                      const displayValue =
                                        cellValue.trim().length > 0 ? cellValue : "—";
                                      const colSpan = cellRecord.colspan ?? 1;
                                      const rowSpan = cellRecord.rowspan ?? 1;
                                      const rawType = typeof cellRecord.type === "string"
                                        ? cellRecord.type.trim()
                                        : undefined;
                                      const showType = rawType && rawType.toLowerCase() !== "data";

                                      const cellBackgroundClass = cellIsGreen
                                        ? "bg-emerald-100 dark:bg-emerald-900/40 border-emerald-200 dark:border-emerald-700"
                                        : "";

                                      const textClass = cellIsGreen
                                        ? "text-emerald-700 dark:text-emerald-300 font-semibold"
                                        : displayValue === "—"
                                        ? "text-muted-foreground"
                                        : "";

                                      return (
                                        <td
                                          key={`cell-${cell.id ?? cellIndex}`}
                                          className={cn("border px-3 py-2 align-top", cellBackgroundClass)}
                                          colSpan={colSpan}
                                          rowSpan={rowSpan}
                                          data-cell-id={cell.id}
                                        >
                                          <div className="space-y-1">
                                            <span className={cn("inline-block", textClass)}>
                                              {displayValue}
                                            </span>
                                            {showType ? (
                                              <p className="text-xs uppercase text-muted-foreground">
                                                {rawType}
                                              </p>
                                            ) : null}
                                          </div>
                                        </td>
                                      );
                                    })}
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    </Card>
                  </TabsContent>
                );
              })}
            </Tabs>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default DemoComparisonResults;
