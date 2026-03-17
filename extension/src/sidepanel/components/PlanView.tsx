import React from "react";
import { Plan, RouteMap } from "../types";
import { TaskCard } from "./TaskCard";

interface PlanViewProps {
  plan: Plan | null;
  routeMap: RouteMap | null;
  currentTaskIdx: number;
  done: boolean;
}

export const PlanView: React.FC<PlanViewProps> = ({
  plan,
  routeMap,
  currentTaskIdx,
  done,
}) => {
  if (!plan) {
    if (routeMap && routeMap.steps && routeMap.steps.length > 0) {
      return (
        <div className="flex-1 overflow-y-auto flex flex-col gap-3" data-testid="plan-view">
          <div className="bg-purple-50 border border-purple-200 rounded-md p-3">
            <h3 className="text-sm font-bold text-purple-900 mb-2">🗺️ Scout 탐색 결과</h3>
            {routeMap.scout_summary && (
              <p className="text-sm text-purple-800 mb-3">{routeMap.scout_summary}</p>
            )}
            <div className="flex flex-col gap-1.5">
              {routeMap.steps.map((step, idx) => (
                <div key={idx} className="flex items-start gap-2 text-xs">
                  <span className="text-purple-400 mt-0.5 flex-shrink-0">{idx + 1}.</span>
                  <div className="min-w-0">
                    <span className="font-medium text-purple-900">{step.title || step.url}</span>
                    {step.action_taken && (
                      <span className="text-purple-600 ml-1">— {step.action_taken}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
            {routeMap.final_url && (
              <p className="text-xs text-purple-600 mt-2">
                최종 도달: {routeMap.final_url}
              </p>
            )}
          </div>
          {!done ? (
            <div className="flex items-center gap-2 text-sm text-gray-500 px-1">
              <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
              <span>이 정보를 바탕으로 실행 계획을 세우고 있습니다...</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
              <span className="text-base">⚠️</span>
              <span>Scout 탐색만으로 작업이 종료되었습니다. 실행 계획이 생성되지 않았습니다.</span>
            </div>
          )}
        </div>
      );
    }
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
