import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

type StatusBannerProps = {
  tone: "error" | "success" | "loading";
  children: ReactNode;
};

export function StatusBanner({ tone, children }: StatusBannerProps) {
  const styles = {
    error: "border-red-200 bg-red-50 text-red-700",
    success: "border-emerald-200 bg-emerald-50 text-emerald-700",
    loading: "border-blue-200 bg-blue-50 text-blue-700",
  };
  const Icon = tone === "error" ? AlertCircle : tone === "success" ? CheckCircle2 : Loader2;

  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm ${styles[tone]}`}
    >
      <Icon size={17} className={`mt-0.5 shrink-0 ${tone === "loading" ? "animate-spin" : ""}`} />
      <div className="leading-6">{children}</div>
    </div>
  );
}

