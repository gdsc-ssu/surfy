import React, { useState } from "react";
import { ChatMessage } from "../types";

interface InterruptBlockProps {
  interruptData: NonNullable<ChatMessage["interruptData"]>;
  onAction: (value: any) => void;
}

export const InterruptBlock: React.FC<InterruptBlockProps> = ({ interruptData, onAction }) => {
  const [showModifyInput, setShowModifyInput] = useState(false);
  const [modifyText, setModifyText] = useState("");

  if (interruptData.interrupt_type === "plan_approval") {
    const tasks = interruptData.payload.plan?.tasks ?? [];

    return (
      <div className="bg-white border border-gray-200 rounded-md p-3 flex flex-col gap-3" data-testid="interrupt-block">
        <h3 className="text-sm font-bold text-gray-900">Approve Plan</h3>

        <div className="bg-gray-50 p-2.5 rounded border border-gray-200">
          <p className="text-xs font-semibold text-gray-700 mb-1">Anchor</p>
          <p className="text-sm text-gray-800 mb-2">{interruptData.payload.plan?.anchor}</p>
          <p className="text-xs font-semibold text-gray-700 mb-1">Tasks</p>
          <ul className="list-decimal list-inside text-sm text-gray-800 space-y-1">
            {tasks.map((task: { description?: string }, index: number) => (
              <li key={index}>{task.description}</li>
            ))}
          </ul>
        </div>

        {showModifyInput ? (
          <>
            <textarea
              value={modifyText}
              onChange={(e) => setModifyText(e.target.value)}
              className="w-full h-24 p-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              placeholder="Describe what you want to change in the plan"
              data-testid="modify-input"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  onAction({ approved: false, modification: modifyText });
                  setShowModifyInput(false);
                  setModifyText("");
                }}
                className="flex-1 bg-blue-600 text-white py-2 rounded-md font-medium"
                data-testid="send-modification-button"
              >
                Send Modification
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowModifyInput(false);
                  setModifyText("");
                }}
                className="flex-1 bg-gray-200 text-gray-800 py-2 rounded-md font-medium"
              >
                Cancel
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => onAction({ approved: true, modification: null })}
                className="flex-1 bg-green-600 text-white py-2 rounded-md font-medium"
                data-testid="approve-button"
              >
                Approve
              </button>
              <button
                type="button"
                onClick={() => setShowModifyInput(true)}
                className="flex-1 bg-blue-600 text-white py-2 rounded-md font-medium"
                data-testid="modify-button"
              >
                Modify
              </button>
            </div>
            <button
              type="button"
              onClick={() => onAction({ approved: false, modification: null })}
              className="w-full bg-gray-600 text-white py-2 rounded-md font-medium"
              data-testid="stop-button"
            >
              Stop
            </button>
          </>
        )}
      </div>
    );
  }

  if (interruptData.interrupt_type === "human_gateway") {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3 flex flex-col gap-3" data-testid="interrupt-block">
        <h3 className="text-sm font-bold text-yellow-700">사용자 확인 필요</h3>
        <div className="bg-white p-2 rounded border border-yellow-200 text-sm text-yellow-900">
          <p className="font-semibold mb-1">진행 중인 작업:</p>
          <p className="mb-2">{interruptData.payload.failed_task}</p>
          <p className="font-semibold mb-1">이유:</p>
          <p>{interruptData.payload.reason || interruptData.payload.message || "Agent needs guidance to continue."}</p>
        </div>
        <button
          type="button"
          onClick={() => onAction({ approved: true, modification: null })}
          className="w-full bg-blue-600 text-white py-2.5 rounded-md font-medium"
          data-testid="retry-button"
        >
          <div className="text-sm font-semibold">완료 — 계속 진행</div>
          <div className="text-xs opacity-80">위 작업을 직접 처리한 후 클릭하세요</div>
        </button>
        <button
          type="button"
          onClick={() => onAction({ approved: false, modification: null })}
          className="w-full bg-gray-600 text-white py-2 rounded-md font-medium text-sm"
          data-testid="stop-button"
        >
          중단
        </button>
      </div>
    );
  }

  if (interruptData.interrupt_type === "completion_check") {
    return (
      <div className="bg-green-50 border border-green-200 rounded-md p-3 flex flex-col gap-3" data-testid="interrupt-block">
        <h3 className="text-sm font-bold text-green-700">Run Complete</h3>
        <p className="text-sm text-green-800">
          Completed {interruptData.payload.completed_count ?? 0} tasks.
        </p>
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={() => onAction({ approved: false })}
            className="w-full bg-green-600 text-white py-2.5 rounded-md font-medium"
            data-testid="complete-button"
          >
            Complete
          </button>
          <button
            type="button"
            onClick={() => onAction({ approved: true })}
            className="w-full bg-blue-600 text-white py-2.5 rounded-md font-medium"
            data-testid="request-more-button"
          >
            Request More
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-md p-3 text-sm text-gray-600" data-testid="interrupt-block">
      Unknown interrupt type: {interruptData.interrupt_type}
    </div>
  );
};
