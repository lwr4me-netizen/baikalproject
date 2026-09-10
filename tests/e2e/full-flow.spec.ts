import { test, expect } from "@playwright/test";
import path from "path";

const SAMPLE_PDF = path.join(__dirname, "fixtures", "sample.pdf");

test("сквозной сценарий: загрузка -> диагностика -> тестовая оплата -> обработка -> скачивание", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Проверьте документы/ })).toBeVisible();

  await page.getByRole("link", { name: "Проверить документы" }).click();
  await expect(page).toHaveURL(/\/upload/);

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(SAMPLE_PDF);
  await expect(page.getByText("sample.pdf")).toBeVisible();

  await page.locator('input[type="checkbox"]').check();
  await page.getByRole("button", { name: "Запустить бесплатную диагностику" }).click();

  await expect(page).toHaveURL(/\/result\//, { timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "Результат бесплатной диагностики" })).toBeVisible();

  await page.getByRole("button", { name: /Перейти к оплате/ }).click();
  await expect(page.getByRole("heading", { name: "Оплата технической подготовки" })).toBeVisible();

  await page.getByRole("button", { name: /Оплатить/ }).click();

  await expect(page.getByRole("heading", { name: "Готово!" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("link", { name: /Скачать архив/ })).toBeVisible();
});
