"use client";

import UploadForm from "@/components/UploadForm";

export default function UploadPage() {
  return (
    <UploadForm
      productCode="ARBITRPACK"
      heading="Загрузите документы"
      subheading="PDF, JPG или PNG. Максимум 30 МБ на файл. Файлы обрабатываются только технически."
      consentProductLabel="ArbitrPack"
      submitLabel="Запустить бесплатную диагностику"
    />
  );
}
