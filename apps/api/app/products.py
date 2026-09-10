"""Реестр продуктов ("цифровых аппаратов"). BAIKALPROJECT — платформа, на которой независимо
работают несколько вендинг-машин технической проверки документов. Каждая машина — отдельный
`product_code`, отдельный файл правил, отдельный тариф и отдельные тексты.

ВАЖНО (раздел 2/4 ТЗ JusticePack): правила и лимиты одного продукта НИКОГДА не переносятся на
другой по аналогии. Если понадобится узнать путь к файлу правил или тариф — всегда через этот
реестр, никогда не хардкодить пути к rules.yaml в другом месте кода.
"""
from __future__ import annotations

import enum
import pathlib
from dataclasses import dataclass

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


class ProductCode(str, enum.Enum):
    ARBITRPACK = "ARBITRPACK"
    JUSTICEPACK = "JUSTICEPACK"


DEFAULT_PRODUCT_CODE = ProductCode.ARBITRPACK.value


@dataclass(frozen=True)
class ProductProfile:
    code: str
    display_name: str
    # человекочитаемое название целевой системы подачи документов
    target_system: str
    rules_path: pathlib.Path
    filename_rule_label: str
    signature_disclaimer: str
    payment_description_prefix: str
    archive_manifest_title: str
    archive_filename_prefix: str


PRODUCTS: dict[str, ProductProfile] = {
    ProductCode.ARBITRPACK.value: ProductProfile(
        code=ProductCode.ARBITRPACK.value,
        display_name="ArbitrPack",
        target_system='«Мой Арбитр» (арбитражные суды)',
        rules_path=REPO_ROOT / "packages" / "validation-rules" / "rules.yaml",
        filename_rule_label='Официальное правило "Мой Арбитр"',
        signature_disclaimer="ArbitrPack не накладывает и не проверяет электронную подпись.",
        payment_description_prefix="Техническая подготовка документов ArbitrPack",
        archive_manifest_title="Состав архива ArbitrPack",
        archive_filename_prefix="arbitrpack",
    ),
    ProductCode.JUSTICEPACK.value: ProductProfile(
        code=ProductCode.JUSTICEPACK.value,
        display_name="JusticePack",
        target_system='ГАС «Правосудие» (суды общей юрисдикции)',
        rules_path=REPO_ROOT / "config" / "rules" / "gas_pravosudie.yaml",
        filename_rule_label='Официальное правило ГАС «Правосудие»',
        signature_disclaimer="JusticePack не накладывает и не проверяет электронную подпись.",
        payment_description_prefix="Техническая подготовка документов JusticePack",
        archive_manifest_title="Состав архива JusticePack",
        archive_filename_prefix="justicepack",
    ),
}


def get_product(product_code: str | None) -> ProductProfile:
    """Возвращает профиль продукта. При неизвестном/пустом коде — ValueError (роутер обязан
    превратить это в HTTP 400, а не молча подставлять ArbitrPack)."""
    code = product_code or DEFAULT_PRODUCT_CODE
    profile = PRODUCTS.get(code)
    if profile is None:
        raise ValueError(f"Unknown product_code: {code!r}. Допустимые значения: {sorted(PRODUCTS)}")
    return profile


def is_valid_product_code(product_code: str | None) -> bool:
    return (product_code or DEFAULT_PRODUCT_CODE) in PRODUCTS
