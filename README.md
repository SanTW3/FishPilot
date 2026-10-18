# GPO Fishing Macro — мини-приложение Telegram

Панель управления макросом [GPO Fishing Macro](https://github.com/SanTW3/Mediavert/tree/main/gpo-fishing-macro)
прямо в Telegram: статистика, старт/стоп, экран вкл/выкл, скриншот, сброс тревоги.

Сайт: https://santw3.github.io/gpo-macro/ (GitHub Pages, ветка `main`, корень).

## Как это работает

Своего сервера нет. Макрос на ПК и эта страница общаются через [ntfy](https://ntfy.sh) по двум топикам
с секретным именем:

- `gpo-<секрет>-status` — ПК публикует статус (JSON), страница его слушает;
- `gpo-<секрет>-cmd` — страница шлёт команды (`start`, `stop`, `screen_on`, `screen_off`, `shot`, `alarm_off`),
  ПК их выполняет.

Секрет и адрес ntfy передаются во фрагменте ссылки (`#t=…&s=…`). Фрагмент не уходит на сервер GitHub,
а ссылку бот присылает только в ваш личный чат. Кто знает секрет, тот видит статус и управляет макросом.
Если ссылка утекла, нажмите в макросе **New secret link**.

## Включение GitHub Pages (один раз)

Settings → Pages → Build and deployment → Source: **Deploy from a branch**,
Branch: **main**, папка **/ (root)** → Save.
