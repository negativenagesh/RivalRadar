import type { Metadata } from "next";
import {
  Archivo_Black,
  Bricolage_Grotesque,
  Fraunces,
  Space_Grotesk,
  Syne,
} from "next/font/google";
import "./globals.css";
import { AppProviders } from "@/components/app-providers";

const syne = Syne({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "700", "800"],
});

const bricolage = Bricolage_Grotesque({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const space = Space_Grotesk({
  variable: "--font-ui",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const fraunces = Fraunces({
  variable: "--font-accent",
  subsets: ["latin"],
  weight: ["500", "700"],
  style: ["normal", "italic"],
});

const archivo = Archivo_Black({
  variable: "--font-shout",
  subsets: ["latin"],
  weight: "400",
});

export const metadata: Metadata = {
  title: "RivalRadar",
  description:
    "Watches competitor social content, spots what's trending, and drafts on-brand response posts queued for human approval.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`dark ${syne.variable} ${bricolage.variable} ${space.variable} ${fraunces.variable} ${archivo.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-background font-[family-name:var(--font-body)] text-foreground">
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
