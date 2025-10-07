import { IHighlight } from "react-pdf-highlighter";
import { CustomHighlight } from "@/components/pdf/types";

export const transformDataToHighlights = (
  data: any,
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

  if (!data.analyses) {
    return {};
  }

  data.analyses.forEach((analysis: any) => {
    if (!analysis.annotated_table || !analysis.annotated_table.rows) return;

    analysis.annotated_table.rows.forEach((row: any) => {
      if (!row.cells) return;
      row.cells.forEach((cell: any) => {
        if (!cell.bounding_boxes) return;

        cell.bounding_boxes.forEach((box: any, index: number) => {
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
