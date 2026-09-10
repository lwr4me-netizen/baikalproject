import { test, expect } from "@playwright/test";
import path from "path";

const SAMPLE_PDF = path.join(__dirname, "fixtures", "sample.pdf");

test("сквозной сценарий JusticePack: выбор аппарата -> загрузка -> диагностика -> mock-оплата -> обработка -> скачивание -> удаление", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Куда вы подаёте документы?" })).toBeVisible();

  await page.getByRole("link", { name: /ГАС Правосудие/ }).click();
  await expect(page).toHaveURL(/\/services\/justicepack/);
  await expect(
    page.getByRole("heading", { name: /Проверьте документы перед электронной подачей в суд общей юрисдикции/ })
  ).toBeVisible();

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(SAMPLE_PDF);
  await expect(page.getByText("sample.pdf")).toBeVisible();

  await page.locator('input[type="checkbox"]').check();
  await page.getByRole("button", { name: "Запустить бесплатную диагностику" }).click();

  await expect(page).toHaveURL(/\/result\//, { timeout: 15_000 });
  await expect(page.getByRole("heading", { name: /Результат бесплатной диагностики — JusticePack/ })).toBeVisible();

  await page.getByRole("button", { name: /Перейти к оплате/ }).click();
  await expect(page.getByRole("heading", { name: "Оплата технической подготовки" })).toBeVisible();

  await page.getByRole("button", { name: /Оплатить/ }).click();

  await expect(page.getByRole("heading", { name: "Готово!" })).toBeVisible({ timeout: 20_000 });
  const downloadLink = page.getByRole("link", { name: /Скачать архив/ });
  await expect(downloadLink).toBeVisible();
  await expect(downloadLink).toHaveAttribute("href", /\/api\/download\//);
  // Кнопка немедленного удаления — за window.confirm(), сценарий deletion покрыт на уровне API
  // тестов (tests/test_justicepack.py::test_justicepack_manual_deletion), здесь достаточно того,
  // что она присутствует на экране.
  await expect(page.getByRole("button", { name: "Удалить мои файлы сейчас" })).toBeVisible();
});

test("ArbitrPack по-прежнему доступен напрямую после появления JusticePack (регрессия)", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Проверьте документы/ })).toBeVisible();
  await page.getByRole("link", { name: "Проверить документы" }).click();
  await expect(page).toHaveURL(/\/upload/);

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(SAMPLE_PDF);
  await page.locator('input[type="checkbox"]').check();
  await page.getByRole("button", { name: "Запустить бесплатную диагностику" }).click();

  await expect(page).toHaveURL(/\/result\//, { timeout: 15_000 });
  await expect(page.getByRole("heading", { name: /Результат бесплатной диагностики — ArbitrPack/ })).toBeVisible();
});
