import React, { useState, useEffect } from "react";

interface ConnectionStatusProps {
  connected: boolean;
  onRetry?: () => void;
}

export const ConnectionStatus: React.FC<ConnectionStatusProps> = ({ connected, onRetry }) => {
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    if (connected) {
      setRetrying(false);
    }
  }, [connected]);

  const handleRetry = () => {
    if (retrying) return;
    setRetrying(true);
    onRetry?.();
    // Auto-reset after 5 seconds if still not connected
    setTimeout(() => setRetrying(false), 5000);
  };

  return (
    <div className="flex items-center gap-2 text-sm font-medium" data-testid="connection-status">
      <div className={`w-2.5 h-2.5 rounded-full ${
        connected ? "bg-green-500" : retrying ? "bg-yellow-500 animate-pulse" : "bg-red-500"
      }`} />
      <span className={
        connected ? "text-green-700" : retrying ? "text-yellow-600" : "text-red-700"
      }>
        {connected ? "Connected" : retrying ? "Connecting..." : "Disconnected"}
      </span>
      {!connected && !retrying && onRetry && (
        <button
          onClick={handleRetry}
          className="ml-1 px-2 py-0.5 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
        >
          Retry
        </button>
      )}
      {retrying && (
        <svg className="animate-spin h-3.5 w-3.5 text-yellow-600" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
    </div>
  );
};
