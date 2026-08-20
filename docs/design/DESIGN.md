# MK 2FA Admin UI — Design System

Источник оформления: соседний **Squid Proxy Manager** (Interros corporate identity).  
Шрифты и логотип — **локально** в `web/assets/` (без CDN).

## Принципы

- Светлый контент + тёмный navy сайдбар, акцент gold `#c9a96e`
- Одна колонка форм; checkbox/radio — `.check-row` / `.choice-stack`
- Секции — `fieldset.settings-section` + legend внутри (не на рамке)
- **Без иконок** у пунктов меню
- **Не показывать** snake_case API (§21 CLAUDE.md)

## Tokens

```css
--ir-primary: #0f1b2e;
--ir-accent: #c9a96e;
--bg: #f0f2f5;
--surface: #ffffff;
--border: #e2e5e9;
--fg: #1a1a1a;
--muted: #8a94a3;
--font: Inter (local /assets/fonts/inter-*.ttf);
```

## Ассеты

| Путь | Что |
|------|-----|
| `web/assets/fonts/` | Inter 400/500/600/700 |
| `web/assets/css/inter-font.css` | @font-face |
| `web/assets/img/logo.png` | логотип (из squid-panel) |
| `web/favicon*.png` | favicon |

## Компоненты

- Login: `.login-page` / `.login-box` / `.brand-mark`
- Sidebar: navy + left accent на `.nav-item.active`
- User menu: top-right dropdown
- **btn** primary = gold на navy text; **ghost** = outline
