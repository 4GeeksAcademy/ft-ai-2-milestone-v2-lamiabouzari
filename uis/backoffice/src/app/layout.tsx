import type { Metadata } from "next";
import { Bitter, Source_Sans_3 } from "next/font/google";
import { SITE_CONTACT } from "@repo/shared-types";
import { BackofficeShell } from "@/components/layout/BackofficeShell";
import "./globals.css";

const sourceSans = Source_Sans_3({
  variable: "--font-source-sans",
  subsets: ["latin"],
});

const bitter = Bitter({
  variable: "--font-bitter",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_CONTACT.url),
  title: {
    default: `Backoffice | ${SITE_CONTACT.brandName}`,
    template: `%s | ${SITE_CONTACT.brandName} Backoffice`,
  },
  description:
    "Internal operations dashboard for Maison Atelier Rue merchandising and finance snapshots.",
  robots: {
    index: false,
    follow: false,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${sourceSans.variable} ${bitter.variable} h-full antialiased`}
    >
      <body className="min-h-full font-sans text-foreground">
        <BackofficeShell>{children}</BackofficeShell>
      </body>
    </html>
  );
}
