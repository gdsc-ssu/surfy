import React from "react";

interface ProgressBarProps {
  completed: number;
  total: number;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({ completed, total }) => {
  if (total === 0) {
    return (
      <div className="w-full text-xs text-gray-600 italic" data-testid="progress-bar">
        Preparing tasks...
      </div>
    );
  }

  return (
    <div className="w-full text-xs text-gray-600 font-medium" data-testid="progress-bar">
      ✓ {completed} tasks completed
    </div>
  );
};
