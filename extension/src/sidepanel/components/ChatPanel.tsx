import React from "react";
import { ChatMessage } from "../types";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";

interface ChatPanelProps {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  isInterruptActive: boolean;
  isRunning: boolean;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ 
  messages, 
  onSend, 
  isInterruptActive,
  isRunning
}) => {
  // We can send messages if we are running OR if there's an active interrupt
  const canSend = isRunning || isInterruptActive;
  
  const placeholder = isInterruptActive 
    ? "Type to modify the plan..." 
    : "Type a message...";

  return (
    <div 
      className="flex flex-col h-64 mt-4 border-t border-gray-200 pt-4"
      data-testid="chat-panel"
    >
      <h3 className="text-sm font-semibold text-gray-700 mb-2">Chat</h3>
      <MessageList messages={messages} />
      <ChatInput 
        onSend={onSend} 
        disabled={!canSend} 
        placeholder={placeholder}
      />
    </div>
  );
};
