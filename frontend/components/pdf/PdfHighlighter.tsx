"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import "react-pdf-highlighter/dist/style.css";
import {
  PdfLoader,
  PdfHighlighter as ReactPdfHighlighter,
  Highlight,
  Popup,
  AreaHighlight,
} from "react-pdf-highlighter";
import type { IHighlight } from "react-pdf-highlighter";

import Spinner from "./Spinner";
import HighlightPopup from "./HighlightPopup";
import Sidebar from "./Sidebar";
import { CustomHighlight } from "./types";

interface Props {
  url: string;
  initialHighlights: CustomHighlight[];
}

const PdfHighlighter: React.FC<Props> = ({ url, initialHighlights }) => {
  const [highlights, setHighlights] =
    useState<CustomHighlight[]>(initialHighlights);
  const [selectedHighlightId, setSelectedHighlightId] = useState<string | null>(
    null
  );

  const scrollViewerTo = useRef<(highlight: IHighlight) => void>(() => {});

  useEffect(() => {
    console.log("Setting highlights:", initialHighlights);
    setHighlights(initialHighlights);
  }, [initialHighlights]);

  const scrollToHighlightFromHash = useCallback(() => {
    const hash = document.location.hash;
    console.log("Hash changed to:", hash);
    if (hash.startsWith("#highlight-")) {
      const highlightId = hash.slice("#highlight-".length);
      console.log("Looking for highlight with ID:", highlightId);
      const highlight = highlights.find((h) => h.id === highlightId);
      console.log("Found highlight:", highlight);
      if (highlight) {
        setSelectedHighlightId(highlight.id);
        console.log(
          "Scroll function available:",
          typeof scrollViewerTo.current
        );
        if (
          scrollViewerTo.current &&
          typeof scrollViewerTo.current === "function"
        ) {
          console.log("Scrolling to highlight using library function");
          try {
            scrollViewerTo.current(highlight);
          } catch (error) {
            console.log("Library scroll function failed:", error);
            console.log("Falling back to manual scroll");
            // Fall through to fallback logic
          }
        }

        // Always use fallback scroll logic as backup
        console.log("Using fallback scroll logic");
        const pageNumber = highlight.position.pageNumber;
        console.log("Scrolling to page:", pageNumber);

        // Try multiple selectors to find the scrollable container
        const selectors = [
          ".App > div:last-child",
          ".react-pdf__Document",
          "[data-testid='pdf-viewer']",
          ".pdf-viewer",
        ];

        let mainContainer = null;
        for (const selector of selectors) {
          mainContainer = document.querySelector(selector);
          if (mainContainer) {
            console.log("Found container with selector:", selector);
            break;
          }
        }

        if (mainContainer) {
          console.log(
            "Container found, height:",
            mainContainer.clientHeight,
            "scrollHeight:",
            mainContainer.scrollHeight
          );

          // Try to find page elements
          const pageSelectors = [
            ".react-pdf__Page",
            "[data-page-number]",
            "[data-page]",
          ];

          let pageElements: Element[] = [];
          for (const selector of pageSelectors) {
            pageElements = Array.from(mainContainer.querySelectorAll(selector));
            if (pageElements.length > 0) {
              console.log(
                "Found page elements with selector:",
                selector,
                "count:",
                pageElements.length
              );
              break;
            }
          }

          if (pageElements.length > 0) {
            // Try to find the specific page
            let targetPage = null;
            for (const pageEl of pageElements) {
              const pageNum =
                pageEl.getAttribute("data-page-number") ||
                pageEl.getAttribute("data-page") ||
                pageEl.getAttribute("data-page-number");
              if (pageNum && parseInt(pageNum) === pageNumber) {
                targetPage = pageEl;
                console.log("Found target page element for page:", pageNumber);
                break;
              }
            }

            if (targetPage) {
              console.log("Scrolling to page element");
              targetPage.scrollIntoView({
                behavior: "smooth",
                block: "start",
              });
            } else {
              console.log("Page element not found, using scroll calculation");
              const containerHeight = mainContainer.clientHeight;
              const scrollHeight = mainContainer.scrollHeight;
              const estimatedPageHeight =
                scrollHeight / Math.max(1, pageElements.length);
              const targetScrollTop = (pageNumber - 1) * estimatedPageHeight;

              console.log("Scroll calculation:", {
                containerHeight,
                scrollHeight,
                estimatedPageHeight,
                targetScrollTop,
                pageNumber,
              });

              mainContainer.scrollTo({
                top: Math.min(targetScrollTop, scrollHeight - containerHeight),
                behavior: "smooth",
              });
            }
          } else {
            console.log(
              "No page elements found, using simple page-based scroll"
            );
            const containerHeight = mainContainer.clientHeight;
            const scrollHeight = mainContainer.scrollHeight;
            const estimatedPageHeight = scrollHeight / 3; // Assume 3 pages
            const targetScrollTop = (pageNumber - 1) * estimatedPageHeight;

            mainContainer.scrollTo({
              top: Math.min(targetScrollTop, scrollHeight - containerHeight),
              behavior: "smooth",
            });
          }
        } else {
          console.log("No scrollable container found");
        }
      }
    }
  }, [highlights]);

  useEffect(() => {
    window.addEventListener("hashchange", scrollToHighlightFromHash, false);
    return () => {
      window.removeEventListener(
        "hashchange",
        scrollToHighlightFromHash,
        false
      );
    };
  }, [scrollToHighlightFromHash]);

  const updateHash = (highlight: CustomHighlight) => {
    const newHash = `highlight-${highlight.id}`;
    console.log("Setting hash to:", newHash);
    document.location.hash = newHash;
  };

  const resetHash = () => {
    document.location.hash = "";
  };

  const handleHighlightClick = (highlight: CustomHighlight) => {
    console.log("Sidebar highlight clicked:", highlight);
    console.log("Current scroll function:", typeof scrollViewerTo.current);
    updateHash(highlight);
  };

  return (
    <div
      className="App"
      style={{
        display: "flex",
        position: "absolute",
        top: 0,
        left: 0,
        bottom: 0,
        right: 0,
      }}
    >
      <Sidebar
        highlights={highlights}
        onHighlightClick={handleHighlightClick}
        selectedHighlightId={selectedHighlightId}
      />
      <div
        style={{
          height: "100%",
          flexGrow: 1,
          position: "relative",
        }}
      >
        <PdfLoader url={url} beforeLoad={<Spinner />}>
          {(pdfDocument) => (
            <ReactPdfHighlighter
              pdfDocument={pdfDocument}
              enableAreaSelection={() => false}
              onScrollChange={resetHash}
              scrollRef={(scrollTo) => {
                console.log("Setting scroll function:", typeof scrollTo);
                scrollViewerTo.current = scrollTo;
                // Call scrollToHighlightFromHash after a short delay to ensure PDF is loaded
                setTimeout(() => {
                  scrollToHighlightFromHash();
                }, 100);
              }}
              onSelectionFinished={() => {
                // Read-only mode - no selection allowed
              }}
              highlightTransform={(
                highlight,
                index,
                setTip,
                hideTip,
                viewportToScaled,
                screenshot,
                isScrolledTo
              ) => {
                console.log(`Processing highlight ${index}:`, highlight);
                if (index === 0) {
                  console.log(
                    "Highlight object in highlightTransform:",
                    highlight
                  );
                }
                const isTextHighlight = !highlight.content?.image;
                const isSelected = selectedHighlightId === highlight.id;

                const component = isTextHighlight ? (
                  <div
                    onClick={() => {
                      console.log("PDF highlight clicked:", highlight);
                      updateHash(highlight);
                    }}
                    style={{
                      backgroundColor: isSelected
                        ? "rgba(255, 0, 0, 0.3)"
                        : "rgba(255, 255, 0, 0.3)",
                      border: isSelected
                        ? "2px solid #ff0000"
                        : "1px solid #ffff00",
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
                    onClick={() => {
                      console.log("PDF area highlight clicked:", highlight);
                      updateHash(highlight);
                    }}
                    style={{
                      backgroundColor: isSelected
                        ? "rgba(255, 0, 0, 0.3)"
                        : "rgba(255, 255, 0, 0.3)",
                      border: isSelected
                        ? "2px solid #ff0000"
                        : "1px solid #ffff00",
                      cursor: "pointer",
                    }}
                  >
                    <AreaHighlight
                      isScrolledTo={isScrolledTo}
                      highlight={highlight}
                      onChange={() => {
                        // Read-only mode - no updates allowed
                      }}
                    />
                  </div>
                );

                return (
                  <Popup
                    popupContent={<HighlightPopup {...highlight} />}
                    onMouseOver={(popupContent) =>
                      setTip(highlight, () => popupContent)
                    }
                    onMouseOut={hideTip}
                    key={index}
                  >
                    {component}
                  </Popup>
                );
              }}
              highlights={highlights}
            />
          )}
        </PdfLoader>
      </div>
    </div>
  );
};

export default PdfHighlighter;
