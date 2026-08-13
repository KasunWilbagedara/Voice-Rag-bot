import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Voice-RAG Bot | Conversational Voice AI with Document Intelligence',
  description: 'Production-grade Voice-In Voice-Out RAG web application powered by OpenAI, PostgreSQL and pgvector.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}
