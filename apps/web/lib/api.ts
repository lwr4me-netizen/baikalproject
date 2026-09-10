import type { ProductCode } from "@/lib/products";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type Issue = {
  rule_code: string;
  severity: "critical" | "warning" | "recommendation";
  message: string;
  auto_fixable: boolean;
};

export type FileResult = {
  original_filename: string;
  size_bytes: number;
  page_count: number | null;
  issues: Issue[];
};

export type Diagnostics = {
  batch_id: string;
  product_code: ProductCode;
  file_count: number;
  critical_count: number;
  warning_count: number;
  recommendation_count: number;
  categories: string[];
  files_needing_fix: string[];
  auto_fixable_count: number;
  files: FileResult[];
  can_download_free: boolean;
};

export type PaymentOut = {
  payment_id: string;
  product_code: ProductCode;
  status: string;
  confirmation_url: string | null;
  amount_value: string;
  currency: string;
};

export type JobStatus = {
  job_id: string;
  product_code: ProductCode;
  status: string;
  operations_performed: string[];
  download_token: string | null;
  expires_at: string | null;
};

async function jsonOrThrow(resp: Response) {
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return resp.json();
}

export async function uploadFiles(
  files: File[],
  ttlHours: number,
  consent: boolean,
  productCode: ProductCode = "ARBITRPACK"
): Promise<Diagnostics> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  form.append("consent_given", String(consent));
  form.append("ttl_hours", String(ttlHours));
  form.append("product_code", productCode);

  const resp = await fetch(`${API_BASE}/api/upload`, {
    method: "POST",
    body: form,
    credentials: "include",
  });
  return jsonOrThrow(resp);
}

export async function getDiagnostics(batchId: string): Promise<Diagnostics> {
  const resp = await fetch(`${API_BASE}/api/batches/${batchId}/diagnostics`, { credentials: "include" });
  return jsonOrThrow(resp);
}

export async function createPayment(batchId: string): Promise<PaymentOut> {
  const resp = await fetch(`${API_BASE}/api/payments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ batch_id: batchId }),
  });
  return jsonOrThrow(resp);
}

export async function confirmMockPayment(providerPaymentId: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/mock/${providerPaymentId}/confirm`, { method: "POST", credentials: "include" });
  await jsonOrThrow(resp);
}

export async function getJobStatus(batchId: string): Promise<JobStatus> {
  const resp = await fetch(`${API_BASE}/api/batches/${batchId}/job`, { credentials: "include" });
  return jsonOrThrow(resp);
}

export async function deleteBatchNow(batchId: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/batches/${batchId}/delete`, { method: "POST", credentials: "include" });
  await jsonOrThrow(resp);
}

export function downloadUrl(token: string): string {
  return `${API_BASE}/api/download/${token}`;
}
