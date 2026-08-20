# Own 2FA Admin UI — Design System

Источник: [Linear](https://getdesign.md/linear.app/design-md) из коллекции
[VoltAgent/awesome-claude-design](https://github.com/VoltAgent/awesome-claude-design).
Ultra-minimal dark admin: точная типографика, фиолетовый акцент, формы в одну колонку.

## Принципы

- Одна колонка, max-width формы ~560px
- Чекбокс + подпись — одна строка (`flex`, gap 10px); несколько вариантов — **столбик** (`.choice-stack`)
- Radio — тот же паттерн, что checkbox (`.check-row`)
- Секции — `fieldset` + uppercase legend
- Подсказки — muted 12px под полем; **у каждого значимого поля**
- Без grid из двух колонок в настройках
- **Не показывать** snake_case API и comma-separated enum — только выбор в UI (§21 CLAUDE.md)

## Tokens

```css
--bg: #0a0a0c;
--surface: #141417;
--surface-2: #1c1c21;
--border: #27272f;
--fg: #eeeef0;
--muted: #8b8d98;
--accent: #5e6ad2;
--accent-hover: #6b77db;
--err: #e5484d;
--radius: 6px;
--font: "Inter", system-ui, sans-serif;
```

## Компоненты

- **field** — label сверху, input на всю ширину
- **field-check** — checkbox слева, текст справа, на всю строку
- **choice-stack** — вертикальный список checkbox/radio
- **field-group-label** — заголовок группы выбора
- **settings-section** — fieldset с отступом между секциями
- **btn-primary** — accent fill
- **btn-ghost** — transparent border
