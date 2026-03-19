import React from "react";
import { ChatMessage } from "../types";

interface ReportBlockProps {
  reportData: NonNullable<ChatMessage["reportData"]>;
}

export const ReportBlock: React.FC<ReportBlockProps> = ({ reportData }) => {
  return (
    <div
      className="bg-green-50 border border-green-200 rounded-md p-3 flex items-start gap-2"
      data-testid="report-block"
    >
      <span className="text-green-600 mt-0.5">✅</span>
      <p className="text-sm text-green-900 whitespace-pre-wrap">{reportData.summary}</p>
    </div>
  );
};
