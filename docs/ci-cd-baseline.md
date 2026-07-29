# CI/CD baseline

Статус: **зафиксирован**.

Дата снимка: 28 июля 2026 года.

Source revision: `development@e22eaa9ad9dd995e60836aa7eb41b5f01976252b`.

Этот документ фиксирует исходное состояние перед реализацией
`docs/ci-cd-restructuring-plan.md`. Он не является описанием целевой архитектуры.

## 1. Repository и protections

Repository:

```text
bakberdy/base_backend
default branch: main
visibility: public
```

GitHub API на момент снимка:

| Scope | Состояние |
| --- | --- |
| `main` branch protection | Выключен. |
| `development` branch protection | Выключен. |
| Repository rulesets | Отсутствуют. |
| Required status checks | Отсутствуют на обеих ветках. |
| `development` environment protection rules | Отсутствуют. |
| `production` environment protection rules | Отсутствуют. |
| Production required reviewers | Отсутствуют. |
| Environment branch policy | Не задана. |
| Admin bypass | Разрешен для обоих environments. |

Следствие: успешный CI и production approval сейчас не являются enforced merge/deploy
boundaries.

Текущий локальный `gh` token недействителен. Public GitHub API позволил проверить workflows,
branches, rulesets, environments и Actions runs. Значения repository/environment variables и
secrets не читались; их имена и ownership проверены по Terraform и workflow contracts.

## 2. Активные workflows

| Workflow | Trigger | Ответственность сейчас |
| --- | --- | --- |
| `project-validation.yml` | `pull_request`, `workflow_call` | 9 jobs: source, tests, runtime, Docker, Gitleaks и diff. |
| `publish-image.yml` | push `development`/`main`, manual | Вызывает validation, строит/push image и вызывает deploy. |
| `deploy-app.yml` | `workflow_call`, manual | SSM deployment по immutable SHA tag. |

Текущий branch flow:

```text
validate -> publish -> deploy
```

## 3. Performance baseline

### Последний успешный PR run

Run:

```text
Project Validation
run id: 30331655777
source: e22eaa9ad9dd995e60836aa7eb41b5f01976252b
wall-clock: 69 seconds
raw runner time: 263 seconds / 4.38 minutes
estimated per-job rounded runner time: 10 minutes
```

Jobs:

| Job | Duration |
| --- | ---: |
| Sensitive Data & Credentials | 5 s |
| Integration Tests | 67 s |
| Format | 24 s |
| Type Check | 37 s |
| Diff Check | 3 s |
| Unit Tests | 28 s |
| Uvicorn Smoke Test | 46 s |
| Lint | 27 s |
| Docker Build | 26 s |

По семи последним успешным PR validation runs median wall-clock равен **68 секундам**.

### Последний успешный development release

Run:

```text
Publish Backend Image
run id: 30331654020
source: e22eaa9ad9dd995e60836aa7eb41b5f01976252b
wall-clock: 392 seconds
raw runner time: 557 seconds / 9.28 minutes
estimated per-job rounded runner time: 15 minutes
```

Ключевые шаги:

| Step | Duration |
| --- | ---: |
| Validation Docker build | 22 s |
| QEMU setup | 7 s |
| Buildx build and ECR push | 233 s |
| Development deploy job | 44 s |
| SSM deployment wait | 33 s |

По пяти последним успешным development release runs median wall-clock равен
**382 секундам**.

### Подтвержденное дублирование

Полный development release выполняет:

- 11 активных jobs;
- 9 validation checkouts и еще 2 delivery checkouts;
- 6 одинаковых Python setup/install;
- 2 отдельных PostgreSQL/Redis service stacks;
- 2 Docker builds одного source SHA;
- `amd64` и `arm64` publish при отсутствии ARM deployment target.

Суммарное время двух Docker build steps в последнем run — **255 секунд**.

### Cache baseline

- `actions/setup-python` использует pip cache.
- BuildKit `cache-from`/`cache-to` не настроен.
- Измеримого BuildKit cache hit rate сейчас нет.
- QEMU используется только из-за `linux/arm64`.

## 4. AWS и ECR baseline

AWS account:

```text
account: 227755137079
deployment region: eu-central-1
```

Локальный AWS CLI default равен `us-east-1`, но deployable infrastructure и Terraform target
находятся в `eu-central-1`. Все CI/CD AWS-команды должны получать region явно.

ECR:

| Поле | Значение |
| --- | --- |
| Repository | `template-backend` |
| URI | `227755137079.dkr.ecr.eu-central-1.amazonaws.com/template-backend` |
| Visibility | Private |
| Tag mutability | `IMMUTABLE` |
| Encryption | `AES256` |
| Repository `scan_on_push` | `true` |
| Registry scan type | `BASIC` |
| Registry scan rules | Отсутствуют |

Несмотря на `scan_on_push`, `DescribeImageScanFindings` для текущего tagged OCI index возвращает
`ScanNotFoundException`. У tagged indexes и проверенных platform/attestation manifests отсутствуют
`imageScanStatus` и severity counts. Поэтому текущая настройка не создает deploy-blocking
security evidence.

## 5. EC2 и SSM baseline

Активные deployment targets:

| Environment | Instance | State | Architecture | Type | SSM |
| --- | --- | --- | --- | --- | --- |
| Development | `i-073f69c95a1fc82c1` | running | `x86_64` | `t3.micro` | Online |
| Production | `i-0a25f89590558cfef` | running | `x86_64` | `t3.micro` | Online |

Обе машины используют Amazon Linux 2023.

Также существует остановленный legacy instance
`i-0a6ee81b5623aad50` (`mobile-app-backend-production`). Он не входит в активные deployment
targets и не изменяется этой реструктуризацией.

Вывод для container target:

```text
required platform: linux/amd64
current linux/arm64 consumer: отсутствует
```

## 6. Текущие artifacts и rollback points

### Development

```text
source SHA:
e22eaa9ad9dd995e60836aa7eb41b5f01976252b

tag:
sha-e22eaa9ad9dd995e60836aa7eb41b5f01976252b

repository digest:
sha256:e7b214c8e9ed5517322f535655e95cd0ae5a5c16db3d016a4d47b2df1203f239

running platform image id:
sha256:daac2515286ae643f26557b4021e5116589386564a6687ed2ea774ff2afbf820
```

Rollback reference:

```text
227755137079.dkr.ecr.eu-central-1.amazonaws.com/template-backend@sha256:e7b214c8e9ed5517322f535655e95cd0ae5a5c16db3d016a4d47b2df1203f239
```

### Production

```text
source SHA:
c72a3d7df73561938df77c250d07d2a8c3493e2a

tag:
sha-c72a3d7df73561938df77c250d07d2a8c3493e2a

repository digest:
sha256:1bc77e8510f0f754f909a69385b5ab89efdcf087494fcfe59c6d516e4fe5ffc6

running platform image id:
sha256:20286e33338ae149f9c6308f73909333347f3e0131913ac16664f7415bdbcd50
```

Rollback reference:

```text
227755137079.dkr.ecr.eu-central-1.amazonaws.com/template-backend@sha256:1bc77e8510f0f754f909a69385b5ab89efdcf087494fcfe59c6d516e4fe5ffc6
```

Оба rollback artifacts существуют в immutable ECR и совпадают с images, запущенными на
соответствующих EC2. Rollback drill не выполнялся: он относится к Этапу 6.

## 7. Security baseline

Сейчас присутствует:

- explicit workflow-level `contents: read`;
- отдельный `id-token: write` для AWS OIDC jobs;
- private immutable ECR;
- отдельные ECR publish, SSM deploy и EC2 pull IAM responsibilities;
- tracked ignored-file check;
- Gitleaks.

Сейчас отсутствует или не enforced:

- branch protection и required checks;
- production approval;
- full-SHA pinning external Actions;
- `persist-credentials: false` у checkout;
- `actionlint`;
- `zizmor`;
- dependency audit;
- Terraform/Dockerfile/Compose security gate;
- authoritative image vulnerability findings;
- SBOM;
- explicit provenance policy;
- image signing и deploy-time verification;
- digest input у deploy workflow;
- stale-deploy guard;
- external health check;
- automatic rollback.

Владельцем security exceptions до появления `CODEOWNERS` назначается repository owner:

```text
@bakberdy
```

Исключения еще не создаются: registry появится на Этапе 4.

## 8. Этап 0: readiness

| Критерий | Результат |
| --- | --- |
| Required checks и protections записаны | Да: отсутствуют. |
| Duration и runner usage записаны | Да. |
| Cache behavior записан | Да: pip cache есть, BuildKit cache отсутствует. |
| Live ECR scan mode подтвержден | Да: `BASIC`, findings отсутствуют. |
| Active EC2 architecture подтверждена | Да: только `x86_64`. |
| Development rollback point записан | Да. |
| Production rollback point записан | Да. |
| Security exception owner определен | Да: `@bakberdy`. |

Этап 0 завершен. Следующий допустимый шаг — только Этап 1: workflow contracts.
