import React from "react";
import { Plan, RouteMap } from "../types";
import { TaskCard } from "./TaskCard";

interface PlanViewProps {
  plan: Plan | null;
  routeMap: RouteMap | null;
  currentTaskIdx: number;
}

export const PlanView: React.FC<PlanViewProps> = ({
  plan,
  routeMap,
  currentTaskIdx,
}) => {
  if (!plan) {
    return (
      <div
        className="flex-1 flex items-center justify-center text-gray-500"
        data-testid="plan-view"
      >
        No active run
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto flex flex-col gap-4" data-testid="plan-view">
      <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
        <h3 className="text-sm font-bold text-blue-900 mb-1">Plan Anchor</h3>
        <p className="text-sm text-blue-800">{plan.anchor}</p>
        {plan.anchor_rationale && (
          <p className="text-xs text-blue-600 mt-2 italic">
            {plan.anchor_rationale}
          </p>
        )}
      </div>

      {routeMap && routeMap.scout_summary && (
        <div className="bg-purple-50 border border-purple-200 rounded-md p-3">
          <h3 className="text-sm font-bold text-purple-900 mb-1">Scout Summary</h3>
          <p className="text-xs text-purple-800 whitespace-pre-wrap">
            {routeMap.scout_summary}
          </p>
        </div>
      )}

      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-bold text-gray-700">Tasks</h3>
        {plan.tasks.map((task, idx) => (
          <TaskCard
            key={idx}
            task={task}
            index={idx}
            isCurrent={idx === currentTaskIdx}
            isCompleted={idx < currentTaskIdx}
          />
        ))}
      </div>
    </div>
  );
};
