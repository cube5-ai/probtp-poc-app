export type Report = {
  comparison_tables?: {
    metadata?: { category?: string | null };
    rows?: { cells?: { id: string; is_best?: boolean | null }[] }[];
  }[] | null;
  analyses?: {
    category?: string | null;
    annotated_table?: {
      rows?: {
        cells?: { id: string; is_best?: boolean | null }[];
      }[];
    } | null;
  }[] | null;
};

export type Analyses = Report["analyses"];
export type Lookup = Map<string, Map<string, boolean>>;

type MaybeCell = { id: string; is_best?: boolean | null } | null | undefined;

type TableCell = { id: string; is_best?: boolean | null };

type IsGreenFn = (category: string | undefined, cell: TableCell) => boolean;

function normalizeCategory(category: string | null | undefined): string {
  if (typeof category !== "string") {
    return "";
  }
  return category.trim();
}

function normalizeCellId(id: string | null | undefined): string {
  if (typeof id !== "string") {
    return "";
  }
  return id.trim();
}

export function buildBestLookup(analyses: Analyses): Lookup {
  const byCategory: Lookup = new Map();

  if (!Array.isArray(analyses)) {
    return byCategory;
  }

  for (const analysis of analyses) {
    const category = normalizeCategory(analysis?.category ?? null);
    if (!category) {
      continue;
    }

    let byId = byCategory.get(category);
    if (!byId) {
      byId = new Map<string, boolean>();
      byCategory.set(category, byId);
    }

    const rows = analysis?.annotated_table?.rows;
    if (!Array.isArray(rows)) {
      continue;
    }

    for (const row of rows) {
      const cells = row?.cells;
      if (!Array.isArray(cells)) {
        continue;
      }

      for (const cell of cells) {
        if (!cell) {
          continue;
        }

        const cellId = normalizeCellId(cell.id);
        if (!cellId) {
          continue;
        }

        if (Object.prototype.hasOwnProperty.call(cell, "is_best")) {
          byId.set(cellId, cell.is_best === true);
        }
      }
    }
  }

  return byCategory;
}

function getExplicitFlag(cell: MaybeCell): boolean | null | undefined {
  if (!cell) {
    return undefined;
  }

  if (!Object.prototype.hasOwnProperty.call(cell, "is_best")) {
    return undefined;
  }

  return cell.is_best;
}

export function makeIsGreen(report: Report): IsGreenFn {
  const bestLookup = buildBestLookup(report?.analyses ?? null);

  return (category, cell) => {
    const explicit = getExplicitFlag(cell);
    if (explicit === true) {
      return true;
    }
    if (explicit === false || explicit === null) {
      return false;
    }

    const normalizedCategory = normalizeCategory(category ?? undefined);
    const normalizedCellId = normalizeCellId(cell?.id);

    if (!normalizedCategory || !normalizedCellId) {
      return false;
    }

    return bestLookup.get(normalizedCategory)?.get(normalizedCellId) === true;
  };
}
