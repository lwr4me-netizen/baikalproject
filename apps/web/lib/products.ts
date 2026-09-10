// Клиентский справочник продуктов ("цифровых аппаратов") — только для отображения (тексты,
// ориентировочная цена для кнопок ДО создания платежа). Источник истины по ценам/правилам —
// backend (packages/validation-rules/rules.yaml для ARBITRPACK, config/rules/gas_pravosudie.yaml
// для JUSTICEPACK). После вызова createPayment фактическая цена всегда берётся из ответа API
// (PaymentOut.amount_value), а не отсюда.

export type ProductCode = "ARBITRPACK" | "JUSTICEPACK";

export type ProductUiConfig = {
  code: ProductCode;
  displayName: string;
  targetSystem: string;
  approxPriceRub: string;
  route: string;
};

export const PRODUCTS: Record<ProductCode, ProductUiConfig> = {
  ARBITRPACK: {
    code: "ARBITRPACK",
    displayName: "ArbitrPack",
    targetSystem: "«Мой Арбитр» (арбитражные суды)",
    approxPriceRub: "399.00",
    route: "/upload",
  },
  JUSTICEPACK: {
    code: "JUSTICEPACK",
    displayName: "JusticePack",
    targetSystem: "ГАС «Правосудие» (суды общей юрисдикции)",
    approxPriceRub: "399.00",
    route: "/services/justicepack",
  },
};

export function productOf(code: string | undefined | null): ProductUiConfig {
  return PRODUCTS[(code as ProductCode) || "ARBITRPACK"] || PRODUCTS.ARBITRPACK;
}
