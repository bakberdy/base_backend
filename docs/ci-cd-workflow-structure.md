# Структура CI/CD workflow и зоны ответственности

Статус: фактическая структура репозитория.

Этот документ является единой картой GitHub Actions для backend-проекта. Он описывает:

- какие события запускают проверки и релизы;
- как workflow вызывают друг друга;
- за что отвечает каждая job;
- какие данные, permissions и артефакты проходят между job;
- где заканчивается зона ответственности одной job и начинается другая;
- как обрабатываются отмена устаревших проверок, ошибки деплоя и rollback.

Источник истины для реализации — файлы в `.github/workflows`. Этот документ должен обновляться
вместе с изменением их структуры.

## 1. Общая схема

В репозитории есть шесть workflow:

| Workflow | Тип | Основная ответственность |
| --- | --- | --- |
| `delivery.yml` | PR orchestrator | Запустить все обязательные проверки pull request и сформировать единственный required check `Delivery Gate`. |
| `project-validation.yml` | Reusable | Проверить качество, unit-тесты и runtime-поведение приложения. |
| `repository-security.yml` | Reusable | Проверить секреты, зависимости, GitHub Actions и инфраструктурные конфигурации. |
| `container-image.yml` | Reusable | Проверить контейнер в PR или собрать, проверить и опубликовать immutable release image. |
| `publish-image.yml` | Tag-release orchestrator | Проверить release tag, запустить release gates и направить релиз в development или production. |
| `deploy-app.yml` | Reusable и manual | Развернуть один одобренный digest на одном EC2 environment и выполнить rollback при ошибке. |

Постоянная ветка одна:

```text
main
```

Проверки pull request:

```text
Pull request -> main
        |
        +--> Application Validation ------+
        |                                 |
        +--> Repository Security ---------+--> Delivery Gate
        |                                 |
        +--> PR Container Validation -----+
```

Development release:

```text
vX.Y.Z-dev.N на текущем main HEAD
        |
        +--> Release Contract
        +--> Application Validation
        +--> Repository Security
                 |
                 +--> Release Container
                           |
                           +--> Deploy development
```

Production release:

```text
vX.Y.Z на текущем main HEAD
        |
        +--> Release Contract
        +--> Application Validation
        +--> Repository Security
                 |
                 +--> Release Container
                           |
                           +--> Deploy production
```

## 2. Владение событиями

| Событие | Workflow-owner | Результат |
| --- | --- | --- |
| PR открыт, обновлен, переоткрыт или переведен из draft в ready | `delivery.yml` | Полный набор обязательных PR-проверок. |
| Merge queue сформировала merge group | `delivery.yml` | Повторная проверка итогового merge commit. |
| Создан tag `vX.Y.Z-dev.N` | `publish-image.yml` | Release pipeline и деплой в `development`. |
| Создан tag `vX.Y.Z` | `publish-image.yml` | Release pipeline и деплой в `production`. |
| Ручной запуск approved digest | `deploy-app.yml` | Деплой выбранного immutable image в выбранное environment. |

Не являются trigger:

- обычный push в `main`;
- push в feature-ветку без pull request;
- ветка `development`;
- произвольный tag, не соответствующий release-схеме.

## 3. Concurrency и отмена дублирующихся запусков

| Workflow | Concurrency group | `cancel-in-progress` | Причина |
| --- | --- | --- | --- |
| `delivery.yml` | `delivery-pr-<PR number или ref>` | `true` | Новый commit в том же PR отменяет устаревший набор проверок. |
| `project-validation.yml` | `project-validation-<ref>` | `true` | Не выполнять application checks повторно для устаревшего ref. |
| `repository-security.yml` | `repository-security-<ref>` | `true` | Не выполнять security checks повторно для устаревшего ref. |
| `container-image.yml` | `container-image-<ref>` | `true` | Не продолжать устаревший PR build. |
| `publish-image.yml` | `publish-image-<tag ref>` | `false` | Release tag является отдельным immutable release event и не отменяется новым tag. |
| `deploy-app.yml` | `deploy-<environment>` | `false` | Деплои одного environment сериализуются и не прерывают выполняющийся rollout/rollback. |

Главный механизм устранения дублей в pull request:

```text
один PR number -> одна concurrency group -> новый push отменяет старый Delivery run
```

GitHub может сохранять отмененные runs в истории, но обязательным результатом является
`Delivery Gate` последнего commit.

## 4. `delivery.yml`: PR orchestration

### Назначение

`delivery.yml` владеет только orchestration pull request. Он не реализует lint, тесты,
security scan, Docker build или deploy самостоятельно.

### Trigger

```text
pull_request -> main:
  opened
  synchronize
  reopened
  ready_for_review

merge_group
```

### Permissions

Workflow default:

```text
contents: read
```

Только вызов container workflow получает `id-token: write`, потому что reusable workflow
содержит release job с максимальным объявленным permission. В PR mode AWS credentials не
используются и image не публикуется.

### Jobs

#### `validation` — Application Validation

Вызывает:

```text
project-validation.yml
```

Передает:

```text
source_sha = PR head SHA или merge-group SHA
```

Ответственность:

- запустить единый reusable application validation;
- привязать все application checks к проверяемому commit.

Не отвечает за:

- security checks;
- container checks;
- публикацию image;
- deploy.

#### `repository-security` — Repository Security

Вызывает:

```text
repository-security.yml
```

Передает:

```text
source_sha   = PR head SHA или merge-group SHA
upload_sarif = false
```

Ответственность:

- запустить единый reusable repository-security контур;
- проверять тот же commit, что и остальные PR jobs.

Не отвечает за application correctness, Docker build или deploy.

#### `container` — Container Validation

Вызывает:

```text
container-image.yml
```

Передает:

```text
mode       = pr
source_sha = PR head SHA или merge-group SHA
platform   = linux/amd64
```

Ответственность:

- запросить только PR-вариант container validation;
- не передавать ECR repository и release credentials.

Не отвечает за release image или deploy.

#### `delivery-gate` — Delivery Gate

Зависит от:

```text
validation
repository-security
container
```

Запускается с:

```text
if: always()
```

Ответственность:

- собрать результаты трех обязательных reusable workflows;
- завершиться успешно, только если все три результата равны `success`;
- быть единственным стабильным required-check context для branch protection.

Любой `failure`, `cancelled` или неожиданный `skipped` блокирует gate.

Не отвечает за выполнение самих проверок.

## 5. `project-validation.yml`: application correctness

### Контракт

Тип:

```text
workflow_call
```

Input:

| Input | Значение |
| --- | --- |
| `source_sha` | Полный SHA проверяемого исходного кода. |

Output:

| Output | Значение |
| --- | --- |
| `status` | `success`, только если прошел `Application Gate`. |

Permissions:

```text
contents: read
```

### Jobs

#### `quality` — Application Quality

Ответственность:

- checkout точного `source_sha`;
- `git diff --check` для PR или проверка whitespace текущего commit;
- установка Python 3.13 и application dependencies;
- `format-check`;
- lint;
- type-check.

Команда:

```text
make PYTHON=python format-check lint type-check
```

Граница ответственности: только статическое качество исходного кода. Job не запускает
unit/runtime tests и не проверяет repository security.

#### `unit` — Unit Tests

Ответственность:

- checkout точного `source_sha`;
- установка Python 3.13 и dependencies;
- запуск изолированных unit-тестов.

Команда:

```text
make PYTHON=python test-unit
```

Граница ответственности: быстрые детерминированные тесты без владения runtime stack.

#### `runtime` — Runtime Tests

Поднимает service containers:

```text
PostgreSQL 16
Redis 7
```

Ответственность:

- дождаться healthy PostgreSQL и Redis;
- установить приложение в Python 3.13 environment;
- выполнить runtime/integration checks и Uvicorn smoke через единый Make target.

Команда:

```text
make PYTHON=python runtime-check
```

Граница ответственности: поведение приложения с тестовой инфраструктурой. Job не использует
development/production services и не собирает release container.

#### `application-gate` — Application Gate

Зависит от:

```text
quality
unit
runtime
```

Ответственность:

- агрегировать application jobs независимо от порядка их завершения;
- вернуть `status=success`, только если все три job успешны;
- не скрывать failure, cancelled или skipped.

## 6. `repository-security.yml`: repository и supply-chain security

### Контракт

Тип:

```text
workflow_call
```

Inputs:

| Input | Значение |
| --- | --- |
| `source_sha` | Полный SHA проверяемого исходного кода. |
| `upload_sarif` | Флаг trusted-context SARIF upload; в текущих callers передается `false`. |

Outputs:

| Output | Значение |
| --- | --- |
| `status` | `success`, только если прошел `Repository Security Gate`. |
| `report_id` | Идентификатор вида `run_id:run_attempt`. |

Default permissions:

```text
contents: read
```

### Jobs

#### `secrets` — Secret Scan

Ответственность:

- checkout с полной Git history;
- отклонить ignored/local files, которые уже попали в Git index;
- скачать pinned Gitleaks и проверить checksum;
- просканировать Git repository на секреты с redaction.

Граница ответственности: утечки секретов и ошибочно tracked local files. Job не проверяет
dependency CVE, workflow policy или IaC.

#### `dependencies` — Dependency Audit

Ответственность:

- установить pinned `pip-audit`;
- проверить `requirements.txt` через repository policy wrapper;
- учесть только формально зарегистрированные security exceptions;
- записать evidence в GitHub Step Summary.

Команда:

```text
python tool/ci/dependency_audit.py requirements.txt
```

Граница ответственности: известные уязвимости Python dependencies.

#### `workflows` — Workflow Security

Ответственность:

- скачать pinned `actionlint` и проверить checksum;
- проверить YAML, expressions и shell-фрагменты всех workflow;
- запустить pinned `zizmor` с persona `pedantic`;
- контролировать GitHub Actions supply-chain policy;
- записать evidence в Step Summary.

Инструменты:

```text
actionlint 1.7.12
zizmor 1.28.0
```

Граница ответственности: только `.github/workflows` и безопасность GitHub Actions.

#### `configuration` — Configuration Security

Ответственность:

- проверить сроки и формат security exceptions;
- построить path-scoped Trivy ignore file;
- проверить policy Docker Compose;
- просканировать Docker и Terraform configuration через Trivy;
- блокировать HIGH и CRITICAL findings без действующего исключения;
- записать evidence в Step Summary.

Команды и инструменты:

```text
python3 tool/ci/security_exceptions.py validate
make PYTHON=python3 compose-check
Trivy config 0.72.0
```

Граница ответственности: IaC, Dockerfile/Compose и configuration policy. Эта job не сканирует
готовый release image — это ответственность `container-image.yml`.

#### `repository-security-gate` — Repository Security Gate

Зависит от:

```text
secrets
dependencies
workflows
configuration
```

Ответственность:

- завершиться успешно только при успехе всех четырех security jobs;
- вернуть `status=success`;
- сформировать `report_id`.

## 7. `container-image.yml`: единый owner application image

### Контракт

Тип:

```text
workflow_call
```

Inputs:

| Input | Назначение |
| --- | --- |
| `mode` | `pr` или `release`. |
| `source_sha` | Полный SHA, который должен представлять image. |
| `platform` | Текущая разрешенная deploy platform: `linux/amd64`. |
| `repository_uri` | Private ECR URI; нужен только для release mode. |

Outputs:

| Output | Назначение |
| --- | --- |
| `source_sha` | SHA, представленный release artifact. |
| `image_digest` | Immutable OCI digest. |
| `image_reference` | Точная ссылка `repository@sha256:digest`. |
| `security_evidence_id` | Идентификатор digest-bound security evidence. |
| `status` | Результат выбранного mode. |

### Jobs

#### `pr` — PR Container

Условие:

```text
pull_request event или mode=pr
```

Permissions:

```text
contents: read
```

Ответственность:

- checkout проверяемого SHA;
- собрать local image один раз для `linux/amd64`;
- использовать GitHub Actions build cache;
- не выполнять push;
- запустить container health smoke на собранном image.

Граница ответственности:

- не обращаться к AWS;
- не публиковать image;
- не создавать release evidence;
- не выполнять deploy.

#### `release` — Release Container

Условие:

```text
mode=release
```

Permissions:

```text
contents: read
id-token: write
```

Ответственность по порядку:

1. Проверить full SHA, `linux/amd64` и формат private ECR URI.
2. Получить short-lived AWS credentials через GitHub OIDC.
3. Войти в private ECR.
4. Найти существующий image с tag `sha-<source_sha>`.
5. Повторно использовать существующий digest либо один раз собрать и push image.
6. При новой сборке сформировать provenance и SBOM.
7. Разрешить top-level immutable digest.
8. Просканировать точный `repository@digest` через Trivy.
9. Проверить vulnerability policy, attestation и managed ECR signing.
10. Сформировать digest-bound `image-security-evidence.json`.
11. Сохранить security evidence и Trivy report как GitHub artifact на 90 дней.
12. Вернуть immutable release outputs.

Ключевой инвариант:

```text
один source SHA -> один immutable ECR digest -> один набор security evidence
```

Release job не выбирает target environment и не выполняет SSM deploy.

#### `container-gate` — Container Gate

Зависит от:

```text
pr
release
```

Ответственность:

- учитывать только job выбранного mode;
- для `pr` требовать успех `PR Container`;
- для `release` требовать успех `Release Container`;
- экспортировать release outputs вызывающему workflow;
- считать failure выбранного mode общим container failure.

Skipped job другого mode является ожидаемым и не блокирует gate.

## 8. `publish-image.yml`: release orchestration

### Trigger

Development:

```text
vX.Y.Z-dev.N
```

Production:

```text
vX.Y.Z
```

Оба tag должны указывать на текущий HEAD защищенной ветки `main`.

### Concurrency

```text
group: publish-image-<tag ref>
cancel-in-progress: false
```

Каждый release tag — отдельный immutable release event.

### Jobs

#### `release-contract` — Release Contract

Ответственность:

- распознать поддерживаемый tag;
- преобразовать `vX.Y.Z-dev.N` в `development`;
- преобразовать `vX.Y.Z` в `production`;
- получить текущий `main` HEAD через GitHub API;
- запретить release, если tag указывает не на текущий `main` HEAD;
- вернуть `target_environment`.

Не отвечает за application/security checks, сборку или deploy.

#### `validate`

Вызывает `project-validation.yml` для `github.sha`.

Ответственность: не доверять предыдущему PR run и повторно проверить точный release commit.

#### `repository-security`

Вызывает `repository-security.yml` для `github.sha`.

Ответственность: повторно проверить repository и supply-chain security точного release commit.

#### `container`

Зависит от:

```text
release-contract
validate
repository-security
```

Вызывает `container-image.yml`:

```text
mode           = release
source_sha     = tag SHA
platform       = linux/amd64
repository_uri = ECR_REPOSITORY_URI
```

Ответственность:

- не запускать публикацию, пока release contract, application и repository security не успешны;
- передать `id-token: write` только release container workflow;
- получить точные `image_reference` и `security_evidence_id`.

#### `deploy`

Зависит от:

```text
release-contract
container
```

Вызывает `deploy-app.yml` с:

```text
target_environment
source_sha
image_reference
security_evidence_id
AWS_ROLE_TO_ASSUME
```

Ответственность:

- направить одобренный artifact в environment, выбранное исключительно release tag;
- не изменять и не пересобирать artifact;
- предоставить deploy workflow минимальные `actions: read`, `contents: read`,
  `id-token: write`.

## 9. `deploy-app.yml`: deployment и rollback

### Контракт

Типы запуска:

```text
workflow_call
workflow_dispatch
```

Inputs:

| Input | Назначение |
| --- | --- |
| `target_environment` | Только `development` или `production`. |
| `source_sha` | SHA, представленный image. |
| `image_reference` | Точный private ECR `repository@sha256:digest`. |
| `security_evidence_id` | Идентификатор evidence для этого SHA и digest. |

Secret:

| Secret | Назначение |
| --- | --- |
| `AWS_ROLE_TO_ASSUME` | AWS role для SSM deploy через GitHub OIDC. |
| `CORS_ALLOWED_ORIGINS` | Environment-scoped HTTPS allowlist, скрытый из Git и Actions logs. |

Outputs:

| Output | Назначение |
| --- | --- |
| `deployed_digest` | Digest, оставшийся развернутым после health/rollback. |
| `previous_digest` | Digest, работавший до rollout. |
| `deployment_status` | `success`, `rolled_back` или `rollback_failed`. |
| `ssm_command_id` | Идентификатор первоначальной SSM-команды. |

Environment:

```text
GitHub environment = target_environment
```

Environment предоставляет:

```text
EC2_INSTANCE_ID
DEPLOY_HEALTH_URL
CORS_ALLOWED_ORIGINS (environment secret)
```

Repository variables предоставляют:

```text
AWS_REGION
PROJECT_NAME
ECR_REPOSITORY_URI
AWS_ECR_SIGNING_PROFILE_ARN
```

Permissions:

```text
actions: read
contents: read
id-token: write
```

### Job `deploy` — Deploy `<environment>`

Это единственная job workflow. Ее внутренняя структура разделена на последовательные
контрольные зоны.

#### Зона 1. Immutable deployment contract

Шаги:

```text
Check out approved source
Validate immutable deployment contract
Reject stale automatic deployment
```

Ответственность:

- разрешить только development/production;
- проверить `PROJECT_NAME`, full SHA, ECR repository@digest и evidence ID;
- убедиться, что image принадлежит настроенному ECR;
- проверить EC2 instance ID и `/health` URL;
- для автоматического tag release отклонить SHA, который больше не является текущим main HEAD.

#### Зона 2. Security evidence и image identity

Шаги:

```text
Download content-addressed security evidence
Verify stored security evidence
Configure AWS credentials
Revalidate digest and managed signature
```

Ответственность:

- скачать evidence из конкретного source run;
- криптографически/структурно связать evidence с source SHA и image digest;
- получить временные AWS credentials через OIDC;
- повторно убедиться, что digest существует в ECR;
- требовать статус managed signature `COMPLETE`.

Deploy не доверяет только outputs предыдущей job и повторно валидирует artifact перед mutation.

#### Зона 3. EC2 rollout

Шаги:

```text
Send digest deployment to EC2
Wait for internal rollout
```

Ответственность:

- передать Compose, nginx и EC2 scripts через AWS SSM;
- запустить `rollout.sh deploy` для точного digest;
- не использовать SSH и статические AWS credentials;
- дождаться завершения SSM command;
- получить `PREVIOUS_IMAGE`;
- требовать внутренний marker `DEPLOYMENT_STATUS=success`.

#### Зона 4. External health

Шаг:

```text
Verify external health
```

Ответственность:

- проверить реальный публичный HTTPS `/health`;
- следовать redirect;
- не отключать TLS verification;
- повторить временные сетевые ошибки ограниченное число раз.

Правильные environment URLs:

```text
development -> https://dev.api.bakberdi.dev/health
production  -> https://api.bakberdi.dev/health
```

IP-адрес нельзя использовать как HTTPS hostname, если он отсутствует в SAN сертификата.

#### Зона 5. Automatic rollback

Шаг:

```text
Roll back after failed health
```

Условие:

```text
always() и internal rollout либо external health неуспешен
```

Ответственность:

- запускаться даже после failed health step;
- проверить наличие валидного previous digest;
- через SSM выполнить `rollout.sh rollback`;
- дождаться результата rollback;
- вернуть `rollback_status`.

#### Зона 6. Deployment result

Шаг:

```text
Set deployment result
```

Запускается с:

```text
if: always()
```

Матрица результата:

| Internal rollout | External health | Rollback | `deployment_status` | Job result |
| --- | --- | --- | --- | --- |
| success | success | не нужен | `success` | success |
| failure или success | failure | success | `rolled_back` | failure |
| failure или success | failure | failure/нет digest | `rollback_failed` | failure |

Rollback возвращает сервис к предыдущему digest, но release run остается failed, чтобы ошибка
не была скрыта.

## 10. Разделение зон ответственности

| Область | Единственный owner | Не должен выполнять |
| --- | --- | --- |
| PR orchestration и required check | `delivery.yml` | Реализацию lint/test/scan/build/deploy. |
| Application static quality | `quality` | Runtime tests, security или Docker. |
| Unit tests | `unit` | External services или deploy. |
| Runtime/integration tests | `runtime` | Development/production access. |
| Secrets | `secrets` | Dependency или image CVE scan. |
| Dependency CVE | `dependencies` | Workflow/IaC policy. |
| GitHub Actions policy | `workflows` | Application tests или deploy. |
| IaC/Docker config security | `configuration` | Release image scan. |
| PR image smoke | `container-image.yml: pr` | ECR push или AWS credentials. |
| Release image, SBOM, scan и signing evidence | `container-image.yml: release` | Выбор environment или deploy. |
| Release tag routing | `publish-image.yml: release-contract` | Build или infrastructure mutation. |
| EC2 deploy и rollback | `deploy-app.yml: deploy` | Build, source validation suite или изменение image. |
| Branch protection и GitHub variables | `infra/terraform` | Application release implementation. |

## 11. Security boundaries

### Без AWS permissions

```text
delivery.yml application/security calls
project-validation.yml
repository-security.yml
container-image.yml PR job
```

### С `id-token: write`

```text
container-image.yml release job -> ECR publish role
deploy-app.yml deploy job       -> SSM deploy role
```

AWS static access keys не хранятся в GitHub. Credentials создаются на время job через OIDC.

### Artifact boundary

Deploy принимает только:

```text
source SHA
ECR repository@digest
digest-bound security evidence ID
```

Deploy не принимает mutable image tag как deploy identity.

## 12. Merge и release invariants

Pull request можно merge в `main`, только если последний `Delivery Gate` успешен.

Прямой push и force push в `main` запрещены branch protection.

Development deploy возможен только по tag:

```text
vX.Y.Z-dev.N
```

Production deploy возможен только по tag:

```text
vX.Y.Z
```

Оба tag должны указывать на текущий `main` HEAD. Один и тот же проверенный immutable digest
может быть повторно использован, но не пересобран под тем же source SHA.

## 13. Ownership при отказах

| Ошибка | Job-owner | Ожидаемое поведение |
| --- | --- | --- |
| Format/lint/type failure | `quality` | Блокировать `Application Gate`. |
| Unit failure | `unit` | Блокировать `Application Gate`. |
| PostgreSQL/Redis/runtime failure | `runtime` | Блокировать `Application Gate`. |
| Найден секрет | `secrets` | Блокировать `Repository Security Gate`. |
| Dependency vulnerability | `dependencies` | Блокировать `Repository Security Gate`. |
| Невалидный workflow | `workflows` | Блокировать `Repository Security Gate`. |
| IaC/Compose HIGH или CRITICAL finding | `configuration` | Блокировать `Repository Security Gate`. |
| PR container не собирается/не healthy | `pr` | Блокировать `Container Gate` и `Delivery Gate`. |
| Release image CVE/signature/evidence failure | `release` | Не запускать deploy. |
| Tag не на текущем main HEAD | `release-contract` | Не запускать container release/deploy. |
| Internal rollout failure | `deploy` rollback zone | Попытаться вернуть previous digest и завершить release как failed. |
| External `/health` failure | `deploy` health/rollback zones | Выполнить rollback и завершить release как failed. |
| Rollback failure | `deploy` result zone | Вернуть `rollback_failed` и потребовать ручного вмешательства. |
