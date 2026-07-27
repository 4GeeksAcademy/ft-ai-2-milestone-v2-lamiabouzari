import type { Metadata } from "next";
import { Manrope, Spectral } from "next/font/google";
import { SITE_CONTACT } from "@repo/shared-types";
import { SiteLayout } from "@/components/layout/SiteLayout";
import { sampleCartLines } from "@/data/catalog";
import "./globals.css";

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
});

const spectral = Spectral({
  variable: "--font-spectral",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_CONTACT.url),
  title: {
    default: SITE_CONTACT.brandName,
    template: `%s | ${SITE_CONTACT.brandName}`,
  },
  description:
    "French business-casual house. Discover new arrivals and best sellers in an airy Parisian-minimal setting.",
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: SITE_CONTACT.brandName,
    title: SITE_CONTACT.brandName,
    description:
      "French business-casual house. Discover new arrivals and best sellers in an airy Parisian-minimal setting.",
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_CONTACT.brandName,
    description:
      "French business-casual house. Discover new arrivals and best sellers in an airy Parisian-minimal setting.",
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
      className={`${manrope.variable} ${spectral.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col overflow-x-hidden font-sans">
        <SiteLayout cartCount={sampleCartLines.length}>{children}</SiteLayout>
      </body>
    </html>
  );
}
