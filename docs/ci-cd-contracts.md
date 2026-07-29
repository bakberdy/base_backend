# CI/CD workflow contracts

Статус: **утверждено для реализации**.

Дата: 28 июля 2026 года.

Основание: `docs/ci-cd-restructuring-plan.md`, Этап 1.

Этот документ фиксирует границы, inputs, outputs, permissions и стабильные check names до
изменения workflow implementation.

## 1. Целевое дерево

```text
.github/workflows/
  delivery.yml
  project-validation.yml
  repository-security.yml
  container-image.yml
  deploy-app.yml
  security-monitoring.yml
```

Переход:

- `publish-image.yml` остается активным до завершения development proof;
- его orchestration переходит в `delivery.yml`;
- его build/publish implementation переходит в `container-image.yml`;
- файл удаляется только на Этапе 6 после успешного rollback drill;
- current-state документация обновляется только на Этапе 7.

## 2. Trigger ownership

`delivery.yml` напрямую реагирует только на:

- `pull_request` в `main`;
- `merge_group`.

`publish-image.yml` отдельно владеет release tag triggers:

- `vX.Y.Z-dev.N` для development;
- `vX.Y.Z` для production.

- `project-validation.yml`, `repository-security.yml` и `container-image.yml` используют
  `workflow_call`;
- `deploy-app.yml` сохраняет `workflow_dispatch` для rollback;
- `security-monitoring.yml` имеет `schedule` и read-only `workflow_dispatch`.

Обе release-схемы принимают только tag, указывающий на текущий HEAD защищенной ветки `main`.

## 3. Stable required check

Workflow:

```text
Delivery
```

Финальный job:

```text
Delivery Gate
```

Стабильный required-check context:

```text
Delivery / Delivery Gate
```

Только этот агрегирующий context добавляется в branch protection. Внутренние job names могут
эволюционировать без изменения repository rules.

`Delivery Gate`:

- выполняется с `if: always()`;
- получает результаты всех обязательных reusable jobs;
- считает `failure`, `cancelled` и неожиданный `skipped` неуспехом;
- допускает `skipped` только для branch-specific jobs, которые не относятся к текущему event;
- не содержит application, Docker, security или AWS implementation.

Required check включен для защищенной ветки `main` через Terraform.

## 4. `project-validation.yml`

Назначение: application correctness.

Trigger:

```text
workflow_call
```

Переходный direct PR trigger удаляется только после включения `delivery.yml`.

### Inputs

| Input | Type | Required | Validation |
| --- | --- | --- | --- |
| `source_sha` | string | yes | Полный 40-character Git SHA. |

Checkout всегда выполняется по `source_sha`.

### Jobs

| Job id | Stable name | Ответственность |
| --- | --- | --- |
| `quality` | Application Quality | diff, Ruff format/lint, mypy в одном Python environment |
| `unit` | Unit Tests | unit tests |
| `runtime` | Runtime Tests | integration tests и Uvicorn smoke на одном PostgreSQL/Redis stack |
| `application-gate` | Application Gate | агрегирует application jobs |

### Outputs

| Output | Value |
| --- | --- |
| `status` | `success` только после `application-gate` |

### Permissions

```text
contents: read
```

Запрещены:

- `id-token: write`;
- AWS credentials;
- Docker build/push;
- repository security implementation;
- deploy secrets.

## 5. `repository-security.yml`

Назначение: repository inputs и CI supply chain.

Trigger:

```text
workflow_call
```

### Inputs

| Input | Type | Required | Validation |
| --- | --- | --- | --- |
| `source_sha` | string | yes | Полный 40-character Git SHA. |
| `upload_sarif` | boolean | yes | `true` только в trusted repository context. |

### Jobs

| Job id | Stable name | Ответственность |
| --- | --- | --- |
| `secrets` | Secret Scan | tracked ignored files и Gitleaks |
| `dependencies` | Dependency Audit | Python dependency vulnerability audit |
| `workflows` | Workflow Policy | actionlint, zizmor, full-SHA policy |
| `configuration` | Configuration Security | Terraform, Dockerfile и Compose config |
| `repository-security-gate` | Repository Security Gate | агрегирует security jobs |

### Outputs

| Output | Value |
| --- | --- |
| `status` | `success` только после `repository-security-gate` |
| `report_id` | GitHub run-scoped report identifier |

### Permissions

Default:

```text
contents: read
```

Только SARIF upload job:

```text
security-events: write
```

Запрещены:

- AWS deploy/publish roles;
- application image build;
- ECR push;
- SSM;
- `secrets: inherit`.

## 6. `container-image.yml`

Назначение: единственный owner application image.

Trigger:

```text
workflow_call
```

### Inputs

| Input | Type | Required | Validation |
| --- | --- | --- | --- |
| `mode` | string | yes | Только `pr` или `release`. |
| `source_sha` | string | yes | Полный 40-character Git SHA. |
| `platform` | string | yes | На первом rollout только `linux/amd64`. |
| `repository_uri` | string | release only | Полный private ECR repository URI без tag/digest. |

### PR mode

Permissions:

```text
contents: read
```

Поведение:

- build один раз;
- `push: false`;
- AWS credentials отсутствуют;
- container health smoke выполняется на том же artifact;
- release evidence не создается.

### Release mode

Permissions caller job:

```text
contents: read
id-token: write
```

Поведение:

- assume только ECR publisher role через OIDC;
- reuse существующего artifact разрешен только по exact `source_sha`;
- новый artifact строится и push выполняется ровно один раз;
- digest получается из BuildKit/ECR, не вычисляется из tag;
- SBOM и provenance прикрепляются к тому же OCI artifact;
- authoritative scan и signing policy обязательны также для reused artifact.

### Outputs

| Output | Format |
| --- | --- |
| `source_sha` | Полный Git SHA |
| `image_digest` | `sha256:<64 lowercase hex>` |
| `image_reference` | `<repository_uri>@<image_digest>` |
| `security_evidence_id` | `<run_id>:<run_attempt>:sha256:<evidence-hash>` |
| `status` | `success` только после container/security gate |

`security_evidence_id` указывает на сохраненный artifact конкретного run и содержит hash
канонического evidence JSON. Deploy скачивает artifact по `run_id`, проверяет content hash,
соответствие source/image, SBOM/provenance и signature, а затем повторно проверяет digest и
managed-signing status в ECR.

### Authoritative image security

Утвержден основной вариант:

```text
Trivy
```

Роли:

- Trivy — единственный blocking vulnerability source;
- BuildKit — SBOM и provenance;
- ECR managed signing / AWS Signer — единственная image signature;
- ECR managed signing status — deploy-time signature verification.

Cosign и второй image vulnerability gate не добавляются параллельно. ECR basic `scan_on_push`
остается informational.

## 7. `deploy-app.yml`

Назначение: deploy или rollback уже approved digest.

Triggers:

```text
workflow_call
workflow_dispatch
```

### Inputs

| Input | Type | Required | Validation |
| --- | --- | --- | --- |
| `target_environment` | string | yes | Только `development` или `production`. |
| `source_sha` | string | yes | Полный 40-character Git SHA. |
| `image_reference` | string | yes | Private ECR URI с `@sha256`, tag запрещен. |
| `security_evidence_id` | string | yes | Run traceability identifier. |

Manual rollback получает те же inputs. Для rollback `source_sha` описывает source выбранного
artifact, а не HEAD вызывающего workflow.

### Permissions

Caller job:

```text
actions: read
contents: read
id-token: write
```

Deploy role передается явно. `secrets: inherit` запрещен.

### Preconditions

До SSM deploy workflow обязан:

1. Проверить input formats.
2. Убедиться, что digest существует в разрешенном ECR repository.
3. Проверить security evidence от authoritative Trivy scan.
4. Проверить signature.
5. Для automatic branch deploy выполнить stale-deploy guard.
6. Сохранить текущий running digest как rollback target.

### Outputs

| Output | Value |
| --- | --- |
| `deployed_digest` | Digest после успешного health check |
| `previous_digest` | Digest до rollout |
| `deployment_status` | `success` или `rolled_back` |
| `ssm_command_id` | Command traceability |

## 8. `security-monitoring.yml`

Назначение: read-only continuous monitoring.

Triggers:

```text
schedule
workflow_dispatch
```

Inputs manual mode:

| Input | Type | Required |
| --- | --- | --- |
| `target_environment` | string | no |
| `image_reference` | string | no |

Permissions:

- read-only ECR role через OIDC;
- `security-events: write` или `issues: write` только для выбранного alert output;
- SSM deploy, ECR push и infrastructure mutation запрещены.

Outputs:

- deployed digest inventory;
- current findings summary;
- expired exception summary;
- runtime dependency image summary.

## 9. `delivery.yml`

Назначение: orchestration only.

### Event routing

| Event | Required jobs | Deploy |
| --- | --- | --- |
| Pull request в `main` | validation, repository security, container PR | no |
| Tag `vX.Y.Z-dev.N` на `main` HEAD | validation, repository security, container release | development |
| Tag `vX.Y.Z` на `main` HEAD | validation, repository security, reuse/build release artifact | production |

### Permission boundary

Workflow default:

```text
contents: read
```

Only caller jobs:

- container release получает `id-token: write`;
- deploy получает `id-token: write`;
- SARIF caller получает `security-events: write`.

Reusable workflow не может повысить permissions caller job.

### Dependency graph

```text
application ─┐
security ────┼─> container release -> deploy -> delivery gate
             |
PR container ┘                         -> delivery gate
```

PR container и release container — взаимоисключающие jobs.

## 10. Failure semantics

- Scanner timeout/error — failure.
- Missing digest, scan, SBOM, provenance или signature — failure.
- Reused image без evidence — failure.
- Deploy health failure — rollback, затем failed/rolled-back result по policy Этапа 5.
- Неожиданный skipped required job — failure.
- Manual rollback не вызывает build/publish.
- Production не может получить permissions шире development без отдельного contract change.

## 11. Transition safety

Stage 2 и Stage 3 имеют одну обязательную safety boundary:

1. Новый security caller добавляется до удаления Gitleaks из старого validation flow.
2. Новый container replacement добавляется до удаления Docker build из validation.
3. Старый и новый owners одной работы не остаются одновременно активными после переключения
   caller.
4. `publish-image.yml` не удаляется и production routing не переключается до Этапа 6.
5. Current development и production rollback references берутся из
   `docs/ci-cd-baseline.md`.

Это предотвращает как пропуск gate, так и длительное двойное выполнение.

## 12. Этап 1: readiness

| Критерий | Результат |
| --- | --- |
| Целевое дерево утверждено | Да. |
| Inputs/outputs утверждены | Да. |
| Permissions утверждены | Да. |
| Stable required check утвержден | `Delivery / Delivery Gate`. |
| Authoritative scanner выбран | Trivy. |
| Digest format утвержден | `repository@sha256:<64 hex>`. |
| Security evidence определен | Run traceability + live service verification. |
| Старые workflows сохраняются до development proof | Да. |

Этап 1 завершен. Следующий допустимый шаг — Этап 2 с transition safety из раздела 11.
