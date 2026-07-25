import type { Metadata } from "next";
import { QueryProvider } from "@/lib/query/provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ontology Manager",
  description:
    "Operational workspace for inspecting ontology structure and governed execution context.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
