import { StatusBanner } from "@/components/status-banner";
import type { HistoryCapture } from "@/lib/types";

export function HistoryNotice({ capture }: { capture?: HistoryCapture | null }) {
  if (!capture) {
    return null;
  }
  if (capture.saved) {
    const notice = capture.notice?.trim();
    const formattedNotice = notice
      ? /[。！？.!?]$/.test(notice)
        ? notice
        : `${notice}。`
      : "";
    return (
      <StatusBanner tone="success">
        已保存到个人历史。
        {formattedNotice ? ` ${formattedNotice}` : ""}
      </StatusBanner>
    );
  }
  return (
    <StatusBanner tone="error">
      {capture.notice ?? "结果未保存到个人历史，当前结果仍可下载"}
    </StatusBanner>
  );
}
