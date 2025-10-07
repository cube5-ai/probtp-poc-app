import { buildBestLookup, makeIsGreen, type Report } from "./isBest";

declare const describe: (name: string, fn: () => void) => void;
declare const it: (name: string, fn: () => void) => void;
declare const expect: (value: unknown) => { toBe(expected: unknown): void };

describe("buildBestLookup", () => {
  it("collects per-category best flags", () => {
    const analyses: NonNullable<Report["analyses"]> = [
      {
        category: "Benefits ",
        annotated_table: {
          rows: [
            {
              cells: [
                { id: " A1 ", is_best: true },
                { id: "B1", is_best: false },
                { id: "C1" },
              ],
            },
            {
              cells: [
                { id: "A2", is_best: true },
                { id: "B2", is_best: null },
              ],
            },
          ],
        },
      },
      {
        category: "",
        annotated_table: {
          rows: [
            {
              cells: [
                { id: "ignored", is_best: true },
              ],
            },
          ],
        },
      },
      null as unknown as Report["analyses"][number],
      {
        category: "Pricing",
        annotated_table: {
          rows: [
            {
              cells: [
                { id: "A1", is_best: false },
                { id: "P2", is_best: true },
              ],
            },
          ],
        },
      },
    ];

    const lookup = buildBestLookup(analyses);

    expect(lookup.get("Benefits")?.get("A1")).toBe(true);
    expect(lookup.get("Benefits")?.get("B1")).toBe(false);
    expect(lookup.get("Benefits")?.has("C1")).toBe(false);
    expect(lookup.get("Benefits")?.get("B2")).toBe(false);
    expect(lookup.get("Pricing")?.get("A1")).toBe(false);
    expect(lookup.get("Pricing")?.get("P2")).toBe(true);
    expect(lookup.has("" as unknown as string)).toBe(false);
  });
});

describe("makeIsGreen", () => {
  const report: Report = {
    analyses: [
      {
        category: "Benefits",
        annotated_table: {
          rows: [
            {
              cells: [
                { id: "A1", is_best: true },
                { id: "A2", is_best: null },
              ],
            },
          ],
        },
      },
      {
        category: "Pricing",
        annotated_table: {
          rows: [
            {
              cells: [
                { id: "A1", is_best: false },
                { id: "P1", is_best: true },
              ],
            },
          ],
        },
      },
    ],
  };

  const isGreen = makeIsGreen(report);

  it("prefers the explicit cell flag when true", () => {
    expect(isGreen("Benefits", { id: "A1", is_best: true })).toBe(true);
  });

  it("prefers the explicit cell flag when false", () => {
    expect(isGreen("Benefits", { id: "A1", is_best: false })).toBe(false);
  });

  it("falls back to analyses lookup when flag missing", () => {
    expect(isGreen("Benefits", { id: "A1" })).toBe(true);
    expect(isGreen("Pricing", { id: "P1" })).toBe(true);
  });

  it("treats null flags on the cell as explicit false", () => {
    expect(isGreen("Benefits", { id: "A2", is_best: null })).toBe(false);
  });

  it("returns false when category is missing", () => {
    expect(isGreen(undefined, { id: "A1" })).toBe(false);
  });

  it("returns false when lookup lacks the cell id", () => {
    expect(isGreen("Benefits", { id: "Z9" })).toBe(false);
  });

  it("keeps category lookups isolated", () => {
    expect(isGreen("Pricing", { id: "A1" })).toBe(false);
    expect(isGreen("Benefits", { id: "A1" })).toBe(true);
  });
});
