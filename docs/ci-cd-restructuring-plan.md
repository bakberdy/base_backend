# План реструктуризации CI/CD

Статус: **Этапы 0–5 реализованы; Этап 6 ожидает development proof в GitHub Actions без
production deploy**.

Аудит выполнен для `development@e22eaa9` 28 июля 2026 года.

Baseline перед изменениями зафиксирован в `docs/ci-cd-baseline.md`.
Workflow contracts зафиксированы в `docs/ci-cd-contracts.md`.
Security baseline exceptions и remediation tasks зафиксированы в
`security/exceptions.json` и `docs/security-remediation.md`.

Этот документ описывает целевую структуру проверок, сборки образа и деплоя. Он не меняет
текущие workflow, Dockerfile, Compose, Terraform, Makefile, GitHub environments или AWS-ресурсы.
Текущее фактическое поведение по-прежнему описано в `.github/docs/github-actions.md` и
`docs/deploy.md`.

## 1. Решение

Текущие EC2, AWS SSM, private ECR и GitHub OIDC сохраняются. Реструктуризация строится на
следующих правилах:

1. Один workflow владеет триггерами и порядком выполнения.
2. Один workflow владеет application image и выполняет не более одной trusted-сборки на SHA.
3. Проверки исходного кода, repository security, image security и deployment не смешиваются.
4. Между build, security и deploy передается immutable digest, а не tag.
5. PR build и trusted release build сохраняются: они проверяют разные SHA и находятся на разных
   trust boundaries.
6. Один security-механизм является блокирующим источником истины для release image. Остальные
   проверки не должны повторять тот же gate.
7. Пока Terraform создает только `x86_64` EC2, release image собирается для `linux/amd64`.
   `arm64` возвращается только при появлении реального ARM-потребителя.
8. Новая схема сначала доказывается в `development`, затем включается для `production`.

## 2. Что происходит сейчас

```text
Pull request
  -> project-validation.yml
     -> format / lint / mypy / unit / integration / Uvicorn
     -> Docker build
     -> Gitleaks / diff

Push development | main
  -> publish-image.yml
     -> project-validation.yml
        -> Docker build #1
     -> Buildx multi-platform build + ECR push #2
     -> deploy-app.yml
        -> deploy repository:sha-tag через SSM
```

Подтвержденные проблемы:

| Проблема | Текущее состояние |
| --- | --- |
| Повторная сборка image | `project-validation.yml` строит validation image, затем `publish-image.yml` снова строит и публикует image. |
| Повторная Python-подготовка | Полная validation выполняет 9 checkout, 6 Python setup и 6 `pip install`. |
| Повторные service containers | Integration и Uvicorn jobs отдельно поднимают одинаковые PostgreSQL и Redis. |
| Две точки истины | CI повторяет команды, уже частично определенные в `Makefile`. |
| Смешанная ответственность | `project-validation.yml` содержит source, runtime, Docker и secret checks; `publish-image.yml` одновременно orchestrator, publisher и deploy caller. |
| Scan не блокирует deploy | Terraform включает ECR `scan_on_push`, но workflow не ожидает результат и не применяет severity policy. |
| Tag вместо digest | Deploy принимает `image_tag` и сам собирает `${repository}:${tag}`. |
| Лишняя платформа | Build публикует `amd64` и `arm64`, хотя Terraform выбирает `x86_64` AMI и `t3` instances. |
| Mutable dependencies | GitHub Actions используют major tags; Compose использует mutable tags, включая `certbot:latest`. |
| Неполный security-контур | Есть Gitleaks, но нет dependency audit, `actionlint`, `zizmor`, IaC policy gate, SBOM и обязательной image policy. |
| Лишние releases | Нет change routing, поэтому docs-only и другие нерелевантные push могут дойти до build/deploy. |

## 3. Целевая структура файлов

```text
.github/workflows/
  delivery.yml
  project-validation.yml
  repository-security.yml
  container-image.yml
  deploy-app.yml
  security-monitoring.yml
```

`publish-image.yml` после переходного периода поглощается двумя контурами:

- orchestration переходит в `delivery.yml`;
- build/publish переходит в `container-image.yml`.

### 3.1. `delivery.yml`

Единственная ответственность: **оркестрация**.

Владеет:

- `pull_request`;
- push в `development` и `main`;
- `needs`, условиями запуска и выбором GitHub environment;
- итоговым стабильным required check;
- передачей digest из container workflow в deploy workflow.

Не владеет:

- shell-командами проверок;
- Python setup;
- Docker/Buildx;
- vulnerability scanning;
- AWS SSM-командами;
- реализацией rollback.

Для branch push это единственный прямой trigger. Остальные контуры вызываются через
`workflow_call`, иначе GitHub запустит одинаковую работу как отдельными workflow, так и через
orchestrator.

### 3.2. `project-validation.yml`

Единственная ответственность: **корректность приложения**.

Jobs:

| Job | Содержимое |
| --- | --- |
| `quality` | `git diff --check`, Ruff format, Ruff lint и mypy в одном checkout/Python environment. |
| `unit` | Только unit tests. |
| `runtime` | Integration tests и source-level Uvicorn smoke на одном PostgreSQL/Redis service stack. |

Правила:

- Docker build, Gitleaks, AWS и deploy отсутствуют;
- локальный и CI-запуск используют одни канонические Make/script targets;
- unit и runtime остаются раздельными, потому что это разные test layers;
- integration и Uvicorn не удаляются, а совместно используют setup.

Ожидаемый результат полной validation: 3 Python environments вместо 6 и 1 service stack вместо 2.

### 3.3. `repository-security.yml`

Единственная ответственность: **безопасность repository inputs и CI supply chain**.

Содержит:

- проверку tracked ignored/local files;
- Gitleaks;
- audit Python dependencies;
- `actionlint` для синтаксиса и expressions;
- `zizmor` для security policy GitHub Actions;
- Terraform/Dockerfile/Compose configuration scan;
- проверку, что external Actions закреплены полным commit SHA;
- SARIF/job summary без доступа к deploy credentials.

Не содержит:

- build или push application image;
- scan опубликованного application image;
- AWS SSM;
- deployment.

Политика Actions:

- `permissions` задаются явно и минимально;
- checkout не сохраняет credentials, если последующий push не нужен;
- external Actions закрепляются полным SHA с комментарием версии;
- Dependabot обновляет `github-actions`;
- `continue-on-error` запрещен для обязательных security checks.

### 3.4. `container-image.yml`

Единственная ответственность: **создание и аттестация application image**.

Имеет два режима одного и того же контракта:

#### PR mode

- одна `linux/amd64` сборка без push;
- container-level startup/health smoke на собранном image;
- Dockerfile/Compose policy проверяется repository security;
- exact-image vulnerability gate выполняется после trusted push;
- AWS credentials и ECR write access отсутствуют.

#### Trusted release mode

1. Проверить, существует ли artifact для source SHA.
2. Если нет — выполнить один BuildKit build и push.
3. Получить manifest digest из build output или ECR.
4. Сгенерировать и прикрепить SBOM.
5. Явно сгенерировать provenance.
6. Дождаться authoritative vulnerability scan.
7. Применить severity/exception policy.
8. Создать или проверить подпись image.
9. Вернуть approved `repository@sha256:...` orchestrator-у.

Если image для SHA уже существует, build пропускается, но scan policy, provenance/signature и
approval не пропускаются. Повторное использование artifact не должно быть обходом security gate.

До появления ARM EC2:

- target platform — только `linux/amd64`;
- QEMU не запускается;
- cache хранится через BuildKit/GitHub cache;
- при возврате multi-platform каждый реально deployable platform manifest сканируется отдельно.

### 3.5. `deploy-app.yml`

Единственная ответственность: **доставка уже одобренного artifact**.

Inputs:

- `target_environment`;
- полный `image_reference` в формате `repository@sha256:<digest>`;
- `source_sha`;
- идентификатор security evidence/attestation.

Владеет:

- GitHub environment approval;
- environment-scoped concurrency;
- проверкой существования digest и security evidence;
- stale-deploy guard;
- AWS OIDC только для deploy role;
- SSM rollout;
- internal health check на EC2;
- external HTTPS health check;
- сохранением предыдущего digest;
- автоматическим или ручным rollback на предыдущий digest.

Не владеет:

- source checks;
- build;
- vulnerability scan;
- публикацией image.

Manual rollback принимает только существующий approved digest. Произвольный tag не является
достаточным deployment input.

### 3.6. `security-monitoring.yml`

Единственная ответственность: **поиск новых рисков после выпуска**.

Scheduled workflow:

- проверяет актуальные findings для digest, реально развернутых в development и production;
- контролирует срок действия security exceptions;
- проверяет сторонние runtime images из Compose;
- создает alert/issue/SARIF, но ничего не публикует и не деплоит.

## 4. Целевые потоки

### Pull request

```text
delivery
  ├─ project-validation
  ├─ repository-security
  └─ container-image (PR mode, no push)
       |
       v
    pr-gate
```

PR artifact не продвигается в production: после merge меняются SHA и trust context. BuildKit cache
может ускорять trusted build, но не превращает untrusted PR image в release artifact.

### Push в `development`

```text
project-validation ─┐
repository-security ├─> container build/push once
                    │      -> digest
                    │      -> SBOM + provenance
                    │      -> scan + signature policy
                    └───────────────────────────────> deploy development
                                                        -> internal health
                                                        -> external health
                                                        -> rollback on failure
```

### Push в `main`

```text
validation + security
  -> reuse already approved digest for the same SHA, or build once
  -> re-check current findings and signature
  -> production environment approval
  -> stale-deploy guard
  -> deploy exact digest
  -> health / rollback
```

Предпочтительный release contract — продвигать в production тот же digest, который прошел
development. Если `main` создает новый merge SHA, он получает один новый trusted build; скрытого
повторного build внутри того же pipeline быть не должно.

### Manual rollback

```text
environment + approved digest
  -> verify digest / scan / signature
  -> SSM deploy
  -> health check
```

Rollback не запускает validation, build или publish.

## 5. Что устраняется, а что остается намеренно

| Работа | Решение | Причина |
| --- | --- | --- |
| Два Docker build в одном branch pipeline | Устранить | Один trusted build должен создать единственный deployable artifact. |
| Шесть одинаковых Python setup/install | Сократить до трех | Static checks могут совместно использовать environment; test layers сохраняют изоляцию. |
| Два PostgreSQL/Redis stack | Объединить | Integration и Uvicorn могут выполняться последовательно в одном runtime job. |
| CI-команды и Make-команды | Оставить одну точку истины | Workflow должен вызывать канонические локальные targets. |
| PR build и release build | Оставить | Разные SHA и trust boundaries. |
| PR validation и validation итогового merge SHA | Оставить | Проверять нужно именно deployable commit. |
| Repository dependency audit и image scan | Оставить | Первый дает раннюю проверку manifest, второй проверяет фактический artifact. |
| Source/Uvicorn, container и deployed health | Оставить | Это разные уровни: процесс, image и развернутая система. |
| Publish/deploy input validation | Оставить | Manual deploy обязан fail closed независимо от caller. |
| ECR scan и второй параллельный image scanner | Не делать двумя gates | Для release должен быть один authoritative policy source. |

## 6. Image security policy

### 6.1. Выбранная базовая модель

Для текущей архитектуры выбрана следующая модель:

- **Trivy** — единственный authoritative release vulnerability scanner;
- **BuildKit** — SBOM и provenance в рамках того же build;
- **ECR managed signing / AWS Signer** — подпись;
- **ECR managed signing status** — повторная проверка подписи на deploy boundary.

ECR basic `scan_on_push` остается informational и не участвует в blocking policy.

### 6.2. Blocking policy

Переход выполняется в два этапа:

1. Baseline run публикует полный отчет без разрешения deploy и фиксирует текущие findings.
2. После triage gate блокирует `CRITICAL` и `HIGH` findings с доступным исправлением.

Исключение допускается только как versioned запись с:

- CVE/finding ID;
- причиной;
- ответственным;
- ссылкой на remediation task;
- датой истечения.

Правила:

- scanner error или timeout означает failed gate;
- blanket-ignore и бессрочные исключения запрещены;
- unfixed findings видимы и имеют remediation SLA;
- reused image повторно проходит текущую policy;
- scan result связывается с digest, не с mutable tag.

### 6.3. Third-party runtime images

Application image scan не покрывает:

- `postgres:16-alpine`;
- `redis:7-alpine`;
- `nginx:1.27-alpine`;
- `certbot/certbot:latest`.

Поэтому отдельный этап должен:

1. Закрепить runtime images по digest.
2. Убрать их неявное обновление из обычного application deploy.
3. Обновлять их отдельным dependency change с development verification.
4. Для единой AWS security model зеркалировать deployable images в управляемый ECR или явно
   определить отдельный scheduled scanner.

`certbot:latest` имеет наивысший приоритет, потому что сейчас не фиксирует даже minor version.

### 6.4. Container hardening backlog

Scan не заменяет исправление самого image. После ввода gate отдельно планируются:

- pinned base image digest;
- non-root runtime user;
- отделение test/dev dependencies от production dependencies;
- минимизация слоев и пакетов;
- проверка лишних host ports;
- ограничение container capabilities и read-only filesystem там, где это совместимо с uploads.

Эти изменения не входят в текущую реструктуризацию workflow.

## 7. Контракты и permissions

| Контур | Минимальные права | Inputs | Outputs |
| --- | --- | --- | --- |
| `delivery` | `contents: read` | event context | итоговый gate |
| `project-validation` | `contents: read` | source SHA | validation status |
| `repository-security` | `contents: read`; `security-events: write` только для SARIF | source SHA | security status/report |
| `container-image` PR | `contents: read` | source SHA, `publish=false` | container status |
| `container-image` release | `contents: read`, `id-token: write`; ECR publish role через OIDC | source SHA, repository, platform | digest, image reference, evidence ID |
| `deploy-app` | `actions: read`, `contents: read`, `id-token: write`; SSM deploy role через OIDC | environment, digest, evidence ID | deployment/rollback result |
| `security-monitoring` | read-only ECR access; write только в выбранный alert channel | deployed digests | Trivy findings summary |

У `delivery.yml` глобальный default остается `contents: read`, но jobs, вызывающие reusable
`container-image` и `deploy-app`, явно получают `id-token: write`. Reusable workflow не должен и
не может повысить права, не выданные caller job.

Секреты не передаются через `secrets: inherit`. Каждый reusable workflow получает только явно
объявленный input/secret. ARN роли предпочтительно хранится как configuration value, а не как
долгоживущий credential.

## 8. Change routing

Path routing добавляется только после появления стабильного агрегирующего required check.
Иначе skipped workflow может исчезнуть из branch protection.

| Изменение | Проверки | Build/deploy |
| --- | --- | --- |
| `app/**`, `main.py`, runtime config, `requirements.txt`, `Dockerfile` | application + repository security + container | Полный release flow. |
| Только `tests/**` | application + relevant security | Без publish/deploy. |
| `.github/**` | actionlint + zizmor + workflow policy | Без application deploy. |
| `infra/**` | Terraform validation + IaC security | Без application image/deploy. |
| Только docs | diff/docs checks | Без image/deploy. |
| `docker-compose.yml`, `nginx/**`, `deploy/**` | deployment bundle checks | Deploy с последним approved digest только после появления надежного environment digest state. |

До реализации надежного environment digest state изменения deployment bundle проходят полный
release flow. Нельзя угадывать текущий digest или молча брать `latest`.

## 9. Порядок миграции

### Этап 0. Зафиксировать baseline

- записать required checks и branch/environment protections;
- измерить duration, runner minutes, cache hit rate и количество builds;
- подтвердить live ECR scan mode;
- подтвердить, что все active EC2 остаются `x86_64`;
- записать текущие development/production digests и рабочий rollback;
- определить владельца каждого security exception.

Готово, когда есть измеримый baseline и rollback point.

### Этап 1. Зафиксировать workflow contracts

- утвердить целевое дерево файлов;
- утвердить inputs, outputs, permissions и required-check names;
- выбрать один authoritative image scanner;
- определить digest format и security evidence;
- сохранить текущие три workflow до окончания development proof.

Готово, когда контракты можно реализовать без скрытой передачи tags, secrets или state.

### Этап 2. Разделить application и repository security

- объединить format, lint, mypy и diff в `quality`;
- оставить unit отдельным;
- объединить integration и Uvicorn setup в `runtime`;
- перенести Gitleaks и workflow/IaC checks в `repository-security.yml`;
- сделать локальные Make/script targets единственной точкой истины.

Готово, когда application validation не содержит Docker/AWS/security implementation и дает те же
или более строгие результаты.

### Этап 3. Создать единый container pipeline

- удалить Docker build из application validation только после появления замены;
- PR: build once, no push, container smoke;
- push: build/push once, вернуть digest;
- использовать `linux/amd64` и не запускать QEMU;
- включить BuildKit cache;
- reused image не должен обходить последующие gates.

Готово, когда один branch run содержит ровно один trusted build, а deployable artifact однозначно
определен digest.

### Этап 4. Добавить security gates

- pin external Actions по full SHA;
- включить actionlint, zizmor, dependency и IaC checks;
- включить выбранный authoritative image scanner;
- дождаться scan completion и применить severity policy;
- добавить SBOM и explicit provenance;
- настроить expiring exception registry;
- добавить signing и verification.

Готово, когда уязвимый, непроверенный или неподписанный digest не может попасть в deploy job.

### Этап 5. Перевести deployment на digest

- заменить tag contract на `repository@sha256:...`;
- добавить stale-deploy guard перед SSM;
- сохранить previous digest;
- добавить internal и external health;
- проверить manual и automatic rollback;
- повторно проверять evidence перед production deployment.

Готово, когда старый run не может перезаписать новый deployment, а failed health возвращает
предыдущий рабочий digest.

### Этап 6. Development proof и production rollout

- запустить новую схему параллельно без production deploy;
- сравнить результаты старых и новых checks;
- включить deployment только для `development`;
- выполнить normal release, reused-image release и rollback drill;
- собрать минимум несколько успешных запусков;
- включить production approval и production deploy;
- только после этого удалить старый `publish-image.yml`.

Готово, когда development и production используют один документированный digest contract.

### Этап 7. Убрать оставшиеся скрытые обновления

- закрепить и проверить Compose runtime images;
- добавить scheduled monitoring;
- добавить change routing;
- обновить required checks и CODEOWNERS/branch protections;
- обновить `.github/docs/github-actions.md` и `docs/deploy.md` как current-state документацию.

## 10. Критерии готовности всей реструктуризации

### Эффективность

- один trusted application image build на новый SHA;
- не более трех Python dependency setups на полную validation;
- один PostgreSQL/Redis service stack;
- QEMU отсутствует, пока нет ARM target;
- docs/test/workflow/infra-only changes не публикуют application image;
- runner minutes и median pipeline duration не хуже baseline, целевое снижение фиксируется после
  первых измерений.

### Разделение ответственности

- orchestrator не содержит implementation steps;
- application validation не знает о Docker/ECR/SSM;
- repository security не публикует image;
- container workflow не деплоит;
- deploy workflow не строит и не сканирует;
- scheduled monitoring ничего не изменяет.

### Security

- все external Actions pinned по full SHA;
- Gitleaks, dependency, workflow и IaC checks обязательны;
- deploy зависит от успешной image policy;
- SBOM, provenance, scan result и signature связаны с одним digest;
- exception имеет owner и expiry;
- сторонние runtime images закреплены и мониторятся;
- долгоживущих AWS/registry credentials нет.

### Reliability

- development и production деплоят exact digest;
- stale run не может выполнить deploy;
- internal и external health обязательны;
- previous digest известен до rollout;
- rollback drill успешно выполнен;
- production сохраняет environment approval и serial deployment.

## 11. Статус реализации

- Этапы 0–1: baseline и workflow contracts зафиксированы.
- Этап 2: application validation и repository security разделены.
- Этап 3: создан единый PR/release container pipeline с одним `linux/amd64` build.
- Этап 4: external Actions закреплены, repository security gates и expiring exception registry
  реализованы; Trivy выбран единственным release image scanner, BuildKit SBOM/provenance и managed
  signing применены. ECR basic `scan-on-push` остается informational.
- Этап 5: deploy принимает только exact digest и content-addressed evidence, проверяет stale run,
  существование digest и managed-signing status, сохраняет previous digest, выполняет internal и
  external health и возвращает previous digest при ошибке. Automatic и manual rollback покрыты
  локальными contract tests.
- Этап 6 не включен: новый pipeline должен пройти development proof в GitHub Actions без
  production deploy до удаления переходного workflow.
- Current-state документы обновляются только на Этапе 7 после полного перехода.

## 12. Официальные источники для реализации

- [Amazon ECR image scanning](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-scanning.html)
- [Trivy image scanning](https://trivy.dev/latest/docs/target/container_image/)
- [Amazon ECR managed image signing](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-signing.html)
- [Docker BuildKit SBOM and provenance](https://docs.docker.com/build/ci/github-actions/attestations/)
- [GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use)
- [GitHub reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)
