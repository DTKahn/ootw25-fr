import { NextRequest, NextResponse } from "next/server";
import { listRows } from "@/lib/rows";
import { rowsToCsv, type ExportScope } from "@/lib/csv";

export async function GET(request: NextRequest) {
  const scopeParam = request.nextUrl.searchParams.get("scope");
  const scope: ExportScope = scopeParam === "changed" ? "changed" : "all";
  const rows = await listRows();
  const csv = rowsToCsv(rows, scope);
  return new NextResponse(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="ootw25-review-${scope}.csv"`,
    },
  });
}
