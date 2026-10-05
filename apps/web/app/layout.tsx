import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Persona · 실행 기록",
  description: "페르소나의 브라우저 실행과 화면 기록을 확인하는 연구 작업실",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
