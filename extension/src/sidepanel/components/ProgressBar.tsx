import React from "react";

interface ProgressBarProps {
  completed: number;
  total: number;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({ completed, total }) => {
  if (total === 0) return null;

  const percentage = Math.round((completed / total) * 100);

  return (
    <div className="w-full" data-testid="progress-bar">
      <div className="flex justify-between text-xs text-gray-600 mb-1">
        <span>Progress</span>
        <span>
          {completed} / {total} ({percentage}%)
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2.5">
        <div
          className="bg-blue-600 h-2.5 rounded-full transition-all duration-500"
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
    </div>
  );
};
