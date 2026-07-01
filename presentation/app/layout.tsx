import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "L0 regularization for subnational microsimulation calibration",
  description: "Draft PolicyEngine presentation for IMA 2026.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
