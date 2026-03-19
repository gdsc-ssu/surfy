import React, { useState } from "react";
import { ChatMessage } from "../types";

interface ActivityBlockProps {
  activityData: NonNullable<ChatMessage["activityData"]>;
}

export const ActivityBlock: React.FC<ActivityBlockProps> = ({ activityData }) => {
  const [expanded, setExpanded] = useState(false);
  const hasDetails = Boolean(activityData.detail) || Boolean(activityData.subSteps?.length);

  return (
    <div
      className={`flex flex-col gap-1 px-3 py-2 rounded-md text-sm border ${
        activityData.status === "running" ? "bg-blue-50 border-blue-200" : "bg-gray-50 border-gray-200"
      }`}
      data-testid="activity-block"
    >
      <button
        type="button"
        onClick={() => hasDetails && setExpanded((prev) => !prev)}
        className={`flex items-center gap-2 text-left ${hasDetails ? "cursor-pointer" : "cursor-default"}`}
        disabled={!hasDetails}
      >
        <span className="text-base">{activityData.icon}</span>
        <span
          className={`flex-1 ${
            activityData.status === "running" ? "text-blue-700 font-medium" : "text-gray-700"
          }`}
        >
          {activityData.label}
        </span>
        {activityData.status === "running" ? (
          <div className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
            <span className="text-xs text-blue-500">running</span>
          </div>
        ) : (
          <span className="text-xs text-gray-500">{activityData.duration || "done"}</span>
        )}
        {hasDetails && <span className="text-xs text-gray-400">{expanded ? "▲" : "▼"}</span>}
      </button>

      {expanded && (
        <div className="ml-6 flex flex-col gap-1">
          {activityData.detail && <p className="text-xs text-gray-600">{activityData.detail}</p>}
          {activityData.subSteps && activityData.subSteps.length > 0 && (
            <div className="flex flex-col gap-0.5 mt-0.5">
              {activityData.subSteps.map((step, index) => (
                <div key={index} className="flex items-center gap-1.5 text-xs text-gray-500">
                  <span className="text-gray-400">↳</span>
                  <span>{step.description}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
