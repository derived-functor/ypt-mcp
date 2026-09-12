# ypt-mcp

MCP-сервер для трекера учёбы YPT (열품타) на базе библиотеки
[`ypt-python`](https://github.com/derived-functor/ypt-private-client).

Работает по stdio-транспорту и через Model Context Protocol открывает доступ к
дневным логам учёбы, рейтингам, учебным группам и таймеру занятий.

## Возможности

- Профиль и сводка за сегодня (`get_profile`)
- Дневные логи учёбы по датам (`get_day_log`)
- Твоё место в рейтинге категории и таблицы лидеров (`get_my_rank`, `get_leaderboard`)
- Поиск групп, мои группы, участники (`browse_groups`, `get_my_groups`, `get_group_members`)
- Таймер занятий: старт/стоп с учётом сессии (`start_study`, `stop_study`)

## Требования

- [uv](https://docs.astral.sh/uv/) (для запуска через `uvx` / `uv run`)
- Доступ к GitHub-репозиториям `derived-functor/ypt-mcp` и
  `derived-functor/ypt-private-client` (приватные — нужен настроенный git-auth:
  SSH-ключ или PAT)

## Быстрый старт

### Вариант 1 — через `uvx` (основной)

Одна команда, без клонирования:

```bash
uvx --from git+https://github.com/derived-functor/ypt-mcp ypt-mcp
```

`uvx` сам подтянет `ypt-mcp` и его зависимость `ypt-python`
(из `git+https://github.com/derived-functor/ypt-private-client`), соберёт и
запустит в изолированном окружении.

При необходимости можно пинить версию: `--from git+...@main`.

### Вариант 2 — локальная разработка через `uv run`

```bash
git clone https://github.com/derived-functor/ypt-mcp
cd ypt-mcp
uv sync
uv run ypt-mcp
```

> При работе над самой библиотекой `ypt-python` удобно временно вернуть в
> `pyproject.toml` локальный источник: `[tool.uv.sources]` =
> `{ path = "/path/to/ypt-private-client", editable = true }`.

## Аутентификация

Сервер использует кэш JWT-токена `~/.cache/ypt-python/token` (общий с
`ypt-cli`). Если токена нет, логинится по переменным окружения:

```bash
export YPT_EMAIL="you@example.com"
export YPT_PASSWORD="your-password"
```

Либо заранее выполни логин через библиотеку:

```bash
cd ~/probe/ypt-private-client && uv run ypt-cli login
```

Приоритет: закэшированный токен → `YPT_EMAIL`/`YPT_PASSWORD`. Если токен
протух, сервер сам перелогинится и обновит кэш. Пароль нигде не хранится
(в кэше только JWT).

> Не коммить реальные `YPT_EMAIL`/`YPT_PASSWORD` в файлы конфигов — используй
> интерполяцию `{env:VAR}` (см. ниже), тогда значения попадут только в окружение.

## Подключение клиентов

### opencode (`opencode.json`)

Проектный `opencode.json` или глобальный `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ypt": {
      "type": "local",
      "command": ["uvx", "--from", "git+https://github.com/derived-functor/ypt-mcp", "ypt-mcp"],
      "environment": {
        "YPT_EMAIL": "{env:YPT_EMAIL}",
        "YPT_PASSWORD": "{env:YPT_PASSWORD}"
      }
    }
  }
}
```

Заметки:
- `command` — массив строк, оболочка не используется;
- `{env:VAR}` подставляет значение из окружения opencode (не `$VAR`);
- после изменения конфига перезапусти opencode — конфиг подхватывается
  только при старте.

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "ypt": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/derived-functor/ypt-mcp", "ypt-mcp"],
      "env": {
        "YPT_EMAIL": "you@example.com",
        "YPT_PASSWORD": "your-password"
      }
    }
  }
}
```

## Тулы

| Тул | Назначение |
|---|---|
| `get_profile` | Профиль, категория/страна, предметы, сводка за сегодня |
| `get_day_log(date)` | Лог учёбы за дату |
| `get_my_rank(category_id, country_id)` | Твоё место в рейтинге категории |
| `get_leaderboard(category_id, country_id, date, ...)` | Таблица лидеров категории |
| `browse_groups(...)` | Поиск публичных групп |
| `get_my_groups` | Твои группы |
| `get_group_members(group_id, country_id)` | Участники группы |
| `start_study(subject, ...)` | Старт таймера учёбы |
| `stop_study(started_at, ...)` | Стоп таймера учёбы |

Время отдаётся в часах (`study_hours`/`rest_hours`, float) и в сырых
миллисекундах (`study_ms`/`rest_ms`, int). Даты — `YYYY-MM-DD`.

### `get_profile`

Без аргументов. Возвращает профиль и сводку за сегодня:

```json
{
  "nickname": "derived-functor",
  "category_code": "ВУЗ",
  "category_id": 94,
  "country_id": 6,
  "subjects": [
    { "id": 131150462, "title": "матеша задачи", "study_hours": 0.0, "archived": false }
  ],
  "day_log": {
    "date": "2026-09-12",
    "study_hours": 0.44,
    "rest_hours": 2.15,
    "subjects": [
      { "subject_id": 131150462, "subject_title": "матеша задачи", "study_hours": 0.44 }
    ]
  }
}
```

### `get_day_log(date)`

| Аргумент | Тип | Описание |
|---|---|---|
| `date` | `str` | Дата в формате `YYYY-MM-DD` |

```json
{
  "date": "2026-09-12",
  "study_ms": 1586019,
  "study_hours": 0.44,
  "rest_hours": 2.15,
  "max_study_hours": 0.44,
  "added_hours": 0.0,
  "subjects": [
    { "subject_id": 131150462, "subject_title": "матеша задачи", "study_ms": 1586019, "study_hours": 0.44 }
  ]
}
```

### `get_my_rank(category_id, country_id)`

| Аргумент | Тип | Описание |
|---|---|---|
| `category_id` | `int` | ID категории из `get_profile` |
| `country_id` | `int` | ID страны из `get_profile` |

Вернёт число (номер места) или `null`, если рейтинга нет.

### `get_leaderboard(category_id, country_id, date, page, rank_type, limit)`

| Аргумент | Тип | Дефолт | Описание |
|---|---|---|---|
| `category_id` | `int` | — | ID категории |
| `country_id` | `int` | — | ID страны |
| `date` | `str` | — | Дата `YYYY-MM-DD` |
| `page` | `int` | `1` | Номер страницы (20 записей) |
| `rank_type` | `str` | `"day"` | Период: `"day"` или `"week"` |
| `limit` | `int` | `20` | Сколько участников вернуть |

```json
{
  "total_count": 729,
  "members": [
    { "nickname": "lisha.rix", "user_id": 17526047, "study_hours": 11.08, "studicon_id": 0 }
  ]
}
```

### `browse_groups(category_id, page, country_id, order_type, only_available, only_open, only_cam)`

| Аргумент | Тип | Дефолт | Описание |
|---|---|---|---|
| `category_id` | `int` | `0` | Фильтр по категории (0 = все) |
| `page` | `int` | `1` | Номер страницы |
| `country_id` | `int \| null` | `null` | Фильтр по стране |
| `order_type` | `str` | `"promotedAt"` | Сортировка |
| `only_available` | `bool` | `false` | Только группы со свободными местами |
| `only_open` | `bool` | `false` | Только открытые группы |
| `only_cam` | `bool` | `false` | Только с камерой |

### `get_my_groups`

Без аргументов. Список групп с `id`, `title`, `owner`, `member_count`.

### `get_group_members(group_id, country_id)`

| Аргумент | Тип | Описание |
|---|---|---|
| `group_id` | `int` | ID группы |
| `country_id` | `int` | ID страны |

У каждого участника: `user_id`, `nickname`, `category`, `study_hours`,
`studying` (учится ли прямо сейчас).

### `start_study(subject, device_model)` / `stop_study(started_at, device_model)`

| Аргумент | Тип | Дефолт | Описание |
|---|---|---|---|
| `subject` | `str` | — | Название предмета (для start) |
| `started_at` | `int \| null` | `null` | Старт сессии epoch ms (для stop) |
| `device_model` | `str` | `"ypt-mcp"` | Модель устройства для API |

`start_study` возвращает `started_at` (epoch ms) и дневной лог. `stop_study`
без `started_at` использует записанную сессию (state-файл
`~/.cache/ypt-python/study_started_at`, тот же, что у `ypt-cli`).

## Сценарии-примеры

Все примеры общаются с сервером по stdio через Python-клиент `mcp`:

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CMD = ["uvx", "--from", "git+https://github.com/derived-functor/ypt-mcp", "ypt-mcp"]

async def call(tool: str, args: dict):
    params = StdioServerParameters(command=CMD[0], args=CMD[1:])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(tool, args)
            return "".join(c.text for c in res.content)

async def main():
    # 1. Ежедневный отчёт
    profile = await call("get_profile", {})
    print(profile)

    # 2. Топ категории (id/страну берём из профиля)
    top = await call("get_leaderboard", {
        "category_id": 94, "country_id": 6, "date": "2026-09-12", "limit": 10,
    })
    print(top)

    # 3. Мои группы и участники
    groups = await call("get_my_groups", {})
    members = await call("get_group_members", {"group_id": groups[0]["id"], "country_id": 6})
    print(members)

    # 4. Таймер: старт → рядом повторяющихся вызовов нет → стоп
    started = await call("start_study", {"subject": "матеша задачи"})
    stopped = await call("stop_study", {"started_at": started["started_at"]})
    print(stopped)

asyncio.run(main())
```

## Обработка ошибок

| Ситуация | Поведение |
|---|---|
| Нет токена и нет `YPT_EMAIL`/`YPT_PASSWORD` | Ошибка с сообщением «credentials not found» |
| Протухший токен | Сервер перелогинится и повторит вызов автоматически |
| `stop_study` без записанной сессии | Ошибка — нужен `started_at` |
| Ошибки YPT API / сети | Пробрасываются выше с кодом/текстом из библиотеки `ypt-python` |

## Архитектура

```
LLM/клиент (opencode, Claude Desktop)
        │  MCP (stdio, JSON-RPC)
        ▼
ypt-mcp  (mcp SDK, тулы, auth-менеджмент)
        │  ypt-python (async-клиент, pydantic-модели)
        ▼
YPT REST API (https://pi.tgclab.com)
```

- `src/ypt_mcp/server.py` — все тулы и логика аутентификации
- `~/.cache/ypt-python/token` — кэш JWT
- `~/.cache/ypt-python/study_started_at` — старт текущей сессии таймера
- `pyproject.toml` — зависимости (`mcp`, `ypt-python` из git) и entry point

## Проверка

Смоук-тест: запустить сервер, выполнить handshake и вывести список тулов.

```bash
uvx --from git+https://github.com/derived-functor/ypt-mcp python - <<'EOF'
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(
        command="uvx",
        args=["--from", "git+https://github.com/derived-functor/ypt-mcp", "ypt-mcp"],
    )
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print([t.name for t in (await s.list_tools()).tools])

asyncio.run(main())
EOF
```

Ожидаемый результат — 9 тулов: `get_profile`, `get_day_log`, `get_my_rank`,
`get_leaderboard`, `browse_groups`, `get_my_groups`, `get_group_members`,
`start_study`, `stop_study`.

## Известные особенности

Для работы `get_leaderboard` в репозитории `ypt-private-client` исправлен
хелпер `_get()` в `src/ypt_python/_models.py`: теперь `null`-значения
(которые API присылает для `si`/`tc`) игнорируются и заменяются дефолтом
вместо падения `int(None)`. Фикс входит в текущий HEAD ветки `main` и
подтягивается автоматически через git-источник `ypt-python`.