import React from "react";
import { ChatMessage } from "../types";

interface PlanBlockProps {
  planData: NonNullable<ChatMessage["planData"]>;
}

export const PlanBlock: React.FC<PlanBlockProps> = ({ planData }) => {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-md p-3 flex flex-col gap-3" data-testid="plan-block">
      <div>
        <h3 className="text-sm font-bold text-blue-900 mb-1">Plan Anchor</h3>
        <p className="text-sm text-blue-800 whitespace-pre-wrap">{planData.anchor}</p>
      </div>

      {planData.anchor_rationale && (
        <p className="text-xs text-blue-600 italic whitespace-pre-wrap">{planData.anchor_rationale}</p>
      )}

      <div className="flex flex-col gap-1.5">
        <h4 className="text-xs font-semibold text-blue-900 uppercase tracking-wider">Tasks</h4>
        <ol className="list-decimal list-inside space-y-1.5">
          {planData.tasks.map((task, index) => (
            <li key={index} className="text-sm text-blue-900">
              <span className="font-medium">{task.description}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
};
