import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BAIKALPROJECT — техническая проверка документов перед подачей в суд",
  description:
    "ArbitrPack («Мой Арбитр», арбитражные суды) и JusticePack (ГАС «Правосудие», суды общей юрисдикции) — техническая проверка PDF и изображений перед электронной подачей. Находит технические ошибки, готовит структуру файлов, формирует архив. Не является юридической консультацией.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <header className="header">
          <a href="/" className="logo" style={{ textDecoration: "none", color: "inherit" }}>
            BAIKALPROJECT
          </a>
          <span className="badge">техническая проверка, не юридическая консультация</span>
        </header>
        {children}
        <footer className="footer">
          BAIKALPROJECT: ArbitrPack («Мой Арбитр») и JusticePack (ГАС «Правосудие») — техническая подготовка
          документов. Не гарантирует принятие документов судом.
          <br />
          <a href="/offer">Оферта</a> · <a href="/privacy">Политика конфиденциальности</a>
        </footer>
      </body>
    </html>
  );
}
