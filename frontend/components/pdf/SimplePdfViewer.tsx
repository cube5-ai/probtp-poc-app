"use client";

import React, { useState, useEffect, useRef } from "react";
import "react-pdf-highlighter/dist/style.css";
import {
  PdfLoader,
  PdfHighlighter,
  Highlight,
  AreaHighlight,
} from "react-pdf-highlighter";
import type { IHighlight } from "react-pdf-highlighter";
import Spinner from "./Spinner";
import { CustomHighlight } from "./types";

interface Props {
  url: string;
  highlight: CustomHighlight | null;
}

const SimplePdfViewer: React.FC<Props> = ({ url, highlight }) => {
  const [highlights, setHighlights] = useState<CustomHighlight[]>([]);
  const scrollViewerTo = useRef<(highlight: IHighlight) => void>(() => {});
  const pendingHighlight = useRef<CustomHighlight | null>(null);

  useEffect(() => {
    console.log("Setting highlights:", highlight);
    if (highlight) {
      setHighlights([highlight]);
      pendingHighlight.current = highlight;
    } else {
      setHighlights([]);
      pendingHighlight.current = null;
    }
  }, [highlight, url]);

  return (
    <div
      style={{
        display: "flex",
        position: "absolute",
        top: 0,
        left: 0,
        bottom: 0,
        right: 0,
      }}
    >
      <div
        style={{
          height: "100%",
          flexGrow: 1,
          position: "relative",
        }}
      >
        <PdfLoader url={url} beforeLoad={<Spinner />}>
          {(pdfDocument) => {
            console.log("PDF document loaded");
            return (
              <PdfHighlighter
                pdfDocument={pdfDocument}
                enableAreaSelection={() => false}
                onScrollChange={() => {}}
                scrollRef={(scrollTo) => {
                  console.log(
                    "ScrollRef called, pendingHighlight:",
                    pendingHighlight.current
                  );
                  scrollViewerTo.current = scrollTo;

                  // Manual scroll to page using DOM
                  if (pendingHighlight.current) {
                    const pageNumber =
                      pendingHighlight.current.position.pageNumber;
                    console.log("Attempting to scroll to page:", pageNumber);

                    const scrollToPageManually = () => {
                      // Find the PDF container
                      const container =
                        document.querySelector(".PdfHighlighter");
                      if (!container) {
                        console.log("Container not found");
                        return;
                      }

                      // Find all page elements
                      const pages = container.querySelectorAll(".page");
                      console.log(`Found ${pages.length} pages`);

                      if (pages.length === 0) return;

                      // Get the target page (pageNumber is 1-indexed)
                      const targetPage = pages[pageNumber - 1];
                      if (targetPage) {
                        console.log(`Scrolling to page ${pageNumber}`);
                        targetPage.scrollIntoView({
                          behavior: "smooth",
                          block: "start",
                        });
                      } else {
                        console.log(`Page ${pageNumber} not found`);
                      }
                    };

                    // Try multiple times with delays
                    setTimeout(scrollToPageManually, 100);
                    setTimeout(scrollToPageManually, 500);
                    setTimeout(scrollToPageManually, 1000);
                  }
                }}
                onSelectionFinished={() => {}}
                highlightTransform={(
                  highlight,
                  index,
                  setTip,
                  hideTip,
                  viewportToScaled,
                  screenshot,
                  isScrolledTo
                ) => {
                  console.log(`Rendering highlight ${index}:`, {
                    id: highlight.id,
                    pageNumber: highlight.position.pageNumber,
                    isScrolledTo,
                    boundingRect: highlight.position.boundingRect,
                  });

                  const isTextHighlight = !highlight.content?.image;

                  const component = isTextHighlight ? (
                    <div
                      key={`text-${highlight.id}-${index}`}
                      style={{
                        backgroundColor: "rgba(255, 255, 0, 0.3)",
                        border: "2px solid #ffff00",
                        cursor: "pointer",
                      }}
                    >
                      <Highlight
                        isScrolledTo={isScrolledTo}
                        position={highlight.position}
                        comment={highlight.comment}
                      />
                    </div>
                  ) : (
                    <div
                      key={`area-${highlight.id}-${index}`}
                      style={{
                        backgroundColor: "rgba(255, 255, 0, 0.3)",
                        border: "2px solid #ffff00",
                        cursor: "pointer",
                      }}
                    >
                      <AreaHighlight
                        isScrolledTo={isScrolledTo}
                        highlight={highlight}
                        onChange={() => {}}
                      />
                    </div>
                  );

                  return component;
                }}
                highlights={highlights}
              />
            );
          }}
        </PdfLoader>
      </div>
    </div>
  );
};

export default SimplePdfViewer;
