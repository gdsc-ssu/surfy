import React from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
      <span className="text-green-600 mt-0.5 flex-shrink-0">✅</span>
      <div className="text-sm text-green-900 prose prose-sm prose-green max-w-none overflow-x-auto [&_a]:text-green-700 [&_a]:underline [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0.5 [&_h2]:text-base [&_h2]:mt-2 [&_h2]:mb-1 [&_h3]:text-sm [&_h3]:mt-2 [&_h3]:mb-1 [&_p]:my-1 [&_table]:w-full [&_table]:text-xs [&_th]:bg-green-100 [&_th]:px-2 [&_th]:py-1 [&_td]:px-2 [&_td]:py-1 [&_td]:border-t [&_td]:border-green-200">
        <Markdown remarkPlugins={[remarkGfm]}>{reportData.summary}</Markdown>
      </div>
    </div>
  );
};
