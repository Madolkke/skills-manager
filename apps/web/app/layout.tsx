import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/chrome";
import "./globals.css";

export const metadata: Metadata = {
  title: "SkillHub",
  description: "Eval-backed skill management platform",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
