import type { ReactNode } from "react";

export const metadata = { title: "OOTW25 Review" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
