import React, { useState } from "react";

interface CancelButtonProps {
  disabled: boolean;
  onCancel: () => void;
}

export const CancelButton: React.FC<CancelButtonProps> = ({ disabled, onCancel }) => {
  const [showConfirm, setShowConfirm] = useState(false);

  if (showConfirm) {
    return (
      <div className="flex items-center justify-between bg-red-50 border border-red-200 rounded-md p-2 mt-2">
        <span className="text-sm text-red-700 font-medium">Cancel execution?</span>
        <div className="flex gap-2">
          <button
            onClick={() => setShowConfirm(false)}
            className="px-3 py-1 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded hover:bg-gray-50"
          >
            No
          </button>
          <button
            onClick={() => {
              setShowConfirm(false);
              onCancel();
            }}
            className="px-3 py-1 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700"
            data-testid="cancel-confirm"
          >
            Yes, Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <button
      onClick={() => setShowConfirm(true)}
      disabled={disabled}
      className="w-full mt-2 px-4 py-2 bg-white border border-red-200 text-red-600 rounded-md text-sm font-medium hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      data-testid="cancel-button"
    >
      Cancel Execution
    </button>
  );
};
