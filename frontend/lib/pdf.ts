import { CustomHighlight } from "@/components/pdf/types";

type ComparisonData = {
  metadata?: {
    "ProBTP Document"?: string;
    "AXA Document"?: string;
  };
  comparison_tables?: ComparisonTable[];
};

type ComparisonTable = {
  rows?: ComparisonRow[];
};

type ComparisonRow = {
  cells?: ComparisonCell[];
};

type ComparisonCell = {
  id?: string;
  value?: string;
  bounding_boxes?: BoundingBox[];
};

type BoundingBox = {
  file_id: string;
  page: number;
  bounding_box: {
    x1: number;
    y1: number;
    x2: number;
    y2: number;
    width: number;
    height: number;
  };
};

export const transformDataToHighlights = (
  data: ComparisonData,
  selectedProjectFiles: { id: string; file: { name: string } }[]
): Record<string, CustomHighlight[]> => {
  const fileHighlights: Record<string, CustomHighlight[]> = {};
  const titleToIdMap: Record<string, string> = {};

  if (data.metadata) {
    const probtpTitle = data.metadata["ProBTP Document"];
    const axaTitle = data.metadata["AXA Document"];
    const probtpFile = selectedProjectFiles.find((f) =>
      f.file.name.includes("Panorama FMC 2025")
    );
    const axaFile = selectedProjectFiles.find((f) =>
      f.file.name.includes("Socle AXA")
    );

    if (probtpTitle && probtpFile) {
      titleToIdMap[probtpTitle] = probtpFile.id;
    }
    if (axaTitle && axaFile) {
      titleToIdMap[axaTitle] = axaFile.id;
    }
  }

  if (!data.comparison_tables) {
    return {};
  }

  data.comparison_tables.forEach((table) => {
    if (!table.rows) return;

    table.rows.forEach((row) => {
      if (!row.cells) return;
      row.cells.forEach((cell) => {
        if (!cell.bounding_boxes) return;

        cell.bounding_boxes.forEach((box, index) => {
          const fileId = titleToIdMap[box.file_id];
          if (!fileId) return;

          if (!fileHighlights[fileId]) {
            fileHighlights[fileId] = [];
          }

          const highlight: CustomHighlight = {
            id: `${cell.id}-${index}`,
            content: { text: cell.value },
            position: {
              pageNumber: box.page + 1,
              boundingRect: box.bounding_box,
              rects: [box.bounding_box],
            },
            comment: { text: "", emoji: "" },
          };
          fileHighlights[fileId].push(highlight);
        });
      });
    });
  });

  console.log("fileHighlights", fileHighlights);

  return fileHighlights;
};
