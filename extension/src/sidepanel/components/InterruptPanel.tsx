import React, { useState } from "react";
import { InterruptData } from "../types";

interface InterruptPanelProps {
  interrupt: InterruptData;
  onResolved: () => void;
}

export const InterruptPanel: React.FC<InterruptPanelProps> = ({ interrupt, onResolved }) => {
  const [showModifyInput, setShowModifyInput] = useState(false);
  const [modifyText, setModifyText] = useState("");

  const handleResume = (value: any) => {
    chrome.runtime.sendMessage({
      source: "sidepanel",
      payload: {
        type: "resume",
        data: {
          interrupt_type: interrupt.interrupt_type,
          value,
        },
      },
    });
    onResolved();
  };

  const renderContent = () => {
    switch (interrupt.interrupt_type) {
      case "plan_approval":
        if (showModifyInput) {
          return (
            <>
              <h3 className="text-lg font-bold text-gray-900 mb-2">Modify Plan</h3>
              <p className="text-sm text-gray-600 mb-3">
                Describe what you want to change in the plan.
              </p>
              <textarea
                value={modifyText}
                onChange={(e) => setModifyText(e.target.value)}
                className="w-full h-32 p-2 border border-gray-300 rounded-md text-sm mb-4 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                placeholder="e.g. Don't search on Google, use DuckDuckGo instead."
                data-testid="modify-input"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    handleResume({ approved: false, modification: modifyText });
                    setShowModifyInput(false);
                    setModifyText("");
                  }}
                  className="flex-1 bg-blue-600 text-white py-2 rounded-md font-medium hover:bg-blue-700 transition-colors"
                  data-testid="send-modification-button"
                >
                  Send Modification
                </button>
                <button
                  onClick={() => {
                    setShowModifyInput(false);
                    setModifyText("");
                  }}
                  className="flex-1 bg-gray-200 text-gray-800 py-2 rounded-md font-medium hover:bg-gray-300 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </>
          );
        }

        return (
          <>
            <h3 className="text-lg font-bold text-gray-900 mb-2">Approve Plan</h3>
            <div className="bg-white p-3 rounded border border-gray-200 mb-4 max-h-60 overflow-y-auto">
              <p className="font-semibold text-sm mb-1">Anchor:</p>
              <p className="text-sm text-gray-700 mb-3">{interrupt.payload.plan?.anchor}</p>
              <p className="font-semibold text-sm mb-1">Tasks:</p>
              <ul className="list-decimal list-inside text-sm text-gray-700 space-y-1">
                {interrupt.payload.plan?.tasks.map((t: any, i: number) => (
                  <li key={i}>{t.description}</li>
                ))}
              </ul>
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex gap-2">
                <button
                  onClick={() => handleResume({ approved: true, modification: null })}
                  className="flex-1 bg-green-600 text-white py-2 rounded-md font-medium hover:bg-green-700 transition-colors"
                  data-testid="approve-button"
                >
                  Approve
                </button>
                <button
                  onClick={() => setShowModifyInput(true)}
                  className="flex-1 bg-blue-600 text-white py-2 rounded-md font-medium hover:bg-blue-700 transition-colors"
                  data-testid="modify-button"
                >
                  Modify
                </button>
              </div>
              <button
                onClick={() => handleResume({ approved: false, modification: null })}
                className="w-full bg-gray-600 text-white py-2 rounded-md font-medium hover:bg-gray-700 transition-colors"
                data-testid="stop-button"
              >
                Stop
              </button>
            </div>
          </>
        );

      case "human_gateway":
        return (
          <>
            <h3 className="text-lg font-bold text-red-600 mb-2">Task Failed</h3>
            <div className="bg-red-50 p-3 rounded border border-red-200 mb-4">
              <p className="font-semibold text-sm text-red-900 mb-1">Failed Task:</p>
              <p className="text-sm text-red-800 mb-3">{interrupt.payload.failed_task}</p>
              <p className="font-semibold text-sm text-red-900 mb-1">Reason:</p>
              <p className="text-sm text-red-800">{interrupt.payload.reason}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleResume({ approved: true, modification: null })}
                className="flex-1 bg-blue-600 text-white py-2 rounded-md font-medium hover:bg-blue-700 transition-colors"
                data-testid="approve-button"
              >
                Retry
              </button>
              <button
                onClick={() => handleResume({ approved: false })}
                className="flex-1 bg-gray-600 text-white py-2 rounded-md font-medium hover:bg-gray-700 transition-colors"
                data-testid="reject-button"
              >
                Exit
              </button>
            </div>
          </>
        );

      case "completion_check":
        return (
          <>
            <h3 className="text-lg font-bold text-green-600 mb-2">Run Complete</h3>
            <div className="bg-green-50 p-3 rounded border border-green-200 mb-4">
              <p className="text-sm text-green-800 mb-2">
                Completed {interrupt.payload.completed_count} tasks.
              </p>
              <p className="font-semibold text-sm text-green-900 mb-1">Anchor:</p>
              <p className="text-sm text-green-800">{interrupt.payload.anchor}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleResume({ approved: true })}
                className="flex-1 bg-green-600 text-white py-2 rounded-md font-medium hover:bg-green-700 transition-colors"
                data-testid="approve-button"
              >
                Continue
              </button>
              <button
                onClick={() => handleResume({ approved: false })}
                className="flex-1 bg-gray-600 text-white py-2 rounded-md font-medium hover:bg-gray-700 transition-colors"
                data-testid="reject-button"
              >
                Exit
              </button>
            </div>
          </>
        );

      default:
        return (
          <div className="text-red-500">
            Unknown interrupt type: {interrupt.interrupt_type}
          </div>
        );
    }
  };

  return (
    <div
      className="absolute inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
      data-testid="interrupt-panel"
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-5 flex flex-col max-h-full">
        {renderContent()}
      </div>
    </div>
  );
};
