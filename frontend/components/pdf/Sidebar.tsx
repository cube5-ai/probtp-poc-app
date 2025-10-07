import React from "react";
import type { CustomHighlight } from "./types";
import { Separator } from "@/components/ui/separator";

interface Props {
  highlights: CustomHighlight[];
  onHighlightClick: (highlight: CustomHighlight) => void;
  selectedHighlightId: string | null;
}

const Sidebar: React.FC<Props> = ({
  highlights,
  onHighlightClick,
  selectedHighlightId,
}) => {
  return (
    <div
      className="sidebar"
      style={{ width: "25%", padding: "1rem", overflowY: "auto" }}
    >
      <h2 className="text-lg font-bold">Highlights</h2>
      <Separator className="my-4" />
      <ul className="pl-4">
        {highlights.map((highlight, index) => {
          const isSelected = selectedHighlightId === highlight.id;
          return (
            <li
              key={index}
              className="sidebar__highlight"
              onClick={() => onHighlightClick(highlight)}
              style={{
                cursor: "pointer",
                marginBottom: "1rem",
                padding: "0.5rem",
                borderRadius: "4px",
                backgroundColor: isSelected ? "#e3f2fd" : "transparent",
                border: isSelected
                  ? "2px solid #2196f3"
                  : "1px solid transparent",
                transition: "all 0.2s ease",
              }}
            >
              <div>
                {highlight.content.text && (
                  <>
                    <span className="truncate max-w-[50px]">{`${highlight.content.text.trim()}`}</span>
                    <div className="text-sm text-gray-500">
                      Page {highlight.position.pageNumber}
                    </div>
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
};

export default Sidebar;
