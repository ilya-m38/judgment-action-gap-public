# Бэкап сырых данных

Код и отчёты лежат на GitHub (`ilya-m38/judgment-action-gap`). Остальное — трассы `pi.jsonl`, `*.sqlite`, папки прогонов, всё, что не в git, — каждую ночь уходит зашифрованным в restic на сервер netcup `german`.

- Хранилище: `sftp:german:/srv/restic/judgment-action-gap`.
- Что входит: вся папка проекта, кроме `archive/` (остановленный тред Merrow не меняется), `.venv`, `__pycache__`.
- Когда: каждый день в 03:30, задача launchd `com.judgment-action-gap.restic-backup`. Если Мак спал, бэкап запустится при пробуждении. Лог: `~/Library/Logs/restic-judgment-action-gap.log`.
- Хранение: 14 ежедневных, 8 еженедельных и 12 ежемесячных снапшотов. По воскресеньям restic читает и проверяет 5% данных.
- Защита сервера: если на `german` свободно меньше 5 ГБ, бэкап пропускается и приходит уведомление. Скорость отправки ограничена 4 МБ/с, чтобы не мешать VPN.
- Пароль: Связка ключей macOS, запись `restic-judgment-action-gap`. **Копия должна лежать в менеджере паролей**: без пароля бэкап не прочитать.

```sh
export RESTIC_REPOSITORY="sftp:german:/srv/restic/judgment-action-gap"
export RESTIC_PASSWORD_COMMAND="security find-generic-password -s restic-judgment-action-gap -a backup -w"
restic snapshots                                   # список снапшотов
restic restore latest --target ~/restore --include "/Users/user/Projects/Move38/Measuring the Judgment-Action Gap in Large Language Models/parcel-office"
```

На другом компьютере вместо `RESTIC_PASSWORD_COMMAND` задайте `RESTIC_PASSWORD`, а в `~/.ssh/config` пропишите хост `german` (46.38.232.12, порт 2222, пользователь root).
