"use client";

import { useEffect, useState } from "react";
import {
  Diagnostics,
  JobStatus,
  PaymentOut,
  confirmMockPayment,
  createPayment,
  deleteBatchNow,
  downloadUrl,
  getDiagnostics,
  getJobStatus,
} from "@/lib/api";
import { productOf } from "@/lib/products";

const SEVERITY_LABEL: Record<string, string> = {
  critical: "Критично",
  warning: "Предупреждение",
  recommendation: "Рекомендация",
};

export default function ResultPage({ params }: { params: { batchId: string } }) {
  const { batchId } = params;
  const [diag, setDiag] = useState<Diagnostics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stage, setStage] = useState<"loading" | "free_result" | "checkout" | "processing" | "ready">("loading");
  const [confirmationUrl, setConfirmationUrl] = useState<string | null>(null);
  const [payment, setPayment] = useState<PaymentOut | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [payLoading, setPayLoading] = useState(false);

  const product = productOf(diag?.product_code);
  const displayPriceRub = payment?.amount_value ?? product.approxPriceRub;

  useEffect(() => {
    getDiagnostics(batchId)
      .then((d) => {
        setDiag(d);
        setStage("free_result");
      })
      .catch((e) => setError(e.message));
  }, [batchId]);

  const startCheckout = async () => {
    setError(null);
    setPayLoading(true);
    try {
      const createdPayment = await createPayment(batchId);
      setPayment(createdPayment);
      setConfirmationUrl(createdPayment.confirmation_url);
      setStage("checkout");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setPayLoading(false);
    }
  };

  const simulateTestPayment = async () => {
    if (!confirmationUrl) return;
    setPayLoading(true);
    setError(null);
    try {
      const providerPaymentId = new URL(confirmationUrl).searchParams.get("mock_payment_id");
      if (!providerPaymentId) throw new Error("Не удалось определить тестовый платёж.");
      await confirmMockPayment(providerPaymentId);
      setStage("processing");
      pollJob();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setPayLoading(false);
    }
  };

  const pollJob = () => {
    const interval = setInterval(async () => {
      try {
        const j = await getJobStatus(batchId);
        setJob(j);
        if (j.status === "done") {
          clearInterval(interval);
          setStage("ready");
        } else if (j.status === "failed") {
          clearInterval(interval);
          setError("Обработка завершилась с ошибкой. Обратитесь в поддержку.");
        }
      } catch {
        /* job ещё не создан — ждём */
      }
    }, 1000);
  };

  const handleDeleteNow = async () => {
    if (!confirm("Удалить все ваши файлы прямо сейчас? Это необратимо.")) return;
    await deleteBatchNow(batchId);
    alert("Файлы удалены.");
  };

  if (stage === "loading") {
    return (
      <main className="container">
        <p>Загружаем результат диагностики…</p>
      </main>
    );
  }

  return (
    <main className="container">
      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}

      {diag && (stage === "free_result" || stage === "checkout") && (
        <>
          <h1 style={{ fontSize: 24 }}>Результат бесплатной диагностики — {product.displayName}</h1>
          <div className="stat-row">
            <div className="stat">
              <div className="num">{diag.file_count}</div>
              <div className="label">файлов</div>
            </div>
            <div className="stat">
              <div className="num" style={{ color: "var(--critical)" }}>
                {diag.critical_count}
              </div>
              <div className="label">критичных ошибок</div>
            </div>
            <div className="stat">
              <div className="num" style={{ color: "var(--warning)" }}>
                {diag.warning_count}
              </div>
              <div className="label">предупреждений</div>
            </div>
            <div className="stat">
              <div className="num" style={{ color: "var(--recommendation)" }}>
                {diag.recommendation_count}
              </div>
              <div className="label">рекомендаций</div>
            </div>
          </div>

          <div className="card">
            <h2>По файлам</h2>
            {diag.files.map((f) => (
              <div key={f.original_filename} style={{ marginBottom: 16 }}>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>
                  {f.original_filename} {f.page_count ? `· ${f.page_count} стр.` : ""}
                </div>
                {f.issues.length === 0 && <div style={{ color: "var(--muted)", fontSize: 14 }}>Проблем не найдено.</div>}
                {f.issues.map((issue, i) => (
                  <div className={`issue ${issue.severity}`} key={i}>
                    <strong>{SEVERITY_LABEL[issue.severity]}:</strong> {issue.message}
                  </div>
                ))}
              </div>
            ))}
          </div>

          {stage === "free_result" && (
            <div className="card">
              <h2>Что дальше</h2>
              <p>
                Полное исправление (удаление метаданных и EXIF), сборка итогового ZIP-архива и его скачивание доступны
                после оплаты технической обработки.
              </p>
              <button className="btn" onClick={startCheckout} disabled={payLoading}>
                Перейти к оплате — {displayPriceRub} ₽
              </button>
            </div>
          )}

          {stage === "checkout" && (
            <div className="card">
              <h2>Оплата технической подготовки</h2>
              <p>Состав услуги: автоматическая сборка итогового архива, безопасные исправления (удаление метаданных/EXIF), проверка целостности.</p>
              <p>
                <strong>Стоимость: {displayPriceRub} ₽</strong>
              </p>
              <p className="disclaimer">
                Сервис не даёт юридической гарантии принятия документов судом. Срок хранения результата — согласно
                выбранному вами сроку удаления. См. <a href="/offer">оферту</a> и{" "}
                <a href="/privacy">политику конфиденциальности</a>.
              </p>
              <button className="btn" onClick={simulateTestPayment} disabled={payLoading}>
                {payLoading ? "Обрабатываем…" : "Оплатить (тестовый режим ЮKassa / mock)"}
              </button>
            </div>
          )}
        </>
      )}

      {stage === "processing" && (
        <div className="card">
          <h2>Оплата подтверждена — готовим архив</h2>
          <p>Это займёт несколько секунд…</p>
        </div>
      )}

      {stage === "ready" && job && (
        <div className="card">
          <h2>Готово!</h2>
          <p>Выполненные операции:</p>
          <ul>
            {job.operations_performed.map((op, i) => (
              <li key={i}>{op}</li>
            ))}
          </ul>
          {job.download_token && (
            <a className="btn" href={downloadUrl(job.download_token)}>
              Скачать архив (ZIP)
            </a>
          )}
          <p className="disclaimer">
            Ссылка на скачивание временная и ограничена по времени. Ваши файлы будут автоматически удалены по
            истечении выбранного срока хранения.
          </p>
          <button className="btn secondary" onClick={handleDeleteNow} style={{ marginTop: 12 }}>
            Удалить мои файлы сейчас
          </button>
        </div>
      )}
    </main>
  );
}
