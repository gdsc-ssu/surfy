import React from "react";

interface ConnectionStatusProps {
  connected: boolean;
}

export const ConnectionStatus: React.FC<ConnectionStatusProps> = ({ connected }) => {
  return (
    <div
      className="flex items-center gap-2 text-sm font-medium"
      data-testid="connection-status"
    >
      <div
        className={`w-2.5 h-2.5 rounded-full ${
          connected ? "bg-green-500" : "bg-red-500"
        }`}
      />
      <span className={connected ? "text-green-700" : "text-red-700"}>
        {connected ? "Connected" : "Disconnected"}
      </span>
    </div>
  );
};
