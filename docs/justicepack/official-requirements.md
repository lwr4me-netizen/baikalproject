# Официальные требования JusticePack (ГАС «Правосудие», суды общей юрисдикции)

Дата проверки: 2026-09-09. Метод: поиск и чтение текста официального нормативного акта через агрегатор sudact.ru,
который в данном случае воспроизводит постатейный текст приказа (не только пересказ, как для части правил
ArbitrPack) — поэтому уровень достоверности здесь в среднем выше, но это всё ещё не прямой доступ к pravo.gov.ru,
поэтому статус — `PARTIALLY VERIFIED`, а не `VERIFIED`, за исключением случаев, где отдельно указано иное.

**Важно — разделение систем (раздел 2 ТЗ):** «Мой Арбитр» (арбитражные суды, приказ №252 от 28.12.2016) и ГАС
«Правосудие» (суды общей юрисдикции, приказ №251 от 27.12.2016) — это два разных нормативных акта, изданных одним
органом (Судебный департамент при ВС РФ) в один день. Совпадение конкретных цифр (30 МБ, 200–300 dpi) в обоих
документах подтверждено независимо для каждого акта отдельно (см. `docs/requirements-sources.md` для №252 и этот
файл для №251) — оно НЕ было предположено по аналогии между системами, как прямо запрещено разделом 4 ТЗ.

## Реестр правил (структурированный, см. также `config/rules/gas_pravosudie.yaml`)

```yaml
rule_id: GAS-R1
system: GAS_PRAVOSUDIE
title: Формат файлов электронного образа документа (скана)
description: >
  Файл электронного образа документа (скана) должен быть в формате PDF.
severity: BLOCKER
source_url: https://sudact.ru/law/prikaz-sudebnogo-departamenta-pri-verkhovnom-sude-rf_290/poriadok-podachi-v-federalnye-sudy/2/2.2/
source_title: >
  Приказ Судебного департамента при Верховном Суде РФ от 27.12.2016 № 251, п. 2.2
verified_at: "2026-09-09"
official_source: true
implementation_status: implemented
test_id: test_gas_scan_must_be_pdf
```

```yaml
rule_id: GAS-R2
system: GAS_PRAVOSUDIE
title: Максимальный размер одного файла
description: >
  Размер файла электронного образа документа не должен превышать 30 Мб.
severity: BLOCKER
source_url: https://sudact.ru/law/prikaz-sudebnogo-departamenta-pri-verkhovnom-sude-rf_290/poriadok-podachi-v-federalnye-sudy/2/2.2/
source_title: Приказ №251, п. 2.2
verified_at: "2026-09-09"
official_source: true
implementation_status: implemented
test_id: test_gas_oversized_file_rejected
```

```yaml
rule_id: GAS-R3
system: GAS_PRAVOSUDIE
title: Требования к сканированию (рекомендация, не блокирующая проверка)
description: >
  Скан в масштабе 1:1, чёрно-белый либо серый цвет, качество 200–300 dpi. Цветное сканирование допускается,
  если цвет имеет значение для дела.
severity: RECOMMENDATION
source_url: https://sudact.ru/law/prikaz-sudebnogo-departamenta-pri-verkhovnom-sude-rf_290/poriadok-podachi-v-federalnye-sudy/2/2.2/
source_title: Приказ №251, п. 2.2
verified_at: "2026-09-09"
official_source: true
implementation_status: implemented_as_recommendation
test_id: test_gas_low_scan_quality_flagged
```

```yaml
rule_id: GAS-R4
system: GAS_PRAVOSUDIE
title: Файлы не должны быть защищены от копирования и печати
description: >
  Приказ прямо требует, чтобы файлы не были защищены от копирования и печати — то есть зашифрованный/защищённый
  паролем PDF формально нарушает это требование сильнее, чем в случае «Мой Арбитр» (там это только техническая
  проблема открытия файла, здесь — прямая формулировка запрета).
severity: BLOCKER
source_url: https://sudact.ru/law/prikaz-sudebnogo-departamenta-pri-verkhovnom-sude-rf_290/poriadok-podachi-v-federalnye-sudy/2/2.2/
source_title: Приказ №251, п. 2.2
verified_at: "2026-09-09"
official_source: true
implementation_status: implemented
test_id: test_gas_encrypted_pdf_rejected
```

```yaml
rule_id: GAS-R5
system: GAS_PRAVOSUDIE
title: Каждый документ — отдельным файлом
description: >
  Каждый документ представляется в суд отдельным файлом (не объединять несколько документов в один PDF).
severity: RECOMMENDATION
source_url: https://sudact.ru/law/prikaz-sudebnogo-departamenta-pri-verkhovnom-sude-rf_290/poriadok-podachi-v-federalnye-sudy/2/2.2/
source_title: Приказ №251, п. 2.2
verified_at: "2026-09-09"
official_source: true
implementation_status: shown_as_recommendation
test_id: —
notes: >
  Технически сервис не может достоверно определить, что PDF "содержит несколько документов" — это осталось
  рекомендацией в тексте отчёта, не автоматической проверкой.
```

```yaml
rule_id: GAS-R6
system: GAS_PRAVOSUDIE
title: Форматы исходных электронных документов (не сканов)
description: >
  Текстовые документы — PDF, RTF, DOC, DOCX, XLS, XLSX, ODT. Графические — PDF, JPEG (JPG), PNG, TIFF.
severity: BLOCKER (для тех форматов, что вне allowlist MVP)
source_url: https://sudact.ru/law/prikaz-sudebnogo-departamenta-pri-verkhovnom-sude-rf_290/poriadok-podachi-v-federalnye-sudy/2/2.3/
source_title: Приказ №251, п. 2.3
verified_at: "2026-09-09"
official_source: true
implementation_status: partially_implemented
test_id: test_gas_disallowed_extension_rejected
notes: >
  MVP JusticePack, как и ArbitrPack, ограничен PDF/JPG/JPEG/PNG (раздел 4 ТЗ первого аппарата и явный список
  форматов раздела 5.1 ТЗ JusticePack). RTF/DOC/DOCX/XLS/XLSX/ODT/TIFF официально допустимы приказом, но
  сознательно не входят в MVP — отмечено как известное ограничение, а не как несоответствие приказу для тех
  случаев, когда пользователь всё равно подаёт PDF/JPG/PNG.
```

```yaml
rule_id: GAS-R7
system: GAS_PRAVOSUDIE
title: Именование файлов
description: >
  Наименование файла должно позволять идентифицировать документ и количество листов в документе
  (например: "исковое заявление от 05122016 3л.pdf").
severity: RECOMMENDATION
source_url: https://sudact.ru/law/prikaz-sudebnogo-departamenta-pri-verkhovnom-sude-rf_290/poriadok-podachi-v-federalnye-sudy/2/2.3/
source_title: Приказ №251, п. 2.3
verified_at: "2026-09-09"
official_source: true
implementation_status: implemented_as_recommendation
test_id: test_gas_filename_not_descriptive_hint
```

```yaml
rule_id: GAS-R8
system: GAS_PRAVOSUDIE
title: Электронная подпись
description: >
  Электронный документ (не скан) должен быть подписан усиленной квалифицированной электронной подписью в формате
  PKCS#7 (отсоединённая подпись, в отдельном файле). Электронный образ (скан) может быть заверен простой либо
  усиленной квалифицированной подписью.
severity: RECOMMENDATION (дисклеймер, не блокирующая проверка — см. ниже)
source_url: https://sudact.ru/law/prikaz-sudebnogo-departamenta-pri-verkhovnom-sude-rf_290/poriadok-podachi-v-federalnye-sudy/2/2.3/
source_title: Приказ №251, п. 2.3
verified_at: "2026-09-09"
official_source: true
implementation_status: disclaimer_only
test_id: test_gas_report_contains_signature_disclaimer
notes: >
  JusticePack, как и ArbitrPack, НЕ накладывает и не проверяет электронную подпись (запрещено разделом 5.3 ТЗ —
  "обходить защиту PDF" / создание юридически значимого содержания вне объёма сервиса). Формат подписи отличается
  от «Мой Арбитр» (там просто «усиленная квалифицированная», здесь явно указан PKCS#7/отсоединённая) — это ЕЩЁ ОДНА
  причина, почему правила двух систем нельзя было объединять по аналогии.
```

```yaml
rule_id: GAS-R9
system: GAS_PRAVOSUDIE
title: Максимальный общий размер обращения
description: Официальный лимит не найден в проверенных источниках на момент проверки.
severity: N/A
source_url: —
source_title: —
verified_at: "2026-09-09"
official_source: false
implementation_status: UNVERIFIED
test_id: —
notes: >
  Как и для ArbitrPack, применяется только продуктовый (не нормативный) лимит сервиса — см.
  config/rules/gas_pravosudie.yaml: max_batch_size_mb. Помечено в UI как "техническое ограничение сервиса".
```

## Отличия от ArbitrPack, зафиксированные явно (не предполагались заранее)

| Параметр | «Мой Арбитр» (252) | ГАС «Правосудие» (251) | Совпадает? |
|---|---|---|---|
| Формат скана | PDF | PDF | да |
| Макс. размер файла | 30 МБ | 30 МБ | да |
| DPI скана | 200–300 | 200–300 | да |
| Требование "без защиты от копирования/печати" | не встречено явно в проверенных источниках (см. `docs/requirements-sources.md` R-1/R-2) | явно указано в п. 2.2 | **нет** — отдельное правило GAS-R4, не перенесённое в ArbitrPack |
| Формат подписи | «усиленная квалифицированная», без уточнения формата в проверенных источниках | явно PKCS#7, отсоединённая, отдельным файлом | **нет** — разные дисклеймеры |
| Номер и дата приказа | № 252 от 28.12.2016 | № 251 от 27.12.2016 | разные акты |

Это подтверждает, почему правила физически разделены на два независимых файла конфигурации, а не параметризованы
общим шаблоном с "переключателем системы".

## Поисковые намерения — явное разделение (раздел 4 ТЗ)

Запросы вида «требования к документам ГАС Правосудие» (информационное намерение) и «ошибка загрузки файла суд»
(проблемное/коммерческое намерение) НЕ складываются механически в одну оценку спроса или выручки — они относятся
к разным этапам воронки и разным намерениям пользователя. Их раздельная разработка — в `docs/justicepack/market-validation.md`.
