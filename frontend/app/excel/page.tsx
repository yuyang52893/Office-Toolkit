import type { Metadata } from "next";

import type { ExcelMode } from "@/lib/types";
import { ExcelWorkspace } from "./excel-workspace";

export const metadata: Metadata = {
  title: "Excel / CSV 拆分合并",
  description:
    "在线按工作表、行数或列值拆分 Excel、XLS、CSV，合并多个表格，支持去除空行和重复行。",
};

const validModes: ExcelMode[] = ["by_sheet", "by_rows", "by_column", "merge"];

export default async function ExcelPage({
  searchParams,
}: {
  searchParams: Promise<{ mode?: string | string[] }>;
}) {
  const requestedMode = (await searchParams).mode;
  const mode = Array.isArray(requestedMode) ? requestedMode[0] : requestedMode;
  const initialMode = validModes.includes(mode as ExcelMode)
    ? (mode as ExcelMode)
    : "by_sheet";
  return <ExcelWorkspace initialMode={initialMode} />;
}

