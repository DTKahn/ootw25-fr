import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE, getExpectedSessionValue } from "@/lib/auth";

export function middleware(request: NextRequest) {
  const session = request.cookies.get(SESSION_COOKIE)?.value;

  let expected: string;
  try {
    expected = getExpectedSessionValue();
  } catch {
    // If AUTH_SECRET is not configured, redirect to login rather than crash.
    // This makes the misconfiguration explicit to the developer.
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (session && session === expected) {
    return NextResponse.next();
  }
  return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
  matcher: ["/review/:path*", "/api/rows/:path*", "/api/export/:path*"],
};
