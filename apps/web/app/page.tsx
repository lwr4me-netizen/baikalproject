import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="container">
      <div className="card" style={{ marginTop: 24 }}>
        <h2>Куда вы подаёте документы?</h2>
        <p className="subtitle" style={{ marginTop: 0 }}>
          BAIKALPROJECT — два независимых аппарата технической проверки. Правила, лимиты и тарифы у них
          независимые: выберите нужную систему подачи документов.
        </p>
        <div className="radio-group" style={{ marginTop: 12, gap: 12 }}>
          <Link href="/upload" className="btn">
            Мой Арбитр
          </Link>
          <Link href="/services/justicepack" className="btn secondary">
            ГАС Правосудие / суд общей юрисдикции
          </Link>
        </div>
      </div>

      <div style={{ marginTop: 40 }}>
        <h1>Проверьте документы перед электронной подачей в суд</h1>
        <p className="subtitle">
          Два независимых аппарата технической проверки — для арбитражных судов и для судов общей юрисдикции.
          Сервис найдёт технические ошибки, подготовит структуру файлов и сформирует готовый архив.
          Юридическое содержание документов не изменяется.
        </p>
        <div className="radio-group" style={{ gap: 12 }}>
          <Link href="/upload" className="btn">
            Проверить документы для «Мой Арбитр»
          </Link>
          <Link href="/services/justicepack" className="btn secondary">
            Проверить документы для ГАС «Правосудие»
          </Link>
        </div>
      </div>

      <div className="card" style={{ marginTop: 48 }}>
        <h2>Что делает каждый аппарат</h2>
        <p className="subtitle" style={{ marginTop: 0 }}>
          ArbitrPack и JusticePack выполняют одинаковый набор технических проверок, но по независимо проверенным
          правилам своей судебной системы (лимиты, форматы и требования у них разные — см.{" "}
          <code>docs/justicepack/official-requirements.md</code>).
        </p>
        <ul>
          <li>Проверяет формат, целостность и защиту паролем PDF-файлов и изображений;</li>
          <li>Находит дубликаты, повреждённые файлы и потенциально пустые страницы;</li>
          <li>Безопасно удаляет метаданные и EXIF из документов;</li>
          <li>Собирает итоговый архив с понятным манифестом;</li>
          <li>Автоматически удаляет ваши файлы по истечении выбранного срока.</li>
        </ul>
      </div>

      <div className="card">
        <h2>Чего сервис не делает</h2>
        <ul>
          <li>Не даёт юридическую оценку и не прогнозирует решение суда;</li>
          <li>Не подписывает документы электронной подписью;</li>
          <li>Не гарантирует, что суд примет поданные документы;</li>
          <li>Не отправляет документы в суд самостоятельно.</li>
        </ul>
      </div>
    </main>
  );
}
