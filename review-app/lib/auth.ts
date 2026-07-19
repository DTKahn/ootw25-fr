export const SESSION_COOKIE = "session";

export function checkPassword(candidate: string): boolean {
  const expected = process.env.REVIEW_APP_PASSWORD;
  if (!expected) throw new Error("REVIEW_APP_PASSWORD is not set");
  return candidate === expected;
}

// The cookie value is a separate secret from the password itself, so a
// leaked cookie doesn't directly reveal the login password.
export function getExpectedSessionValue(): string {
  const secret = process.env.AUTH_SECRET;
  if (!secret) throw new Error("AUTH_SECRET is not set");
  return secret;
}
