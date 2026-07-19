import { NextResponse } from "next/server";
import { listRows } from "@/lib/rows";

export async function GET() {
  const rows = await listRows();
  return NextResponse.json({ rows });
}
