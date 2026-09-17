import type { Metadata } from "next";
import { Noto_Sans_KR } from "next/font/google";
import "./globals.css";
import { Toaster } from "react-hot-toast";

const notoSans = Noto_Sans_KR({
  variable: "--font-noto",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  title: "KG스틸 업무도우미",
  description: "KG스틸 당진생산지원팀 전용 시스템",
  icons: {
    icon: "/favicon.png",
    apple: "/favicon.png",
  },
  openGraph: {
    title: "KG스틸 업무도우미",
    description: "KG스틸 당진생산지원팀 전용 시스템",
    siteName: "KG스틸 업무도우미",
    images: [{ url: "/kg.jpg", width: 512, height: 512, alt: "KG스틸" }],
    locale: "ko_KR",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className={`${notoSans.variable} h-full`}>
      <body className="min-h-full font-sans bg-gray-50">
        {children}
        <Toaster position="top-center" toastOptions={{ duration: 3000 }} />
      </body>
    </html>
  );
}
