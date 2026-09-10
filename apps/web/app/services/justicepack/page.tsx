"use client";

import Link from "next/link";
import UploadForm from "@/components/UploadForm";

export default function JusticePackPage() {
  return (
    <>
      <main className="container" style={{ marginTop: 24 }}>
        <div className="card">
          <h2>О JusticePack</h2>
          <p className="subtitle" style={{ marginTop: 0 }}>
            JusticePack — отдельный аппарат технической проверки для судов общей юрисдикции (ГАС «Правосудие»).
            Правила проверки независимо проверены по приказу Судебного департамента при Верховном Суде РФ от
            27.12.2016 № 251 и НЕ совпадают автоматически с правилами ArbitrPack (арбитражные суды, «Мой Арбитр»,
            приказ № 252) — см. <code>docs/justicepack/official-requirements.md</code>.
          </p>
          <p className="disclaimer">
            Сервис выполняет только техническую проверку файлов. Он не является юридической консультацией, не
            гарантирует принятие документов судом и не заменяет требования к содержанию процессуальных документов.
          </p>
          <p style={{ fontSize: 14, marginTop: 8 }}>
            Ищете «Мой Арбитр» (арбитражные суды)? <Link href="/upload">Перейти в ArbitrPack</Link>.
          </p>
        </div>
      </main>
      <UploadForm
        productCode="JUSTICEPACK"
        heading="Проверьте документы перед электронной подачей в суд общей юрисдикции"
        subheading="PDF, JPG или PNG. Максимум 30 МБ на файл. Файлы обрабатываются только технически, по правилам ГАС «Правосудие»."
        consentProductLabel="JusticePack"
        submitLabel="Запустить бесплатную диагностику"
      />
    </>
  );
}
