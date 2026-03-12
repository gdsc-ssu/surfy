import React, { useRef, useEffect } from "react";
import { ActivityLogEntry } from "../types";

interface ActivityLogProps {
  entries: ActivityLogEntry[];
}

function formatDuration(start: number, end: number | null): string {
  const elapsed = (end || Date.now()) - start;
  const seconds = Math.floor(elapsed / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

export const ActivityLog: React.FC<ActivityLogProps> = ({ entries }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries.length]);

  if (entries.length === 0) return null;

  return (
    <div className="flex flex-col gap-1 mb-4 max-h-48 overflow-y-auto">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Activity</h3>
      {entries.map((entry, idx) => (
        <div
          key={idx}
          className={`flex flex-col gap-0.5 px-3 py-1.5 rounded-md text-sm ${
            entry.status === "running"
              ? "bg-blue-50 border border-blue-200"
              : "bg-gray-50"
          }`}
        >
          <div className="flex items-center gap-2">
            <span className="text-base">{entry.icon}</span>
            <span className={`flex-1 ${entry.status === "running" ? "text-blue-700 font-medium" : "text-gray-600"}`}>
              {entry.label}
            </span>
            {entry.status === "running" ? (
              <div className="flex items-center gap-1">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                <span className="text-xs text-blue-500">running</span>
              </div>
            ) : (
              <span className="text-xs text-gray-400">
                {formatDuration(entry.startedAt, entry.endedAt)}
              </span>
            )}
          </div>
          {entry.detail && (
            <p className="text-xs text-gray-500 ml-6">{entry.detail}</p>
          )}
          {entry.subSteps && entry.subSteps.length > 0 && (
            <div className="ml-6 mt-1 flex flex-col gap-0.5">
              {entry.subSteps.map((step, stepIdx) => (
                <div key={stepIdx} className="flex items-center gap-1.5 text-xs text-gray-500">
                  <span className="text-gray-400">↳</span>
                  <span>{step.description}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
};
