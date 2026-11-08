# C3 — стабильность fine-tuning BERT

Рабочая папка группового проекта по статье [Mosbach et al., ICLR 2021](https://arxiv.org/abs/2006.04884v3).

Подготовлены [pre-reg.md](pre-reg.md), [DECISIONS.md](DECISIONS.md), конфиг и скрипты локального пилота. Репозиторий Git инициализирован пользователем. Upstream скачан отдельно в `C:\Users\n7210\PycharmProjects\PythonProject\bert-stable-fine-tuning`, SHA `3cf27e8667aee9d1c822d747c63ce331b231f283`; его исходники не изменялись.

## Текущий пилот и просмотр прогресса

08.11.2026 в 20:29 MSK запущен `original-seed0`: BERT-large, RTE, 20 эпох, seed 0, batch 16, accumulation 1, FP32, RTX 3070 Ti 8 GiB. На момент записи первые шаги прошли, итоговый результат ожидается. Это запуск с адаптациями окружения и путей, подробно описанными в журнале решений.

В PowerShell из этой папки:

```powershell
# Общий прогресс по всем 20 эпохам, elapsed и примерный остаток.
.\.runtime\python38\python.exe scripts/pilot_status.py

# Последние сообщения и живой прогресс; Ctrl+C завершает только просмотр.
Get-Content .\results\pilot\original-seed0.stderr.log -Tail 20 -Wait

# Статус running/completed/failed, время и peak CUDA memory после завершения.
Get-Content .\results\pilot\original-seed0\metadata.json
```

Коллектор автоматически сформирует [сводку пилота](results/pilot/original-seed0/summary.md) после окончания. `results/pilot/outputs/` содержит checkpoint и авторские TSV; большие артефакты исключены из Git. Скопируйте нужные небольшие таблицы в отслеживаемую папку перед сдачей. Единственный пилотный seed не является основным результатом по нескольким сидам.

Процент `Iteration` в сыром логе относится к одной текущей эпохе; общий прогресс показывает `pilot_status.py`. Он берёт последний залогированный шаг, поэтому отстаёт максимум примерно на 10 шагов. ETA ориентировочная и включает накладные расходы оценки/checkpoint.

Чтобы сохранить небольшой снимок метрик для коммита, не вмешиваясь в процесс:

```powershell
.\.runtime\python38\python.exe scripts/export_pilot_snapshot.py
```

Снимок содержит train/eval TSV, время и фактический статус в `results/pilot/original-seed0/snapshots/`. На 08.11.2026 23:50 MSK запущен отдельный процесс отложенного экспорта: он сохранит такой же снимок при включённом компьютере. После завершения основного пилота коллектор обновит summary; для явного экспорта финальных TSV можно повторно вызвать `summarize_pilot.py --attempt original-seed0`.

## Что коммитить

Добавляйте документы, `docs/`, `configs/`, `scripts/`, `environment/` и небольшие артефакты из `results/pilot/`. `.runtime/`, `downloads/`, `data/`, `model-cache/`, `.idea/` и `results/pilot/outputs/` исключены: это интерпретатор, пакеты, данные, веса, IDE и большие checkpoints. Сырые растущие stdout/stderr, журнал установки и `last-launch.json` тоже локальные; вместо них сохраняем timestamped snapshots и финальные сводки.

Из этой папки сейчас:

```powershell
git add .gitignore README.md pre-reg.md DECISIONS.md docs configs scripts environment
git add results/pilot/asset-sources.json results/pilot/weights-verified.json results/pilot/import-check.log
git add results/pilot/original-seed0/snapshots
git diff --cached --stat
git diff --cached --check
git commit -m "Complete preregistration plan and add reproducible pilot setup"
git push
```

После окончания пилота дополнительно добавьте `results/pilot/original-seed0/metadata.json`, `summary.md`, `summary.json` и экспортированные TSV. Перед сдачей проверьте время/статус снимка: метрика промежуточного шага и итоговая оценка восстановленного checkpoint — разные результаты. Исходный репозиторий авторов отдельно целиком в этот Git копировать не требуется; его URL и SHA уже зафиксированы.

## Повторный запуск пилота

После завершения текущего процесса:

```powershell
# Проверка импорта и доступности GPU.
.\.runtime\python38\python.exe scripts/run_pilot.py --upstream C:\Users\n7210\PycharmProjects\PythonProject\bert-stable-fine-tuning --config configs/rte-pilot-original.yaml --attempt check --check-only

# Новый процесс в фоне, уникальное имя попытки по времени.
.\scripts\start-pilot.ps1
```

`start-pilot.ps1` возвращает PID и пути stdout/stderr. Параметр `-Upstream` позволяет указать другую копию оригинала. Каждая попытка получает отдельную папку; существующая не перезаписывается. Для сводки другой попытки вызовите `scripts/summarize_pilot.py --attempt ИМЯ --wait` тем же Python.

Окружение: portable CPython 3.8.10 в `.runtime/python38`, PyTorch 1.13.1+cu117, авторский Transformers 2.5.1 импортируется из исходников. Полный freeze: [environment/pilot-freeze.txt](environment/pilot-freeze.txt). При восстановлении на другой машине установите Python 3.8 x64, PyTorch с официального cu117 wheel index и зависимости из freeze, затем используйте launcher с новым путем Python. Импорт и CUDA проверены; полный пилот пока не завершён. URL/hash данных и весов: [asset-sources.json](results/pilot/asset-sources.json), [weights-verified.json](results/pilot/weights-verified.json).

## Как организовать репозиторий

Репозиторий группы содержит план, журнал решений, собственные конфиги, команды, изменения оригинала и результаты. Сейчас используется отдельная локальная копия upstream с записанным SHA. Для переноса проекта можно вместо этого подключить Git submodule: сохраняется точный upstream commit без ручного копирования всего проекта.

Из этой папки, при наличии Git и доступа к GitHub:

```powershell
git init
git submodule add https://github.com/uds-lsv/bert-stable-fine-tuning.git upstream/bert-stable-fine-tuning
git -C upstream/bert-stable-fine-tuning rev-parse HEAD
```

Последняя команда показывает SHA, который нужно записать в материалы пилота. После фиксации gitlink в commit группы submodule будет привязан к этому SHA. Перед commit заполните и проверьте план. Удалённый репозиторий GitHub/GitLab создаётся отдельно; подготовка Markdown не требует заранее создавать его на сайте.

После публикации другой участник получает проект вместе с оригиналом:

```powershell
git clone --recurse-submodules <URL_РЕПОЗИТОРИЯ_ГРУППЫ>
```

Submodule — это локальная копия официального репозитория внутри проекта. Дополнительный независимый clone рядом не нужен. Альтернатива — fork авторского репозитория с собственными файлами и сохранённой лицензией. Для этого проекта предлагается submodule плюс отдельные конфиги и patches; не редактировать upstream молча.

## Что добавить к чекпоинту

Структура материалов (submodule — опциональный вариант вместо отдельного clone):

```text
pre-reg.md
DECISIONS.md
README.md
.gitignore
upstream/bert-stable-fine-tuning/   # submodule с зафиксированным SHA
configs/                          # пилот и план серии, включая seeds
scripts/                          # запуск пилота, серия, сбор результатов
environment/                      # реально проверенный lock/freeze или Dockerfile
patches/                          # изменения относительно оригинала, если нужны
results/pilot/                    # метаданные, небольшой лог, результат или traceback
results/tables/                   # итоговые CSV/Markdown после экспериментов
```

Для чекпоинта нужны рабочая команда пилота и его честный результат, точное окружение, GPU/время, принятый план и участники. Полную серию из 25 сидов выполняем после фиксации плана. Запуск, закончившийся ошибкой, документируем с traceback и попытками исправления.

## Как начать исходный запуск

Читайте [официальную инструкцию](https://github.com/uds-lsv/bert-stable-fine-tuning/blob/master/examples/bert_stable_fine_tuning/README.md) и конфиги в `examples/bert_stable_fine_tuning/`. Код основан на авторском fork Transformers v2.5.1; `pip install transformers` актуальной версии не заменяет этот fork.

Понадобятся исходники, данные GLUE RTE и предобученные веса/tokenizer BERT-large-uncased. Исходники можно скачать локально, а обучать на локальном NVIDIA GPU, в Colab/Kaggle или на сервере; локальное обучение не является требованием курса. На CPU полноценная серия непрактична.

Официальный сценарий использует Bash и Linux/Docker-пути. Его команды не предназначены для прямого копирования в PowerShell. Для локального NVIDIA GPU на Windows обычно нужен подходящий Linux/WSL2/Docker GPU setup; точную рабочую среду следует выбрать и проверить пилотом. На Colab/Kaggle надо отдельно проверить совместимость старых зависимостей, не считать её гарантированной.

В исходном `seeds.sh` есть заглушки переменных W&B. Не вписывайте ключи в Git; изменение запуска или логирования записывайте в журнал. Для основной серии предложен W&B offline; пилот использует исходный конфиг с выключенным W&B и сохраняет локальные TSV/stdout/stderr. Данные, веса, временные загрузки и portable Python исключены из Git.

**До сдачи:** дождаться полного пилота, перенести фактические итоговые метрики/время/память в раздел 3 pre-registration, вписать участников и URL проекта, проверить и принять ставки и бюджет, зафиксировать документы commit до основной серии.
