import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AutoSage — Verified Multi-Agent AutoML",
  description: "Natural-Language-Driven Automated Machine Learning with Rigorous Verification",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-slate-950 text-slate-50 antialiased">
        {children}
      </body>
    </html>
  );
}
