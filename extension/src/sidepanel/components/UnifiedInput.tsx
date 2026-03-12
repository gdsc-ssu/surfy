import React, { useState, KeyboardEvent } from "react";
import { InterruptData } from "../types";

interface UnifiedInputProps {
  state: {
    connected: boolean;
    running: boolean;
    done: boolean;
    error: string | null;
    interrupt: InterruptData | null;
  };
  onRun: (command: string) => void;
  onChat: (text: string) => void;
  disabled?: boolean;
}

export const UnifiedInput: React.FC<UnifiedInputProps> = ({ state, onRun, onChat, disabled }) => {
  const [inputValue, setInputValue] = useState("");

  const isIdle = !state.running && !state.done && !state.error;
  const isRunning = state.running && !state.interrupt;
  const isInterrupt = !!state.interrupt;
  const isDone = state.done && !state.error;
  const isError = !!state.error;

  let placeholder = "";
  let buttonLabel = "";
  let action: "run" | "chat" = "run";

  if (isIdle) {
    placeholder = "무엇을 도와드릴까요?";
    buttonLabel = "실행";
    action = "run";
  } else if (isRunning) {
    placeholder = "메시지 입력...";
    buttonLabel = "전송";
    action = "chat";
  } else if (isInterrupt) {
    placeholder = "계획을 어떻게 수정할까요?";
    buttonLabel = "전송";
    action = "chat";
  } else if (isDone) {
    placeholder = "다른 명령을 입력하세요";
    buttonLabel = "실행";
    action = "run";
  } else if (isError) {
    placeholder = "다시 시도하거나 새 명령 입력";
    buttonLabel = "실행";
    action = "run";
  }

  const handleSend = () => {
    if (!inputValue.trim() || disabled || !state.connected) return;
    
    if (action === "run") {
      onRun(inputValue.trim());
    } else {
      onChat(inputValue.trim());
    }
    setInputValue("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex gap-2 w-full">
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled || !state.connected}
        className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:text-gray-500"
        data-testid="unified-input"
      />
      <button
        onClick={handleSend}
        disabled={disabled || !state.connected || !inputValue.trim()}
        className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
        data-testid="unified-send-button"
      >
        {buttonLabel}
      </button>
    </div>
  );
};
