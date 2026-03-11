import React, { useState } from "react";

interface CommandInputProps {
  disabled: boolean;
  onRun?: () => void;
}

export const CommandInput: React.FC<CommandInputProps> = ({ disabled, onRun }) => {
  const [inputValue, setInputValue] = useState("");

  const handleRun = () => {
    if (!inputValue.trim() || disabled) return;

    onRun?.();

    chrome.runtime.sendMessage({
      source: "sidepanel",
      payload: {
        type: "run",
        data: { command: inputValue.trim() },
      },
    });
    setInputValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleRun();
    }
  };

  return (
    <div className="flex gap-2 w-full">
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder="What should I do?"
        className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-500"
        data-testid="command-input"
      />
      <button
        onClick={handleRun}
        disabled={disabled || !inputValue.trim()}
        className="px-4 py-2 bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700 disabled:bg-blue-300 disabled:cursor-not-allowed transition-colors"
        data-testid="run-button"
      >
        Run
      </button>
    </div>
  );
};
