import React, { useEffect, useRef } from "react";
import { ChatMessage } from "../types";

interface MessageListProps {
  messages: ChatMessage[];
}

export const MessageList: React.FC<MessageListProps> = ({ messages }) => {
  const endOfMessagesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div 
      className="flex-1 overflow-y-auto p-3 space-y-3 bg-white border border-gray-200 rounded-md"
      data-testid="message-list"
    >
      {messages.length === 0 ? (
        <div className="text-center text-gray-400 text-sm mt-4">
          No messages yet.
        </div>
      ) : (
        messages.map((msg, idx) => {
          const isUser = msg.sender === "user";
          const timeString = new Date(msg.timestamp).toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
          });
          
          return (
            <div 
              key={idx} 
              className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
            >
              <div 
                className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                  isUser 
                    ? "bg-blue-600 text-white rounded-br-none" 
                    : "bg-gray-100 text-gray-800 rounded-bl-none"
                }`}
              >
                {msg.text}
              </div>
              <span className="text-xs text-gray-400 mt-1 px-1">
                {timeString}
              </span>
            </div>
          );
        })
      )}
      <div ref={endOfMessagesRef} />
    </div>
  );
};
