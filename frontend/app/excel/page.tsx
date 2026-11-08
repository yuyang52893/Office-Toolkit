import type { Metadata } from "next";

import { ExcelWorkspace } from "./excel-workspace";

export const metadata: Metadata = {
  title: "Excel / CSV 拆分合并",
  description:
    "在线按工作表、行数或列值拆分 Excel、XLS、CSV，合并多个表格，支持去除空行和重复行。",
};

export default function ExcelPage() {
  return <ExcelWorkspace />;
}

