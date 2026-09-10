"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { uploadFiles } from "@/lib/api";
import type { ProductCode } from "@/lib/products";

const TTL_OPTIONS = [
  { hours: 24, label: "24 часа" },
  { hours: 72, label: "3 дня" },
  { hours: 168, label: "7 дней" },
];

export type UploadFormProps = {
  productCode: ProductCode;
  heading: string;
  subheading: string;
  consentProductLabel: string;
  submitLabel?: string;
};

export default function UploadForm({
  productCode,
  heading,
  subheading,
  consentProductLabel,
  submitLabel = "Запустить бесплатную диагностику",
}: UploadFormProps) {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [consent, setConsent] = useState(false);
  const [ttlHours, setTtlHours] = useState(72);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((incoming: FileList | null) => {
    if (!incoming) return;
    setFiles((prev) => [...prev, ...Array.from(incoming)]);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragActive(false);
      addFiles(e.dataTransfer.files);
    },
    [addFiles]
  );

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSubmit = async () => {
    setError(null);
    if (files.length === 0) {
      setError("Добавьте хотя бы один файл.");
      return;
    }
    if (!consent) {
      setError("Необходимо согласие на обработку файлов.");
      return;
    }
    setLoading(true);
    try {
      const result = await uploadFiles(files, ttlHours, consent, productCode);
      router.push(`/result/${result.batch_id}`);
    } catch (e: any) {
      setError(e.message || "Не удалось загрузить файлы. Попробуйте ещё раз.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="container">
      <h1 style={{ fontSize: 24 }}>{heading}</h1>
      <p className="subtitle">{subheading}</p>

      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}

      <div
        className={`dropzone${dragActive ? " active" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Перетащите файлы сюда или нажмите, чтобы выбрать"
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          style={{ display: "none" }}
          onChange={(e) => addFiles(e.target.files)}
        />
        Перетащите файлы сюда или нажмите, чтобы выбрать
      </div>

      {files.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          {files.map((f, idx) => (
            <div className="file-row" key={`${f.name}-${idx}`}>
              <span>
                {f.name} ({(f.size / 1024).toFixed(0)} КБ)
              </span>
              <button className="btn secondary" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => removeFile(idx)}>
                Удалить
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="field-row" style={{ marginTop: 24 }}>
        <label>Срок автоматического удаления файлов</label>
        <div className="radio-group">
          {TTL_OPTIONS.map((opt) => (
            <div
              key={opt.hours}
              className={`radio-option${ttlHours === opt.hours ? " selected" : ""}`}
              onClick={() => setTtlHours(opt.hours)}
              role="radio"
              aria-checked={ttlHours === opt.hours}
              tabIndex={0}
            >
              {opt.label}
            </div>
          ))}
        </div>
      </div>

      <div className="field-row">
        <label style={{ display: "flex", alignItems: "flex-start", gap: 10, fontWeight: 400 }}>
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} style={{ marginTop: 3 }} />
          <span>
            Я согласен(-на) на техническую обработку загруженных файлов сервисом {consentProductLabel} и ознакомлен(-а) с{" "}
            <a href="/privacy" target="_blank">
              политикой конфиденциальности
            </a>
            . Файлы будут автоматически удалены по истечении выбранного срока.
          </span>
        </label>
      </div>

      <button className="btn" onClick={handleSubmit} disabled={loading}>
        {loading ? "Проверяем…" : submitLabel}
      </button>
    </main>
  );
}
