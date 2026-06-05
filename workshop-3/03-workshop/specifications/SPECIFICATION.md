# Specification Template for KYC API

> Ingest the information from this file, implement the Low-Level Tasks, and generate the code that will satisfy the High and Mid-Level Objectives.

## High-Level Objective
- Build a comprehensive KYC (Know Your Customer) API that validates customer information, verifies documents, and performs compliance checks for banking applications

## Mid-Level Objectives
- Create a complete OpenAPI 3.1 specification for the KYC API
- Implement FastAPI endpoints with proper validation and error handling
- Build document verification capabilities with mock services
- Add compliance checking for sanctions lists and AML requirements
- Implement comprehensive contract testing to validate API against specification
- Include proper authentication, authorization, and audit logging
- Deploy to Azure following phased rollout (phases 0–5) with phase/env visible in code, tags, IaC, and CI/CD
- Satisfy prod go-live security checklist before phase 4 production traffic
- Achieve OWASP ASVS Level 2 compliance across auth, session management, input validation, cryptography, and API security domains
- Implement tamper-evident audit logging with append-only storage and SHA-256 hash-chain integrity for banking regulatory compliance
- Apply PII tokenization for document storage and mTLS (phase 3+) for all service-to-service communication

## Implementation Notes
- Use OpenAPI 3.1 as the source of truth for API design
- Implement with FastAPI framework for automatic documentation
- Use Pydantic models for request/response validation
- Include comprehensive error handling with proper HTTP status codes
- Add authentication using JWT tokens
- Implement audit logging for all API operations
- Follow banking industry standards for data validation
- Include data privacy compliance (GDPR, CCPA)
- Use Decimal for all monetary calculations
- Add comprehensive testing with contract validation
- Follow Python 3.12+ with type hints for better code clarity
- Follow PEP 8 coding standards
- Include logging for audit trails (important for banking)
- Implement proper exception handling for API operations
- Support international compliance requirements
- Include data privacy compliance for PII handling
- Deploy to Azure with phased rollout; represent phase and environment explicitly in code, IaC, and CI/CD (see Cloud Deployment sections below)
- Expose `GET /health` and `GET /ready` for load balancer and orchestrator probes
- Use environment-based configuration (`pydantic-settings`); never hardcode secrets (Key Vault in cloud)

## Security Architecture

### OWASP API Security Top 10 (2023) — Endpoint Mapping

All 10 API risks must be explicitly mitigated before phase 4. Mapping must be reviewed and signed off as part of the prod go-live checklist.

| OWASP API Risk | Affected KYC Endpoints | Required Mitigation |
|---|---|---|
| **API1: Broken Object Level Authorization (BOLA)** | `GET /customers/{id}`, `GET /customers/{id}/compliance`, `GET /customers/{id}/documents` | Per-request ownership check: JWT `sub` must equal `customer.owner_id` or role must be `admin`/`kyc_officer`. Return `403` regardless of existence to prevent enumeration oracle. |
| **API2: Broken Authentication** | All endpoints | RS256 only (HS256 rejected at validation); 15-min access token TTL; refresh token rotation with family tracking; `jti` revocation blacklist in Redis; `alg:none` attack explicitly rejected. |
| **API3: Broken Object Property Level Authorization** | `POST /customers`, `PATCH /customers/{id}` | Pydantic `ConfigDict(extra='forbid')` on all request models; no `**kwargs` passthrough to ORM; explicit field allowlists per role. |
| **API4: Unrestricted Resource Consumption** | `POST /customers/{id}/documents` | File size cap 10 MB; MIME-type allowlist (JPEG, PNG, PDF); per-user Redis rate limiting; multipart body size limit in FastAPI settings. |
| **API5: Broken Function Level Authorization** | `POST /customers/{id}/verify`, `DELETE /customers/{id}` | Role matrix enforced via decorators in `src/auth.py`; `admin`-only operations explicitly annotated; tested in CI with role boundary tests. |
| **API6: Unrestricted Access to Sensitive Business Flows** | `POST /customers/{id}/verify` | Workflow state machine: cannot re-verify an already-`APPROVED` or `REJECTED` customer without explicit `admin` override action. State transition table enforced at service layer. |
| **API7: Server-Side Request Forgery (SSRF)** | Any endpoint accepting URLs or callbacks | Allowlist of accepted external service domains; block all RFC-1918 address ranges (10.x, 172.16.x, 192.168.x); `localhost` and `169.254.x` (metadata endpoint) blocked. |
| **API8: Security Misconfiguration** | All endpoints | Security headers middleware active (HSTS, CSP, X-Frame-Options, `no-store`); `/docs` and `/redoc` disabled in prod; Azure WAF OWASP 3.2 rules enabled; debug mode off in all non-dev environments. |
| **API9: Improper Inventory Management** | `GET /health`, `GET /ready` | Only documented endpoints exposed; all routes discoverable via APIM. No shadow endpoints or versioned routes outside API Management policy. OpenAPI spec is canonical inventory. |
| **API10: Unsafe Consumption of APIs** | Sanctions/PEP external list calls, OCR service calls | Timeout (5 s) + retry with exponential backoff (max 3 attempts); strict response schema validation before processing any external payload; circuit breaker for downstream failures. |

### Input Sanitization and Injection Prevention

- **SQL injection**: All database access through SQLAlchemy ORM with parameterized queries. No raw `text()` with user-supplied strings. Enforced via semgrep rule in CI. `sqlmap` scan run against test environment in Phase 3+.
- **Command injection**: No `subprocess` calls with user-supplied strings anywhere in `src/`. Document OCR exclusively through Azure Form Recognizer SDK. Enforced via bandit rule B602/B603.
- **Path traversal**: Blob object names are always `uuid4()` — never user-supplied filenames. Any local filesystem access uses `pathlib.Path(...).resolve()` and validates the resolved path is under an allowed prefix before read.
- **Template injection**: No Jinja2 rendering of user input. Structured log messages use `%s` positional formatting or `structlog` context binding — never f-strings with user-controlled data.
- **Pydantic enforcement**: All incoming JSON models use `ConfigDict(extra='forbid')`. Custom field validators enforce E.164 phone format, ISO 8601 date of birth (must be ≥ 18 years old and ≤ 150 years ago), RFC-5322 email via `email-validator` library, and country codes against ISO 3166-1 alpha-2 allowlist.

### JWT Hardening

- **Algorithm**: RS256 only. Private signing key stored in Key Vault; public key loaded at startup. Any token with `alg != RS256` or `alg == none` is rejected at middleware level before business logic.
- **Access token TTL**: 15 minutes (`exp` claim). Refresh token TTL: 24 hours in `dev`/`test`; 8 hours in `staging`/`prod`.
- **Refresh token rotation with family tracking**: On each refresh, issue new refresh token and invalidate the old one. Track refresh token families in Redis. Detecting reuse of an already-rotated token within a family triggers revocation of the entire family (defense against stolen token attacks).
- **Token revocation (blacklist)**: On logout, privilege change, or password reset, write the `jti` claim to a Redis SET with TTL matching the remaining token lifetime. Every request validates the `jti` is not in the blacklist before allowing access.
- **Required claims**: `iss`, `aud`, `sub` (user UUID), `roles` (list), `jti` (UUID4), `exp`, `iat`. Tokens missing any required claim are rejected with `401`.
- **Phase 3+ Entra ID**: When `APP_ENV in ("staging", "prod")`, validate `iss` against the Azure Entra tenant endpoint. Workshop-issued JWT (`APP_ENV in ("dev", "test")`) blocked in staging/prod via feature flag `kyc.entra-auth-only`.
- **JWKS endpoint**: `GET /.well-known/jwks.json` serves the current public key(s). During key rotation, both old and new public keys are present in JWKS for a 7-day overlap window to allow in-flight tokens to drain.

### Secrets Rotation Policy and Zero-Trust

- **PostgreSQL password**: 90-day automatic rotation via Key Vault rotation policy. Application fetches secret at startup — never from a hardcoded connection string or environment variable string. Dual-credential pattern enables zero-downtime rotation: Key Vault holds both old and new credentials; app retries once on auth failure before alerting.
- **JWT signing key pair**: 365-day rotation. New RSA key pair generated in Key Vault; public key published immediately to JWKS endpoint. 7-day overlap window where both keys are valid for token verification.
- **Blob SAS tokens**: Application-generated SAS tokens with 1-hour TTL for document access. Never stored in database or logs; regenerated per request on demand.
- **Zero-trust network (Phase 3+)**: All service-to-service calls within private VNet. PostgreSQL, Redis, Key Vault, and Blob Storage accessible only via private endpoints. App never connects to any backend over public internet in `staging`/`prod`.
- **Workload identity**: Managed Identity assigned to AKS pod identity (via Azure Workload Identity) or App Service managed identity from Phase 1+. No client secret strings in environment variables or app settings from Phase 1+.

### Audit Trail Integrity (Tamper-Evident Logging)

**Required fields on every audit log record:**

| Field | Description |
|---|---|
| `timestamp` | UTC ISO-8601 with millisecond precision |
| `trace_id` | From request `X-Request-ID` header (UUID4); generated by API if absent |
| `actor_id` | JWT `sub` claim (user UUID); `SYSTEM` for background jobs |
| `actor_role` | JWT `roles` value at time of action |
| `action` | Dot-namespaced action string (e.g. `customer.verify.start`) |
| `resource_type` | e.g. `customer`, `document`, `compliance_check` |
| `resource_id` | UUID of the affected resource |
| `outcome` | `success` or `failure` |
| `ip_address` | Extracted from `X-Forwarded-For` after WAF strips untrusted values |
| `pii_accessed` | Boolean: true if the operation read or wrote PII fields |
| `phase` | `DEPLOY_PHASE` value at request time |
| `env` | `APP_ENV` value |

**What must NOT be logged**: Raw PII values (name, date of birth, SSN/tax ID, document content, phone number). Use tokenized reference IDs in the audit record. PII redaction middleware (see `src/middleware/pii_redaction.py`) intercepts all log emissions before they leave the application.

**Tamper-evident mechanism**:
- Append-only `audit_log` PostgreSQL table: application role has `INSERT` only. `UPDATE` and `DELETE` are explicitly denied for the app database role. A separate `audit_reader` role (for compliance queries) has `SELECT` only.
- Streamed to Azure Log Analytics **immutable** table with 7-year retention and 1-year lock period (regulatory hold).
- `prev_hash` column: SHA-256 hash of the previous record's composite fields (`timestamp + trace_id + actor_id + action + resource_id + outcome`). Background job validates hash chain continuity on a 6-hour schedule; alert fires on any hash mismatch.

### Data-at-Rest Encryption

- **PostgreSQL**: Azure Flexible Server SSE (AES-256) by default. Phase 4+: Customer-Managed Key (CMK) via Key Vault (`BYOK`) required for data sovereignty compliance.
- **Blob Storage**: SSE with Microsoft-managed keys (Phase 1–3). Phase 4+: SSE with CMK in Key Vault. Soft delete enabled (30-day retention). Blob versioning enabled on the `compliance-documents` container.
- **Application-layer column encryption (Phase 3+)**: `customer.tax_id` and `customer.date_of_birth` encrypted at application layer using `cryptography.Fernet` with an encryption key fetched from Key Vault before writing to PostgreSQL. Provides defense-in-depth beyond database-level TDE. Encrypted columns stored as base64-encoded ciphertext.
- **PII tokenization**: Document metadata extracted by OCR (name, DOB, address) stored as tokens in `pii_vault` table — never as raw values in `document` or `customer` tables. Token format: `pii:<uuid4>`. Actual values stored as Key Vault secrets keyed by token ID. Only users with `pii.read` scope can resolve tokens.

### mTLS for Service-to-Service Communication (Phase 3+)

- Enabled when `DEPLOY_PHASE >= 3` and `APP_ENV in ("staging", "prod")`.
- **AKS deployment**: Istio service mesh (or Azure Service Mesh) with `PeerAuthentication` policy set to `STRICT` across all namespaces — no plaintext inter-pod traffic permitted.
- **Certificate management**: Certificates issued by cert-manager with Azure Private CA. 90-day auto-rotation; cert-manager handles renewal automatically.
- **Feature flag**: `kyc.mtls-required` — when `false` (dev/test), falls back to TLS-only. When `true`, strict mTLS enforced and plaintext connections rejected.

### Dependency Vulnerability Scanning

- **Dependabot**: Configured for `pip` ecosystem in `.github/dependabot.yml`. Weekly scan cadence. Auto-PRs for patch-level updates. GitHub security advisory alerts enabled for HIGH/CRITICAL. All advisory PRs reviewed within 5 business days.
- **pip-audit** (Phase 1+, every PR): `pip-audit --strict --output json` — hard gate, exits `1` on any vulnerability. Output saved as CI artifact for audit trail.
- **Trivy** (Phase 2+, every build): Container image scan (`trivy image --exit-code 1 --severity CRITICAL,HIGH`) and filesystem scan (`trivy fs . --scanners vuln,secret,config`). SARIF output uploaded to GitHub Advanced Security.
- **SBOM generation**: `syft` generates CycloneDX SBOM JSON on every release tag. SBOM attached to GitHub Release as artifact. Required for banking supply chain compliance.
- **Known-acceptable exceptions**: documented in `.trivy-ignore` and `pip-audit-ignore.toml` with mandatory justification comment and annual review date.

### Security Headers Middleware

New file: `src/middleware/security_headers.py` — Starlette `BaseHTTPMiddleware` applied to all responses:

```
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
Content-Security-Policy: default-src 'none'; frame-ancestors 'none'
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 0
Referrer-Policy: no-referrer
Permissions-Policy: geolocation=(), microphone=(), camera=()
Cache-Control: no-store
```

- Applied to all responses containing data. Omitted from `GET /health` and `GET /ready` probe endpoints.
- `Content-Security-Policy` header is suppressed in `dev`/`test` environments to allow Swagger UI to function (controlled by feature flag `kyc.strict-security-headers`).
- Middleware registered before route handlers in `src/api.py` app factory.

### OWASP ASVS Level 2 Compliance Target

Target ASVS 4.0 Level 2 as the minimum compliance baseline before Phase 4 production traffic. Formal compliance checklist maintained at `docs/asvs-compliance-checklist.md`, updated and signed off per phase.

| ASVS Chapter | Key Requirements | Implementation |
|---|---|---|
| **V2: Authentication** | No credential stuffing, MFA-ready, secure account recovery | `src/auth.py`, Phase 3+ Entra ID |
| **V3: Session Management** | JWT revocation, short TTL, token binding guidance for clients | `src/auth.py`, Redis `jti` blacklist |
| **V5: Input Validation** | All inputs validated; unexpected parameters rejected | Pydantic `extra='forbid'` on all models |
| **V6: Cryptography** | AES-256, RSA-2048+, no weak hash functions (MD5/SHA1) | Key Vault, TDE, `cryptography.Fernet` |
| **V8: Data Protection** | PII tokenization, at-rest encryption, no PII in logs | `src/middleware/`, `pii_vault`, column encryption |
| **V9: Communication** | TLS 1.2+, certificate validation enforced, mTLS Phase 3+ | Azure WAF, Istio `PeerAuthentication STRICT` |
| **V10: Malicious Code** | Dependency scanning, SBOM, no backdoors or debug code in prod | CI pipeline, Trivy, syft |
| **V13: API** | OWASP API Top 10 mitigations, rate limiting, no verbose errors | `src/api.py`, Redis, APIM, error handlers |

---

## Cloud Deployment (Azure)

### Compute options (high scaling)

Choose compute based on expected RPS, burst patterns, and team Kubernetes maturity. **Default recommendation for high scale: Azure Kubernetes Service (AKS).**

| Option | Best for | High-scale notes |
|--------|----------|------------------|
| **Azure Kubernetes Service (AKS)** | Production banking APIs, 10k+ RPS, custom autoscaling | Cluster autoscaler + **KEDA** (scale on queue/APIM metrics); multi-zone node pools; **NGINX Ingress** or **Application Gateway Ingress Controller (AGIC)**; pod autoscaling (HPA/VPA); blue/green via separate deployments or **Argo Rollouts** |
| **Azure App Service (Linux, Premium v3 P1v3+)** | Moderate scale without K8s ops | Autoscale on CPU/memory/HTTP queue; deployment slots for blue/green; ceiling ~hundreds of instances; simpler than AKS |
| **Azure VM Scale Sets + Load Balancer** | Legacy lift-and-shift, full OS control | Manual or custom autoscale; highest ops burden; use only if containers/K8s are not an option |
| **Azure Container Apps** | Mid-scale, minimal ops | Good to ~few thousand RPS with consumption plan; less control than AKS for fine-grained scheduling and service mesh |
| **Azure Functions (HTTP)** | Event/async side paths only | Not primary host for full FastAPI monolith; use for async document/OCR pipelines triggered from Blob/Event Grid |

**Supporting Azure services (all compute options):** Azure Container Registry (ACR), API Management, Front Door + WAF, PostgreSQL Flexible Server, Blob Storage, Azure Cache for Redis, Key Vault, Microsoft Entra ID, Application Insights + Log Analytics.

### Phased rollout

| Phase | Scope | Indicative duration |
|-------|--------|---------------------|
| **0** | Implement API per spec; local Docker | — |
| **1** | **dev:** ACR + compute + PostgreSQL + Blob + Key Vault (minimal SKUs, permissive network) | 1–2 days |
| **2** | **test:** APIM OpenAPI import, CI pipeline, schemathesis gate on deploy | 2–3 days |
| **3** | **staging:** VNet, private endpoints, Entra ID, Application Insights, autoscale policies | 3–5 days |
| **4** | **prod:** Front Door, WAF, HA database, alerts, Azure Policy, runbooks | 5–10 days |
| **5** | **hardening:** penetration test, DR drill, Purview/classification (ongoing) | Ongoing |

Each phase must be **deployable independently**: merging phase *N* infrastructure does not require re-running phase *N−1* manually if state is in Git/IaC.

### Phased rollout in code (how phases appear in the repository)

Phases must be traceable in Git, CI/CD, and runtime without tribal knowledge. Use a **layered convention** (all layers aligned to the same phase number):

#### 1. Git tags (release boundaries)

Annotate phase completions and environment promotions:

```
deploy/phase-1-dev
deploy/phase-2-test
deploy/phase-3-staging
deploy/phase-4-prod
v1.0.0-phase4-prod
```

- CI deploy workflows trigger on tag pattern `deploy/phase-*` or on merge to `release/phase-N` branches.
- `CHANGELOG.md` entries reference phase tags.

#### 2. Container image tags (ACR)

Single image build; promote by tag (immutable digest in prod):

```
kyc-api:1.2.3                    # semver from app
kyc-api:1.2.3-phase2-test        # phase + env (CI adds on promote)
kyc-api:sha-abc1234              # traceability
```

Prod deploys **only** digest-pinned tags (`@sha256:...`), not floating `latest`.

#### 3. Environment and phase in application config

```python
# src/config.py (pydantic-settings)
APP_ENV: Literal["dev", "test", "staging", "prod"]
DEPLOY_PHASE: Literal[0, 1, 2, 3, 4, 5]  # set by pipeline / Helm values
```

- `GET /health` returns `env`, `phase`, `version` (from `importlib.metadata` or `GIT_SHA` build arg).
- Phase **4+:** disable FastAPI `/docs` and `/redoc` when `APP_ENV == "prod"`.
- Phase **3+:** require Entra-issued tokens (keep workshop JWT only when `APP_ENV in ("dev", "test")`).

#### 4. IaC parameters per phase (`infra/`)

```
infra/parameters/
  phase-1-dev.bicepparam      # public endpoints OK, smallest SKUs
  phase-2-test.bicepparam     # + APIM, diagnostic settings
  phase-3-staging.bicepparam  # + VNet, private endpoints, autoscale
  phase-4-prod.bicepparam     # + Front Door, WAF, HA PostgreSQL
```

Pipeline step: `az deployment group create -f infra/main.bicep -p infra/parameters/phase-${PHASE}-${ENV}.bicepparam`

Optional **Bicep module feature flags**: `param enableFrontDoor bool = false` flipped per parameter file.

#### 5. CI/CD GitHub Environments (or Azure DevOps stages)

| GitHub Environment | Maps to | Protection |
|--------------------|---------|------------|
| `dev` | Phase 1 | None |
| `test` | Phase 2 | Required reviewers optional |
| `staging` | Phase 3 | Required reviewers |
| `production` | Phase 4 | Required reviewers + wait timer |

Workflow `deploy.yml` inputs: `phase`, `environment`. Job `environment: ${{ inputs.environment }}` gates secrets and approvals.

#### 6. Kubernetes labels (if using AKS)

```yaml
metadata:
  labels:
    app.kubernetes.io/name: kyc-api
    app.kubernetes.io/version: "1.2.3"
    deployment.phase: "3"          # matches DEPLOY_PHASE
    environment: staging
```

Helm `values-staging.yaml` vs `values-prod.yaml` carry phase-specific replica counts and resource limits.

#### 7. Feature flags (phase-gated behavior without redeploy)

**Azure App Configuration** feature flags (or simple env flags in early phases):

| Flag key | Enabled from phase |
|----------|-------------------|
| `kyc.use-blob-storage` | 1 (dev real Blob; local may mock) |
| `kyc.entra-auth-only` | 3 |
| `kyc.disable-openapi-ui` | 4 |
| `kyc.strict-pii-log-redaction` | 2 |

Application reads flags at startup; audit log records flag snapshot on each deploy.

#### 8. OpenAPI `info.version` and operation tags

In `specs/kyc-api.yaml`:

```yaml
info:
  version: 1.2.3
  x-deployment-phase: 2
```

Group operations with tags: `Customers`, `Documents`, `Compliance`, `Operations` (health). APIM revision per phase import.

#### Suggested repo layout for deployment artifacts

```
infra/
  main.bicep
  modules/...
  parameters/phase-{1-4}-{env}.bicepparam
.github/workflows/
  build.yml
  deploy.yml          # inputs: phase, environment
src/config.py         # APP_ENV, DEPLOY_PHASE, feature flag client
Dockerfile
CHANGELOG.md          # phase completion notes
```

### Security checklist (prod go-live)

All items required before **phase 4 (prod)** traffic. CI includes a manual gate (`security-checklist-gate` job with GitHub Environment `production`) that requires reviewer approval and verifies machine-checkable items automatically.

#### Authentication & Authorization

- [ ] JWT uses RS256; private signing key in Key Vault; HS256 and `alg:none` rejected at middleware
- [ ] Access token TTL ≤ 15 minutes; refresh token rotation active with family-based revocation
- [ ] Token revocation `jti` blacklist (Redis SET) verified working under concurrent load
- [ ] RBAC roles (`admin`, `kyc_officer`, `readonly`) all tested with privilege escalation and IDOR test suite in CI
- [ ] Phase 3+: Entra ID tokens only; workshop JWT issuer blocked in `staging`/`prod` (feature flag `kyc.entra-auth-only` = true)
- [ ] IDOR protection verified: `GET /customers/{id}` returns `403` for non-owner non-admin; no `404` vs `403` enumeration oracle

#### Network & Infrastructure

- [ ] All PII backends (PostgreSQL, Blob, Key Vault, Redis) use private endpoints; no public access
- [ ] Managed identity only for app → Key Vault, PostgreSQL, Blob; no connection strings in app settings or repo
- [ ] Azure Front Door (or Application Gateway) + WAF with OWASP 3.2 rules enabled and in Prevention mode
- [ ] TLS 1.2+ enforced end-to-end; TLS 1.0/1.1 explicitly blocked; verified with `testssl.sh` in Phase 3+ CI gate
- [ ] Phase 3+: mTLS between all services verified (`PeerAuthentication STRICT`); no plaintext inter-service traffic

#### Data Protection

- [ ] PostgreSQL Customer-Managed Key (CMK) enabled via Key Vault (`BYOK`); key rotation tested
- [ ] Blob Storage SSE with CMK enabled; soft delete (30 days) and versioning active on compliance container
- [ ] PII tokenization active: no raw PII values in `document` table, `customer` table (except encrypted columns), or logs
- [ ] Application-layer column encryption (`tax_id`, `date_of_birth`) active in `staging`/`prod`; encrypt/decrypt round-trip tested
- [ ] PII redaction middleware verified: sample trace review in Application Insights confirms no raw PII in any log record

#### API Security

- [ ] Security headers middleware active: HSTS, CSP, `X-Frame-Options: DENY`, `X-Content-Type-Options`, `Cache-Control: no-store` — verified on all data-returning endpoints
- [ ] `/docs` and `/redoc` disabled in prod (feature flag `kyc.disable-openapi-ui = true`); verified returning `404`
- [ ] Rate limiting active at APIM and application layer (Redis); burst test confirms `429` returned at threshold; `Retry-After` header present
- [ ] OWASP API Security Top 10 (2023) mapping reviewed and all 10 risks have verified mitigations (see Security Architecture section)

#### Audit & Compliance

- [ ] Append-only `audit_log` table verified: `UPDATE` and `DELETE` blocked for app database role; `INSERT` confirmed working
- [ ] Audit log hash chain integrity validation job running on schedule; no hash mismatches in prior 24-hour window
- [ ] Log Analytics immutable table configured with 7-year retention and 1-year lock period; write test confirmed
- [ ] OWASP ASVS Level 2 checklist (`docs/asvs-compliance-checklist.md`) reviewed, all items checked, and signed off by security officer

#### Supply Chain & Secrets

- [ ] Dependabot active; no open HIGH/CRITICAL GitHub security advisories unreviewed
- [ ] Trivy image scan for deployed image: zero CRITICAL CVEs confirmed in CI artifact
- [ ] SBOM (CycloneDX JSON) generated and attached to release artifact via `syft`
- [ ] `truffleHog --only-verified` scan: zero verified secrets detected in full Git history

#### Operations

- [ ] API Management JWT validation aligned with Microsoft Entra ID (or documented issuer for service accounts)
- [ ] PostgreSQL and Blob backup/restore tested successfully; RTO and RPO targets documented in `docs/runbooks/`
- [ ] Diagnostic settings enabled on all Azure resources → Log Analytics workspace
- [ ] Incident runbook and alert routing configured (`docs/runbooks/`); tested with a simulated P1 alert to on-call channel
- [ ] Azure Policy assignments verified for subscription: encryption at rest, diagnostic settings, soft delete, CMK requirements

## Incident Response

### Alert Triggers

Automatic alerts fire to the configured on-call channel (`#kyc-security-alerts` in Teams/PagerDuty) when the following thresholds are breached:

| Trigger | Threshold | Severity |
|---|---|---|
| Authentication failures | > 50 failed auth attempts in 5 minutes from a single IP | HIGH |
| JWT validation failures | > 100 JWT rejections in 1 minute across all IPs | HIGH |
| Audit log hash chain mismatch | Any mismatch detected by the 6-hour integrity job | CRITICAL |
| Rate limit threshold saturated | > 80% of per-user limit sustained for 10 minutes | MEDIUM |
| Trivy scan new CRITICAL CVE | Any new CRITICAL CVE detected on `main` branch image | HIGH |
| PII pattern detected in logs | Regex match for SSN, card number, or raw DOB in Log Analytics | CRITICAL |
| Secret rotation overdue | Key Vault rotation due date exceeded by 7 days | HIGH |
| Anomalous compliance rejection rate | > 50% of verifications rejected within 1 hour window | MEDIUM |

### Escalation Paths

| Priority | Trigger | Response |
|---|---|---|
| **P1 (CRITICAL)** | Audit log tamper, PII leak confirmed, active data breach | Immediate page to on-call security engineer; CISO notified within 30 minutes; GDPR 72-hour notification clock starts |
| **P2 (HIGH)** | Auth/JWT anomaly, secret rotation overdue, new CRITICAL CVE | On-call paged; response within 2 hours |
| **P3 (MEDIUM)** | Rate limit saturation, anomalous rejection rate | Ticket created automatically; triage within next business day |

### Runbooks

All runbooks stored in `docs/runbooks/` and linked from the APIM developer portal:

- `incident-pii-exposure.md` — Steps for suspected PII data breach: isolate affected resource, initiate forensic snapshot, start GDPR 72-hour notification clock, notify DPO
- `incident-jwt-compromise.md` — Steps to rotate all JWT signing keys, invalidate all active sessions globally, issue emergency communications to API consumers
- `incident-db-breach.md` — Isolate PostgreSQL private endpoint, rotate all database credentials via Key Vault, take forensic snapshot, assess blast radius
- `incident-audit-log-tamper.md` — Freeze audit log writes, notify compliance officer, preserve Log Analytics immutable copy, initiate forensic review of hash chain gap
- `dr-drill-checklist.md` — Quarterly DR drill procedure: failover test, backup restore validation, chaos experiment execution

---

## Context

### Beginning context

### Ending context
- `specs/kyc-api.yaml` - Complete OpenAPI 3.1 specification
- `src/models.py` - Pydantic models for data validation
- `src/api.py` - FastAPI application with all endpoints
- `src/compliance_checker.py` - Compliance checking logic
- `src/document_verifier.py` - Document verification services
- `src/auth.py` - Authentication and authorization
- `tests/test_kyc_api.py` - Comprehensive test suite
- `tests/contract_tests.py` - Contract testing with schemathesis
- `docs/api-documentation.md` - API documentation
- `requirements.txt` - Project dependencies
- `README.md` - Installation and usage instructions
- `src/config.py` - Environment, deploy phase, feature flags, version metadata
- `Dockerfile` - Container image for Azure (ACR)
- `infra/main.bicep` and `infra/parameters/phase-*-{env}.bicepparam` - IaC per rollout phase
- `.github/workflows/build.yml`, `.github/workflows/deploy.yml` - CI/CD with phase/environment gates
- `CHANGELOG.md` - Phase completion and release notes tied to Git tags
- `docs/testing-strategy.md` - Comprehensive testing strategy: all test layers, security testing (SAST/DAST/fuzzing/IDOR), CI gate progression per phase, test data governance
- `docs/asvs-compliance-checklist.md` - OWASP ASVS Level 2 tracking checklist, updated and signed off per phase
- `src/middleware/security_headers.py` - Starlette middleware: HSTS, CSP, X-Frame-Options, Cache-Control, and other security response headers
- `src/middleware/pii_redaction.py` - structlog processor: redacts PII patterns from all log records before emission
- `rules/banking-pii.yml` - Custom semgrep rules for PII logging, raw SQL construction, and weak JWT algorithm usage
- `docs/runbooks/` - Incident response runbooks (PII exposure, JWT compromise, DB breach, audit log tamper, DR drill)

## Low-Level Tasks

### 1. Create OpenAPI Specification
```
What prompt would you run to complete this task?
CREATE specs/kyc-api.yaml with complete OpenAPI 3.1 specification

What file do you want to CREATE or UPDATE?
specs/kyc-api.yaml

What function do you want to CREATE or UPDATE?
Complete API specification with all endpoints

What are details you want to add to drive the code changes?
- Define all KYC API endpoints (customers, documents, verification, compliance)
- Include proper HTTP methods, status codes, and error responses
- Define request/response schemas with validation rules
- Add authentication and security requirements
- Include examples for all endpoints
- Follow RESTful design principles
```

### 2. Create Data Models
```
What prompt would you run to complete this task?
CREATE src/models.py with Pydantic models for KYC data

What file do you want to CREATE or UPDATE?
src/models.py

What function do you want to CREATE or UPDATE?
Pydantic models: Customer, Document, VerificationResult, ComplianceCheck

What are details you want to add to drive the code changes?
- Customer model with KYC fields (name, DOB, address, phone, email)
- Document model for uploaded documents
- VerificationResult model for verification outcomes
- ComplianceCheck model for compliance status
- Include proper validation and error messages
- Add data privacy and security considerations
```

### 3. Implement FastAPI Application
```
What prompt would you run to complete this task?
CREATE src/api.py with FastAPI application and all endpoints

What file do you want to CREATE or UPDATE?
src/api.py

What function do you want to CREATE or UPDATE?
FastAPI app with endpoints: POST /customers, GET /customers/{id}, POST /customers/{id}/documents, POST /customers/{id}/verify, GET /customers/{id}/compliance

What are details you want to add to drive the code changes?
- Implement all endpoints from OpenAPI specification
- Add proper request/response validation using Pydantic models
- Include comprehensive error handling with proper HTTP status codes
- Add authentication and authorization middleware
- Include audit logging for all operations
- Follow FastAPI best practices
```

### 4. Implement Document Verification
```
What prompt would you run to complete this task?
CREATE src/document_verifier.py with document verification logic

What file do you want to CREATE or UPDATE?
src/document_verifier.py

What function do you want to CREATE or UPDATE?
DocumentVerifier class with methods: verify_identity_document(), verify_address_document(), verify_income_document()

What are details you want to add to drive the code changes?
- Implement mock document verification services
- Add validation for different document types (passport, driver's license, utility bills)
- Include OCR simulation for document text extraction
- Add document authenticity checks
- Include error handling for invalid documents
- Add audit logging for verification attempts
```

### 5. Implement Compliance Checking
```
What prompt would you run to complete this task?
CREATE src/compliance_checker.py with compliance checking logic

What file do you want to CREATE or UPDATE?
src/compliance_checker.py

What function do you want to CREATE or UPDATE?
ComplianceChecker class with methods: check_sanctions(), check_pep(), check_aml(), generate_compliance_report()

What are details you want to add to drive the code changes?
- Implement sanctions list checking (OFAC, EU, UN)
- Add PEP (Politically Exposed Person) screening
- Include AML (Anti-Money Laundering) risk assessment
- Add compliance scoring and risk categorization
- Include audit logging for all compliance checks
- Add data privacy compliance validation
```

### 6. Create Contract Tests
```
What prompt would you run to complete this task?
CREATE tests/contract_tests.py with schemathesis contract testing

What file do you want to CREATE or UPDATE?
tests/contract_tests.py

What function do you want to CREATE or UPDATE?
Contract test suite using schemathesis to validate API against OpenAPI spec

What are details you want to add to drive the code changes?
- Use schemathesis to generate test cases from OpenAPI spec
- Test all endpoints, methods, and response codes
- Validate request/response schemas
- Test error handling and edge cases
- Include performance and load testing
- Add test data fixtures for realistic scenarios
```

### 7. Create Integration Tests
```
What prompt would you run to complete this task?
CREATE tests/test_kyc_api.py with comprehensive integration tests

What file do you want to CREATE or UPDATE?
tests/test_kyc_api.py

What function do you want to CREATE or UPDATE?
Integration test suite: TestCustomerAPI, TestDocumentVerification, TestComplianceChecking

What are details you want to add to drive the code changes?
- Test complete KYC workflow end-to-end
- Test document verification with mock services
- Test compliance checking with sample data
- Include error scenarios and edge cases
- Test authentication and authorization
- Add performance tests for API endpoints
- Include security tests for input validation
```

### 8. Add Authentication and Security
```
What prompt would you run to complete this task?
CREATE src/auth.py with JWT authentication and security

What file do you want to CREATE or UPDATE?
src/auth.py

What function do you want to CREATE or UPDATE?
Authentication system with JWT tokens, role-based access control, and security middleware

What are details you want to add to drive the code changes?
- Implement JWT token-based authentication
- Add role-based access control (admin, user, read-only)
- Include password hashing and validation
- Add rate limiting and throttling
- Include security headers and CORS configuration
- Add audit logging for authentication events
- Implement session management and token refresh
```

### 10. Implement Security Middleware and JWT Hardening
```
What prompt would you run to complete this task?
CREATE src/middleware/security_headers.py, src/middleware/pii_redaction.py, and harden src/auth.py with RS256, refresh token rotation, and jti revocation

What file do you want to CREATE or UPDATE?
src/auth.py, src/middleware/security_headers.py, src/middleware/pii_redaction.py, src/api.py (middleware registration)

What function do you want to CREATE or UPDATE?
SecurityHeadersMiddleware, PiiRedactionProcessor (structlog), create_access_token (RS256), create_refresh_token, rotate_refresh_token, revoke_token_family, verify_token (RS256 + jti blacklist), GET /.well-known/jwks.json endpoint

What are details you want to add to drive the code changes?
- src/middleware/security_headers.py: Starlette BaseHTTPMiddleware; add HSTS, CSP, X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy no-referrer, Cache-Control no-store to all data responses; suppress CSP in dev/test environments (feature flag kyc.strict-security-headers)
- src/middleware/pii_redaction.py: structlog processor; define regex patterns for SSN (\d{3}-\d{2}-\d{4}), 16-digit card numbers, email, and phone; replace matched values with [REDACTED] in all log record values before emission
- src/auth.py JWT hardening: use python-jose or PyJWT with RS256 algorithm; load private key from Key Vault at startup; access token TTL 15 min; refresh token TTL configurable (24h dev/test, 8h staging/prod via settings); implement refresh token family tracking in Redis (SET per family_id → set of jti values); on refresh token reuse detection revoke entire family; jti blacklist: on logout/privilege change write jti to Redis SET with TTL = remaining token lifetime; every verify_token call checks jti against blacklist
- GET /.well-known/jwks.json: return RSA public key in JWK format (n, e, kid, kty, alg, use); support multiple keys during rotation overlap window
- Register both middlewares in src/api.py app factory; security headers first, then PII redaction processor added to structlog chain
- Add integration test: verify security headers present on data responses; verify headers absent from /health and /ready
- Phase-gate: jti blacklist and mTLS flag gated on DEPLOY_PHASE >= 3; Entra-only auth gated on APP_ENV in (staging, prod)
```

### 11. Create Testing Strategy Document and Security Test Suite
```
What prompt would you run to complete this task?
CREATE docs/testing-strategy.md and tests/security/ test files implementing the security test scenarios

What file do you want to CREATE or UPDATE?
docs/testing-strategy.md (already created), tests/security/test_auth_bypass.py, tests/security/test_jwt_fuzzing.py, tests/security/test_idor.py, tests/security/test_pii_leakage.py, tests/security/test_rate_limiting.py, tests/security/test_input_validation.py, tests/security/test_privilege_escalation.py, tests/compliance/test_gdpr.py, tests/compliance/test_aml_kyc.py, tests/compliance/test_audit_log.py, tests/fixtures/synthetic_data.py, rules/banking-pii.yml, .zap/rules.tsv, .secrets.baseline

What function do you want to CREATE or UPDATE?
Security test classes per file above; KYCBankingProvider(BaseProvider) for synthetic data; semgrep custom rules; ZAP policy file

What are details you want to add to drive the code changes?
- tests/security/test_auth_bypass.py: 9 scenarios (no token, expired, HS256, alg:none, revoked jti, missing iss, wrong aud, insufficient role, cross-tenant); all return 401 or 403 never 500
- tests/security/test_jwt_fuzzing.py: use hypothesis @given strategies to fuzz sub, roles, exp claims and header fields; all fuzz inputs must return 401 never 500
- tests/security/test_idor.py: fixture creates two customers with separate JWTs; JWT(A) accessing customer B endpoints returns 403; endpoint returns 403 for non-existent resource IDs too (no enumeration oracle)
- tests/security/test_pii_leakage.py: verify response bodies contain no regex-matched PII; check audit_log table; check captured log output; check /health response
- tests/security/test_rate_limiting.py: mock Redis clock; per-user rate limit enforcement; Retry-After header present; limit resets after window
- tests/security/test_input_validation.py: hypothesis-driven boundary tests for all string fields; all violations return 422 never 500
- tests/compliance/test_gdpr.py: delete customer removes PII; soft-delete lifecycle; data portability export
- tests/compliance/test_aml_kyc.py: sanctions hit blocks onboarding; PEP enhanced due diligence; risk score thresholds; document expiry
- tests/compliance/test_audit_log.py: one test per mutating operation; audit_no_pii_in_any_record scans full table after test suite
- tests/fixtures/synthetic_data.py: Faker + KYCBankingProvider; seeded with Faker(seed=42) for reproducibility; kyc_pep_customer(), kyc_sanctioned_customer(), kyc_high_risk_customer() high-risk profiles
- rules/banking-pii.yml: semgrep rules for PII logging, raw SQL interpolation, weak JWT algorithm usage
- .zap/rules.tsv: IGNORE info-level on health/ready probes; FAIL on MEDIUM+ alerts
```

### 9. Add deployment phase visibility and cloud readiness
```
What prompt would you run to complete this task?
CREATE src/config.py, Dockerfile, infra parameters, and CI workflows so phased Azure rollout is visible in code

What file do you want to CREATE or UPDATE?
src/config.py, Dockerfile, infra/parameters/*.bicepparam, .github/workflows/deploy.yml, GET /health in src/api.py

What function do you want to CREATE or UPDATE?
Settings model (APP_ENV, DEPLOY_PHASE); health endpoint returning env, phase, version; deploy workflow with phase input

What are details you want to add to drive the code changes?
- pydantic-settings for APP_ENV and DEPLOY_PHASE (injected by pipeline / Helm)
- Health response: {"status": "ok", "env": "...", "phase": 3, "version": "1.0.0", "git_sha": "..."}
- Dockerfile with PYTHON 3.12, non-root user, GIT_SHA and VERSION build args
- Git tag convention: deploy/phase-N-{env} documented in README
- ACR image tags: semver + phase-env suffix on promote
- Feature flags (env or Azure App Configuration): blob storage, entra-only auth, disable OpenAPI UI by phase
- deploy.yml: inputs phase + environment; GitHub Environment protection for staging/prod
- Parameter files phase-1-dev through phase-4-prod with incremental enableFrontDoor, privateEndpoints flags
- Prod checklist gate job before production deploy (validates security checklist markdown or workflow inputs)
```
