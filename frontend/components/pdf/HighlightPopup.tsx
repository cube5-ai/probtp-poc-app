import React from "react";
import { IHighlight } from "react-pdf-highlighter";

interface HighlightPopupProps extends IHighlight {}

const HighlightPopup: React.FC<HighlightPopupProps> = ({ comment }) => {
  if (!comment || !comment.text) {
    return null;
  }

  return (
    <div className="Highlight__popup">
      {comment.emoji} {comment.text}
    </div>
  );
};

export default HighlightPopup;
