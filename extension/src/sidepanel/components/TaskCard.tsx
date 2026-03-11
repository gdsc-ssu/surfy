import React from "react";
import { TaskItem } from "../types";

interface TaskCardProps {
  task: TaskItem;
  index: number;
  isCurrent: boolean;
  isCompleted: boolean;
}

export const TaskCard: React.FC<TaskCardProps> = ({
  task,
  index,
  isCurrent,
  isCompleted,
}) => {
  let borderClass = "border-gray-200";
  let bgClass = "bg-white";

  if (isCurrent) {
    borderClass = "border-blue-500 ring-1 ring-blue-500";
    bgClass = "bg-blue-50";
  } else if (isCompleted) {
    borderClass = "border-green-200";
    bgClass = "bg-green-50 opacity-75";
  }

  return (
    <div
      className={`p-3 rounded-md border ${borderClass} ${bgClass} transition-colors`}
      data-testid="task-card"
    >
      <div className="flex items-start gap-2">
        <div
          className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium mt-0.5 ${
            isCurrent
              ? "bg-blue-500 text-white"
              : isCompleted
              ? "bg-green-500 text-white"
              : "bg-gray-200 text-gray-600"
          }`}
        >
          {isCompleted ? "✓" : index + 1}
        </div>
        <div className="flex-1 min-w-0">
          <p
            className={`text-sm font-medium ${
              isCompleted ? "text-gray-600 line-through" : "text-gray-900"
            }`}
          >
            {task.description}
          </p>
          
          {task.target_url && (
            <p className="text-xs text-gray-500 mt-1 truncate">
              <span className="font-semibold">URL:</span> {task.target_url}
            </p>
          )}
          
          <div className="mt-2 text-xs text-gray-600 bg-white/50 p-2 rounded border border-gray-100">
            <p className="font-semibold mb-1">Success Criteria:</p>
            <ul className="list-disc list-inside space-y-0.5">
              {task.success_criteria.url_contains && (
                <li>URL contains: {task.success_criteria.url_contains}</li>
              )}
              {task.success_criteria.text_visible && (
                <li>Text visible: {task.success_criteria.text_visible}</li>
              )}
              <li>{task.success_criteria.description}</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
