import { NextRequest, NextResponse } from "next/server";
import { updateRow, isValidStatus, type RowPatch } from "@/lib/rows";

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return NextResponse.json({ error: "invalid body" }, { status: 400 });
  }

  const patch: RowPatch = {};
  if ("reviewerFrench" in body) {
    if (typeof body.reviewerFrench !== "string") {
      return NextResponse.json({ error: "reviewerFrench must be a string" }, { status: 400 });
    }
    patch.reviewerFrench = body.reviewerFrench;
  }
  if ("notes" in body) {
    if (typeof body.notes !== "string") {
      return NextResponse.json({ error: "notes must be a string" }, { status: 400 });
    }
    patch.notes = body.notes;
  }
  if ("status" in body) {
    if (!isValidStatus(body.status)) {
      return NextResponse.json({ error: "invalid status" }, { status: 400 });
    }
    patch.status = body.status;
  }

  const updated = await updateRow(id, patch);
  if (!updated) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json({ row: updated });
}
