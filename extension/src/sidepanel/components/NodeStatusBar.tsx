import React from "react";

interface NodeStatusBarProps {
  currentNode: string | null;
}

export const NodeStatusBar: React.FC<NodeStatusBarProps> = ({ currentNode }) => {
  if (!currentNode) return null;

  return (
    <div
      className="w-full bg-gray-100 border-t border-gray-200 p-2 text-xs text-gray-600 flex items-center gap-2"
      data-testid="node-status"
    >
      <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
      <span>Running: {currentNode}</span>
    </div>
  );
};
