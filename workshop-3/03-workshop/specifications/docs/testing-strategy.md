# KYC API — Comprehensive Testing Strategy

> Authoritative reference for test coverage requirements, tooling, CI/CD gate configuration per deployment phase, and test data governance. All engineers and CI pipelines must conform to this strategy. The API specification source of truth is `specs/kyc-api.yaml`; the OpenAPI contract governs all contract tests.

---

## 1. Test Pyramid and Coverage Targets

| Layer | Tool(s) | Coverage / Pass Gate | Phase Gate |
|---|---|---|---|
| Unit | pytest 8.x + pytest-cov | > 80% line coverage | Phase 0 |
| Integration | pytest + testcontainers[postgresql] | All endpoint happy + sad paths | Phase 1 |
| Contract | schemathesis 3.x | 100% schema conformance | Phase 2 |
| End-to-end | pytest + httpx + docker compose | Full KYC workflow scenarios | Phase 2 |
| Security SAST | bandit + semgrep | Zero HIGH findings | Phase 2 |
| Security DAST | OWASP ZAP | Zero HIGH/CRITICAL alerts | Phase 3 |
| Performance | Locust | Baseline RPS targets met | Phase 3 |
| Compliance | custom pytest suite | All regulatory scenarios pass | Phase 4 |
| Chaos | Azure Chaos Studio + chaostoolkit | Documented resilience targets met | Phase 4 |

---

## 2. Unit Tests

### Principles

FIRST — **F**ast (< 200 ms per test), **I**ndependent (no shared mutable state between tests), **R**epeatable (deterministic, seed-controlled random data), **S**elf-validating (assert without manual inspection), **T**imely (written before or alongside production code).

### Framework

```
pytest 8.x
pytest-cov
pytest-mock
pytest-asyncio
```

### Structure

```
tests/
  unit/
    test_models.py                # Pydantic model validation, boundary conditions
    test_compliance_checker.py    # Sanctions/PEP/AML scoring logic
    test_document_verifier.py     # Document type dispatch, status codes
    test_auth.py                  # JWT creation, validation, revocation
    test_security_headers.py      # Middleware header assertions
    test_pii_redaction.py         # Log redaction middleware output
    conftest.py                   # Fixtures: mock DB session, fake JWT factory
```

### Coverage Gate

```bash
pytest tests/unit/ \
  --cov=src \
  --cov-fail-under=80 \
  --cov-report=xml:reports/coverage.xml \
  --cov-report=term-missing
```

JUnit XML uploaded as CI artifact; Codecov or Azure coverage gate posts status check on PRs. Branch and line coverage both reported.

### Key Unit Test Categories

**Pydantic model boundary validation**
- Phone: valid E.164, missing `+`, too short, too long, non-digit characters
- DOB: exactly 18 years ago (boundary), 17 years 364 days (rejected), future date, >150 years ago
- Email: missing `@`, multiple `@`, local part >254 chars, valid international format
- Name: empty string, 1 char, 255 chars, 256 chars (rejected), HTML tags, null bytes
- Tax ID: synthetic checksum-valid format passes, wrong checksum fails
- `extra='forbid'`: any unknown field in body → `422`

**JWT unit tests**
- Valid RS256 token → `200`
- Token signed with HS256 → `401` (algorithm rejected)
- Expired token (`exp` = 1 second ago) → `401`
- `alg: none` attack → `401`
- Missing `iss` claim → `401`
- Missing `aud` claim → `401`
- Revoked `jti` in Redis blacklist → `401`
- Token with unknown role → `403` on protected route
- Refresh token reuse after rotation → `401` (family revoked)

**RBAC tests**
- Each of `admin`, `kyc_officer`, `readonly` roles tested against every protected route decorator
- Positive case for highest-required role; negative cases for all lower roles

**PII redaction**
- Log record containing SSN pattern `\d{3}-\d{2}-\d{4}` → value replaced with `[REDACTED]` in output
- Log record containing email → `[REDACTED]`
- Log record with `tax_id` key → value `[REDACTED]`
- Non-PII fields in same record remain unredacted

### AAA Structure

Every test function must have clear Arrange / Act / Assert sections:

```python
def test_expired_token_returns_401(client, expired_jwt):
    # Arrange
    headers = {"Authorization": f"Bearer {expired_jwt}"}

    # Act
    response = client.get("/customers/abc-123", headers=headers)

    # Assert
    assert response.status_code == 401
    assert response.json()["detail"] == "Token has expired"
```

---

## 3. Integration Tests

### Principle

No mocks for the database layer. All integration tests run against a real PostgreSQL instance provisioned by `testcontainers`. Schema applied via `alembic upgrade head` in the session-scoped fixture.

### Framework

```
pytest
httpx (AsyncClient)
testcontainers[postgresql]
alembic
```

### Structure

```
tests/
  integration/
    test_customer_crud.py       # POST/GET/PATCH /customers full DB round-trip
    test_document_upload.py     # POST /customers/{id}/documents
    test_verification_flow.py   # POST /customers/{id}/verify with real DB state machine
    test_compliance_checks.py   # GET /customers/{id}/compliance — real scoring
    test_audit_log.py           # Assert audit_log rows after every operation
    test_rate_limiting.py       # Redis rate limit enforcement
    conftest.py                 # PostgreSQL + Redis container fixtures, app factory
```

### Database Fixture Pattern

```python
@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        run_alembic_migrations(pg.get_connection_url())
        yield pg

@pytest.fixture(autouse=True)
def clean_db(db_session):
    yield
    db_session.rollback()
    for table in reversed(metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()
```

Each test function runs inside a transaction that is rolled back (or tables are truncated). No test data leaks between tests.

### Required Integration Test Coverage

- Complete customer lifecycle: create → upload document → verify → compliance check → assert `APPROVED` result
- Constraint violations: duplicate customer (unique index), invalid FK reference, missing required field at DB level
- Audit log assertion: after **every** write operation, query `audit_log` table and assert:
  - Exactly one new row inserted
  - `action` field matches expected action string
  - `actor_id` matches JWT `sub`
  - `resource_id` matches the created/modified resource UUID
  - No PII values present in any column
- Rate limit enforcement: send 61 requests in 60-second window (mock Redis time) to rate-limited endpoint → 60th succeeds with `200`, 61st returns `429` with `Retry-After` header

---

## 4. Contract Tests

### Tool

`schemathesis` 3.x — generates and fuzzes test cases from `specs/kyc-api.yaml`.

### Running

```bash
schemathesis run specs/kyc-api.yaml \
  --base-url http://localhost:8000 \
  --auth-type bearer \
  --auth "$TEST_JWT" \
  --checks all \
  --stateful=links \
  --hypothesis-max-examples=100 \
  --junit-xml=reports/schemathesis.xml \
  --report=reports/schemathesis.html
```

### CI Gate (Phase 2+)

`schemathesis` exits non-zero on any schema violation or response that does not conform to the declared OpenAPI schema. JUnit XML parsed by CI for test reporting. Build fails on first schema violation.

### Stateful Testing

`x-links` extensions in `specs/kyc-api.yaml` define the KYC state machine for multi-step fuzzing:

```yaml
POST /customers:
  responses:
    "201":
      links:
        GetCreatedCustomer:
          operationId: getCustomer
          parameters:
            customer_id: $response.body#/id
        UploadDocument:
          operationId: uploadDocument
          parameters:
            customer_id: $response.body#/id
```

Schemathesis follows links: `POST /customers` → `GET /customers/{id}` → `POST /customers/{id}/documents` → `POST /customers/{id}/verify`.

### Custom Checks

```
tests/contract/
  custom_checks.py
```

**`check_no_pii_in_response`**: scans every response body string value with regex patterns for SSN (`\d{3}-\d{2}-\d{4}`), raw 16-digit card numbers, and ISO date-of-birth fields — fails if any raw PII found in response from a non-admin endpoint.

**`check_audit_header_present`**: every mutating response (`201`, `200` on POST) must include `X-Audit-Event-ID` response header.

**`check_error_body_schema`**: all `4xx` responses must have `{"detail": string}` or `{"detail": [{"loc":..., "msg":..., "type":...}]}` structure (no raw exception text).

---

## 5. End-to-End Tests

### Scope

Full KYC onboarding workflow running against a fully deployed container stack, not `TestClient`.

### Tool

```bash
docker compose -f docker-compose.test.yml up -d
pytest tests/e2e/ --base-url https://localhost:8443
docker compose -f docker-compose.test.yml down
```

Services in `docker-compose.test.yml`: `kyc-api`, `postgres:16`, `redis:7`, `wiremock` (mocks for sanctions list, PEP list, OCR service).

### Scenarios

| Scenario | Steps | Expected |
|---|---|---|
| Happy path — new customer approved | POST customer → POST passport → POST verify → GET compliance | `status: APPROVED`, audit log complete (4 records) |
| Sanctions hit | POST customer with name matching mock OFAC list → GET compliance | `status: REJECTED`, `reason: SANCTIONS_MATCH` |
| Document rejection | POST corrupt/expired document → POST verify | `document_status: INVALID`, `status: PENDING` |
| Unauthorized access (IDOR) | JWT(user A) → GET `/customers/{user B id}` | `403 Forbidden` |
| Token expiry | Use JWT with `exp` in the past → any protected endpoint | `401 Unauthorized`, `detail: Token has expired` |

---

## 6. Security Testing

### 6.1 SAST — Static Analysis

#### bandit (Phase 2+)

```bash
bandit -r src/ \
  --severity-level high \
  --confidence-level medium \
  --format json \
  --output reports/bandit.json
# Hard gate: exit non-zero on any HIGH severity finding
```

Key rules enforced for banking/KYC context:

| Rule | Description |
|---|---|
| B106 | Hardcoded password argument |
| B107 | Hardcoded password in function default |
| B501–B504 | Insecure TLS/SSL configuration |
| B608 | SQL injection via string formatting |
| B301, B302 | Pickle deserialization |
| B324 | Use of weak MD5/SHA1 hash function |

CI: SARIF output uploaded to GitHub Advanced Security → annotations appear inline on PRs.

#### semgrep (Phase 2+)

```bash
semgrep \
  --config=p/python \
  --config=p/owasp-top-ten \
  --config=p/secrets \
  --config=rules/banking-pii.yml \
  --error \
  --sarif \
  --output=reports/semgrep.sarif \
  src/
```

Custom `rules/banking-pii.yml` detects:
- `logging.*` calls with PII variable names (`customer_name`, `ssn`, `dob`, `tax_id`, `phone`, `email`)
- `f"SELECT ... {variable}"` patterns (raw SQL string interpolation)
- `jwt.decode(... algorithms=["HS256"])` (weak algorithm usage)
- `os.environ.get("DATABASE_URL")` used directly instead of Key Vault fetch pattern
- `subprocess.run(shell=True)` or `os.system()` with any variable interpolation

Gate: zero HIGH findings → build passes. MEDIUM findings allowed but reported.

---

### 6.2 DAST — Dynamic Analysis

#### OWASP ZAP (Phase 3+)

```yaml
# .github/workflows/deploy.yml — post-deploy job for test/staging
- name: OWASP ZAP Full Scan
  uses: zaproxy/action-full-scan@v0.10.0
  with:
    target: ${{ vars.KYC_API_URL }}
    rules_file_name: .zap/rules.tsv
    cmd_options: '-a -j -m 10 -T 60 -n specs/kyc-api.yaml'
    token: ${{ secrets.GITHUB_TOKEN }}
    fail_action: true
```

ZAP authenticated scan: `zap-auth-header.json` provides Bearer token for all requests. ZAP imports OpenAPI spec (`-n specs/kyc-api.yaml`) to enumerate all endpoints automatically.

`.zap/rules.tsv` configuration:
- `IGNORE` info-level findings on `/health` and `/ready` (no auth on probe endpoints)
- `FAIL` on any MEDIUM, HIGH, or CRITICAL alert

Outputs:
- HTML report uploaded as CI artifact
- GitHub issue created for any new HIGH+ alert via ZAP action built-in reporting
- JSON output parsed to extract alert count for metric trending

---

### 6.3 Dependency Scanning

```bash
# pip-audit — Phase 1+ on every PR
pip-audit \
  --strict \
  --format json \
  --output reports/pip-audit.json
# Hard gate: exits 1 on any vulnerability

# Trivy image scan — Phase 2+ on every build
trivy image \
  --exit-code 1 \
  --severity CRITICAL,HIGH \
  --format sarif \
  --output reports/trivy-image.sarif \
  kyc-api:${{ github.sha }}

# Trivy filesystem scan — Phase 2+
trivy fs . \
  --exit-code 1 \
  --severity CRITICAL,HIGH \
  --scanners vuln,secret,config \
  --format sarif \
  --output reports/trivy-fs.sarif

# SBOM generation — on every release tag
syft kyc-api:${{ github.sha }} \
  -o cyclonedx-json=reports/sbom.cyclonedx.json
```

Both Trivy SARIF outputs uploaded to GitHub Advanced Security. Known acceptable vulnerabilities documented in `.trivy-ignore` with justification comment and annual review date.

---

### 6.4 Authentication and Authorization Bypass Tests

File: `tests/security/test_auth_bypass.py`

| Test | Request | Expected |
|---|---|---|
| `test_no_token_returns_401` | Any protected endpoint, no `Authorization` header | `401` |
| `test_expired_token_returns_401` | JWT with `exp` = 60 seconds ago | `401` |
| `test_hs256_token_rejected` | HS256-signed token on RS256-only endpoint | `401` |
| `test_alg_none_attack` | JWT with `alg: none` in header | `401` |
| `test_revoked_jti_returns_401` | Valid JWT but `jti` in Redis blacklist | `401` |
| `test_missing_iss_returns_401` | JWT without `iss` claim | `401` |
| `test_wrong_audience_returns_401` | JWT with `aud` != API identifier | `401` |
| `test_insufficient_role_returns_403` | `readonly` JWT → `POST /customers/{id}/verify` | `403` |
| `test_cross_tenant_token_rejected` | JWT from staging issuer against prod (phase 3+) | `401` |

---

### 6.5 JWT Fuzzing and Token Manipulation Tests

File: `tests/security/test_jwt_fuzzing.py`

Uses `hypothesis` library with custom strategies. All inputs below must return `401` — **never `500`**.

**`sub` claim fuzzing**: empty string, null, string of 10,000 chars, SQL fragment (`' OR '1'='1`), unicode overflow (`￿ `), path traversal (`../../etc/passwd`)

**`roles` claim fuzzing**: non-list value (string), nested list, list with unknown role strings, list with 1,000 elements

**`exp` claim fuzzing**: `0` (Unix epoch), negative integer, string instead of integer, year 9999 (far future)

**Header manipulation**: remove `alg`, change `typ` to `JWT2`, add unknown header fields, change `kid` to unknown key ID

**Signature stripping**: base64-decode token, modify payload JSON, re-encode with original signature → must be rejected

**Algorithm confusion**: attempt to use RS256 public key as HS256 secret key

---

### 6.6 SQL Injection Tests

#### Automated — sqlmap (Phase 3+)

```bash
sqlmap \
  -u "https://kyc-api-test.example.com/customers/1" \
  -H "Authorization: Bearer $TEST_JWT" \
  --data='{"name":"test"}' \
  --level=5 \
  --risk=3 \
  --batch \
  --dbms=postgresql \
  --output-dir=reports/sqlmap/
```

Endpoints tested: `GET /customers/{id}`, `POST /customers` (all body fields), `GET /customers/{id}/compliance` (query parameters if any).

#### Manual Parametric Tests — `tests/security/test_sql_injection.py`

Payloads injected into every string request field:
- `' OR '1'='1`
- `'; DROP TABLE customers; --`
- `1 UNION SELECT * FROM pg_user --`
- `' AND SLEEP(5) --`

Expected outcomes (all must hold):
- Response status is `422` (Pydantic rejects at model boundary) or `200`/`403`/`404` (SQLAlchemy parameterizes safely)
- Response body contains **no** PostgreSQL error messages
- Response body contains **no** table/column structure information
- Response time does not increase by > 3 seconds (no time-based SQLi)

---

### 6.7 Rate Limiting Verification Tests

File: `tests/security/test_rate_limiting.py`

- `test_rate_limit_enforced_per_user`: mock Redis clock; send 61 requests as user A in 60-second window → 60th returns `200`, 61st returns `429` with `Retry-After` header
- `test_rate_limit_per_user_not_global`: user A exhausts limit → user B's next request returns `200`
- `test_rate_limit_headers_present`: every response includes `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- `test_rate_limit_resets_after_window`: exhaust limit → advance mock clock past window → next request returns `200`
- `test_rate_limit_429_body_schema`: `429` response body contains `{"detail": "Rate limit exceeded", "retry_after": <int>}`

---

### 6.8 PII Leakage Tests

File: `tests/security/test_pii_leakage.py`

- `test_response_body_no_raw_tax_id`: POST customer with `tax_id` value → GET customer → response contains token reference, **not** the raw `tax_id` value
- `test_error_response_no_pii`: submit customer with valid SSN-format string → `422` error body contains **no** SSN pattern
- `test_audit_log_no_raw_pii`: after creating customer, query `audit_log` table directly → scan all text columns with PII regex → assert zero matches
- `test_health_endpoint_no_secrets`: `GET /health` → response body contains no connection strings, no Key Vault URIs, no signing keys
- `test_log_output_redacted`: capture `structlog` output during request containing PII body → scan captured lines with SSN/email/phone regex → assert zero raw PII patterns

---

### 6.9 Secrets Detection

```bash
# detect-secrets — Phase 2+ (baseline approach)
detect-secrets scan --all-files > .secrets.baseline
# CI: compare scan output against committed baseline
detect-secrets scan --all-files | \
  python -c "import sys,json; \
    new=json.load(sys.stdin); base=json.load(open('.secrets.baseline')); \
    sys.exit(1 if new['results'] != base['results'] else 0)"

# truffleHog — Phase 3+ (full git history)
trufflehog git file://. \
  --only-verified \
  --fail \
  --json \
  --output=reports/trufflehog.json
```

`truffleHog` exits non-zero on any verified secret in git history → blocks deploy. `.secrets.baseline` committed to repository and reviewed quarterly.

---

### 6.10 TLS Configuration Testing

Tool: `testssl.sh` via Docker (Phase 3+ against staging endpoint)

```bash
docker run --rm drwetter/testssl.sh \
  --json \
  --logfile reports/testssl.json \
  --warnings off \
  kyc-api-staging.example.com:443
```

CI assertion script parses JSON output:

| Property | Required Value |
|---|---|
| `TLS1` (1.0) | `not offered` |
| `TLS1_1` (1.1) | `not offered` |
| `TLS1_2` | `offered` |
| `TLS1_3` | `offered` |
| `HSTS` | present, `max-age >= 31536000` |
| `BEAST` | `not vulnerable` |
| `POODLE_SSL` | `not vulnerable` |
| `HEARTBLEED` | `not vulnerable` |
| `ROBOT` | `not vulnerable` |
| `LUCKY13` | `not vulnerable` |

---

### 6.11 Input Validation Boundary Tests

File: `tests/security/test_input_validation.py`

Uses `hypothesis` library with `@given` decorator for property-based testing.

**Customer name**: empty string (`422`), 1 char (valid), 255 chars (boundary), 256 chars (`422`), Unicode emoji, null bytes, HTML tags `<script>alert(1)</script>`, SQL fragments

**Date of birth**: today (rejected — not 18+), exactly 18 years ago (accepted), yesterday - 18 years (rejected), >150 years ago (rejected), invalid format `not-a-date`, leap day Feb 29 1900 (invalid year)

**Phone (E.164)**: no `+` prefix, too short (+123), too long (>15 digits after +), non-digit chars (+1-800-FLOWERS), valid formats from 50 countries via hypothesis strategy

**Email**: `@domain.com` (no local part), `user@` (no domain), multiple `@`, local part >254 chars, valid international TLD formats

**File upload**: 0 bytes (`422`), 10 MB exactly (accepted), 10 MB + 1 byte (rejected), wrong MIME type declared, valid JPEG magic bytes but `.pdf` extension, zip bomb (compressed ratio > 100:1 rejected)

All boundary violations must return `422 Unprocessable Entity` with a structured `{"detail": [...]}` body. Must **never** return `500`.

---

### 6.12 IDOR Tests

File: `tests/security/test_idor.py`

Setup: two customers (A, B) with two corresponding valid JWTs.

| Test | JWT | Endpoint | Expected |
|---|---|---|---|
| `test_cannot_read_other_customer` | JWT(A) | `GET /customers/{B.id}` | `403` |
| `test_cannot_update_other_customer` | JWT(A) | `PATCH /customers/{B.id}` | `403` |
| `test_cannot_access_other_documents` | JWT(A) | `GET /customers/{B.id}/documents` | `403` |
| `test_kyc_officer_can_read_any` | JWT(officer) | `GET /customers/{B.id}` | `200` |
| `test_sequential_id_enumeration_blocked` | JWT(A) | `GET /customers/{B.id}` (B doesn't exist) | `403` (not `404`) |

**Critical**: endpoint must return `403` regardless of whether the resource ID exists. Returning `404` for non-existent vs `403` for existing-but-unauthorized creates an enumeration oracle that reveals which customer IDs are valid. Always return `403` when the requesting identity does not own the resource.

---

### 6.13 Privilege Escalation Tests

File: `tests/security/test_privilege_escalation.py`

- `test_readonly_cannot_create_customer`: `POST /customers` with `readonly` role → `403`
- `test_user_cannot_self_promote`: `PATCH /customers/{id}` with body `{"role": "admin"}` → `422` (field unknown due to `extra='forbid'`)
- `test_role_in_body_ignored`: even if request body includes a `roles` field that matches an existing Pydantic field, JWT claims are authoritative; body roles field is rejected
- `test_kyc_officer_cannot_delete`: `DELETE /customers/{id}` with `kyc_officer` role → `403`
- `test_horizontal_escalation_blocked`: `kyc_officer` A cannot view `kyc_officer` B's personal assignments or audit actions through any API parameter manipulation

---

## 7. Compliance Testing

### 7.1 GDPR Right-to-Erasure

File: `tests/compliance/test_gdpr.py`

- `test_delete_customer_removes_pii`: `DELETE /customers/{id}` (admin role) → `GET /customers/{id}` returns `404`; assert DB: PII columns set to NULL or row removed; Blob documents deleted; `pii_vault` tokens marked invalid
- `test_delete_emits_audit_event`: after deletion, `audit_log` contains record with `action=customer.pii.erased`, `actor_id` present, **no** PII values anywhere in the record
- `test_soft_delete_purge_lifecycle`: soft-delete creates `deleted_at` timestamp; assert purge job (30-day TTL) hard-deletes the record after the retention period
- `test_data_portability_export`: `GET /customers/{id}/export` (admin or owner) returns structured JSON containing all stored data for the subject; response is complete and well-formed

### 7.2 AML/KYC Regulatory Validation

File: `tests/compliance/test_aml_kyc.py`

- `test_pep_requires_enhanced_due_diligence`: customer flagged as Politically Exposed Person → compliance result includes `enhanced_due_diligence_required: true` and `risk_category: HIGH`
- `test_sanctions_match_blocks_onboarding`: customer name matches mock OFAC SDN entry → `POST /customers/{id}/verify` sets `status: REJECTED`, `reason: SANCTIONS_HIT`
- `test_aml_risk_score_thresholds`: score 0–29 → `risk_category: LOW`; 30–69 → `MEDIUM`; 70–100 → `HIGH`; assert all boundary values
- `test_document_expiry_validation`: passport with expiry date in the past → document verification returns `document_status: EXPIRED`
- `test_high_risk_jurisdiction_flag`: customer address in FATF high-risk jurisdiction → `risk_category` automatically elevated to minimum `HIGH`
- `test_compliance_recheck_on_material_change`: update customer nationality → assert `compliance_status` transitions to `PENDING_REVIEW` within the same request

### 7.3 Audit Log Completeness

File: `tests/compliance/test_audit_log.py`

For every mutating API operation, assert exactly one audit record exists with correct `action`, `actor_id`, `resource_id`, and `outcome`:

| Test | Operation | Expected `action` |
|---|---|---|
| `test_audit_customer_create` | `POST /customers` | `customer.create` |
| `test_audit_document_upload` | `POST /customers/{id}/documents` | `document.upload` |
| `test_audit_verify_start` | `POST /customers/{id}/verify` | `customer.verify.start` |
| `test_audit_verify_complete` | Verification job completion | `customer.verify.complete` |
| `test_audit_compliance_check` | `GET /customers/{id}/compliance` | `compliance.check` |
| `test_audit_failed_auth` | Invalid JWT request | `auth.failure` |
| `test_audit_pii_access` | Any PII field resolved by admin | `pii.resolve` |

`test_audit_no_pii_in_any_record`: after all tests run, scan entire `audit_log` table for `\d{3}-\d{2}-\d{4}` (SSN), email, and phone regex patterns → assert zero matches across all columns.

---

## 8. Performance and Reliability Tests

### 8.1 Load Tests (Locust)

File: `tests/performance/locustfile.py`

**Baseline RPS targets** (Phase 3+ against staging environment):

| Endpoint | Target RPS | p95 Latency |
|---|---|---|
| `POST /customers` | 50 | < 500 ms |
| `GET /customers/{id}` | 200 | < 100 ms |
| `POST /customers/{id}/verify` | 20 | < 2,000 ms |
| `GET /customers/{id}/compliance` | 100 | < 200 ms |
| `GET /health` | 500 | < 50 ms |

```python
class KYCUserBehavior(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def get_customer(self):
        self.client.get(f"/customers/{self.customer_id}",
                        headers=self.auth_headers)

    @task(1)
    def create_customer(self):
        response = self.client.post("/customers",
                                    json=synthetic_customer(),
                                    headers=self.auth_headers)
        if response.status_code == 201:
            self.customer_id = response.json()["id"]

    @task(1)
    def verify_customer(self):
        self.client.post(f"/customers/{self.customer_id}/verify",
                         headers=self.admin_headers)
```

CI run (Phase 3+ post-deploy):

```bash
locust -f tests/performance/locustfile.py \
  --headless \
  -u 100 -r 10 \
  --run-time 2m \
  --host "$KYC_STAGING_URL" \
  --csv=reports/locust \
  --exit-code-on-error 1
```

Threshold check: `scripts/check_locust_thresholds.py` parses `locust_stats.csv` and exits `1` if any endpoint exceeds p95 target.

### 8.2 Chaos Testing (Phase 4+)

Tool: **Azure Chaos Studio** experiments + **chaostoolkit-azure** for AKS targets.

| Scenario | Fault Injected | Pass Criteria |
|---|---|---|
| Pod kill | Kill 50% of API pods | Load balancer routes to surviving pods; health checks green within 30 s |
| PostgreSQL failover | Force primary failover to replica | Connection pool reconnects; requests queue (not fail) during 10 s failover window |
| Redis unavailability | Block Redis port | API falls back to direct DB rate-limit check (degraded); no crash; alert fires within 5 min |
| Key Vault throttled | Inject throttle faults | Cached secrets serve requests; new startup fails gracefully; alert fires within 5 min |
| Network partition | Simulate VNet partition from external service | Sanctions check times out → returns `SERVICE_UNAVAILABLE` (not `500`); circuit breaker trips |

Chaos results are human-reviewed after each Phase 4 DR drill. Pass criteria and evidence documented in `docs/runbooks/dr-drill-checklist.md`.

---

## 9. CI/CD Test Gates Per Phase

### Phase 0 — Local Development

```
pytest tests/unit/ --cov-fail-under=80
schemathesis run specs/kyc-api.yaml --base-url http://localhost:8000
```

### Phase 1 — dev (on every PR)

```
All Phase 0 gates, plus:
├── pytest tests/unit/ + tests/integration/ (testcontainers PostgreSQL)
├── pip-audit --strict (hard gate: any vuln → fail)
└── docker build + trivy fs . --severity CRITICAL,HIGH
```

### Phase 2 — test (on deploy/phase-2-test tag)

```
All Phase 1 gates, plus:
├── schemathesis run against deployed test API (schema conformance hard gate)
├── pytest tests/contract/ (custom schemathesis checks)
├── pytest tests/security/test_pii_leakage.py
├── bandit -r src/ --severity-level high (SAST hard gate)
├── semgrep --config=p/owasp-top-ten --error (SAST hard gate)
├── detect-secrets scan (compare to committed baseline)
└── trivy image --severity CRITICAL,HIGH (image scan hard gate)
```

### Phase 3 — staging (on deploy/phase-3-staging tag)

```
All Phase 2 gates, plus:
├── OWASP ZAP full scan against staging (zero HIGH/CRITICAL alerts hard gate)
├── pytest tests/security/ (full suite: auth bypass, IDOR, SQLi, JWT fuzzing, rate limit)
├── testssl.sh assertions against staging endpoint
├── trufflehog git --only-verified --fail (full history secrets scan)
├── locust load test (baseline RPS targets hard gate)
└── pytest tests/compliance/ (GDPR, AML, audit completeness)
```

### Phase 4 — prod (on deploy/phase-4-prod tag)

```
All Phase 3 gates, plus:
├── Security checklist gate job (manual approval required — GitHub Environment: production)
├── Penetration test sign-off artifact present
│   └── check: compliance/pentest-signoff-$(date +%Y-Q*).pdf exists in repo
├── OWASP ASVS Level 2 sign-off document present
│   └── check: docs/asvs-compliance-checklist.md all items checked
├── sqlmap scan report reviewed (manual gate with reviewer attestation)
└── Chaos test results reviewed (manual gate with DR attestation)
```

Gate implementation for Phase 4 prod checklist:

```yaml
jobs:
  security-checklist-gate:
    runs-on: ubuntu-latest
    if: inputs.environment == 'production'
    environment: production    # Requires manual approval + wait timer
    steps:
      - uses: actions/checkout@v4

      - name: Verify penetration test sign-off artifact
        run: |
          QUARTER=$(python3 -c "
          from datetime import date
          d = date.today()
          q = (d.month - 1) // 3 + 1
          print(f'{d.year}-Q{q}')
          ")
          if [[ ! -f "compliance/pentest-signoff-${QUARTER}.pdf" ]]; then
            echo "ERROR: Penetration test sign-off for ${QUARTER} not found"
            exit 1
          fi

      - name: Verify ASVS checklist complete
        run: |
          UNCHECKED=$(grep -c '^\- \[ \]' docs/asvs-compliance-checklist.md || true)
          if [[ "$UNCHECKED" -gt 0 ]]; then
            echo "ERROR: $UNCHECKED ASVS items unchecked"
            exit 1
          fi
```

---

## 10. Test Data Strategy

### Synthetic PII Generation

File: `tests/fixtures/synthetic_data.py`

```python
from faker import Faker
from faker.providers import BaseProvider

fake = Faker(seed=42)    # Seeded for reproducible contract/schemathesis data

class KYCBankingProvider(BaseProvider):
    def kyc_customer(self) -> dict:
        """Generates realistic but entirely synthetic customer — never a real person."""
        return {
            "first_name": self.generator.first_name(),
            "last_name": self.generator.last_name(),
            "date_of_birth": self.generator.date_of_birth(
                minimum_age=18, maximum_age=80
            ).isoformat(),
            "phone": self._e164_phone(),
            "email": self.generator.email(),
            "nationality": self.generator.country_code(representation="alpha-2"),
            "address": self._kyc_address(),
        }

    def kyc_pep_customer(self) -> dict:
        """Customer whose full name matches a mock PEP list entry."""
        ...

    def kyc_sanctioned_customer(self) -> dict:
        """Customer matching a mock OFAC SDN list entry."""
        ...

    def kyc_high_risk_customer(self) -> dict:
        """Customer from a FATF high-risk jurisdiction."""
        ...
```

### Test Data Vault

- Separate PostgreSQL instance `kyc_test` — never shares a server or credentials with production.
- `docker-compose.test.yml` provisions isolated test PostgreSQL, Redis, and WireMock containers.
- Test fixtures cleaned between test runs via `TRUNCATE ... RESTART IDENTITY CASCADE` in `conftest.py` teardown.
- **No production data is ever copied to any test environment.** This policy is documented in `docs/data-classification.md` and enforced by network policy (no prod-to-test connectivity).

### PII Scrubbing for Staging (Emergency Use Only)

If production-originated data is ever required in staging (strongly discouraged — approval required):

```bash
python scripts/scrub-staging-data.py \
  --target-db "$STAGING_DB_URL" \
  --audit-to "$LOG_ANALYTICS_WORKSPACE_ID"
```

Script behavior:
- Replaces all PII columns with `faker`-generated synthetic equivalents
- Idempotent (can be re-run safely)
- Tags all scrubbed rows with `data_origin='synthetic'` in metadata column
- Writes scrubbing operation to audit log
- Requires `ADMIN_APPROVAL_TOKEN` env var (issued by security officer)

---

## 11. Test Reporting and Metrics

| Report | Tool | Output | CI Action |
|---|---|---|---|
| Unit test results | pytest | JUnit XML | CI test summary panel |
| Coverage | pytest-cov | XML + HTML | Codecov PR status check; fail if < 80% |
| SAST (bandit) | bandit | SARIF | GitHub Advanced Security annotations |
| SAST (semgrep) | semgrep | SARIF | GitHub Advanced Security annotations |
| Container vuln | Trivy | SARIF | GitHub Advanced Security annotations |
| Dependency vuln | pip-audit | JSON artifact | Build failure + Slack alert if HIGH+ |
| Contract testing | schemathesis | JUnit XML + HTML | CI test summary + artifact link in PR comment |
| DAST | OWASP ZAP | HTML artifact | GitHub issue created for new HIGH+ |
| Performance | Locust | CSV | Threshold check script; fail if p95 exceeded |
| TLS | testssl.sh | JSON | Assertion script; fail if TLS 1.0/1.1 offered |
| Secrets scan | truffleHog | JSON artifact | Build failure on verified secret |
| SBOM | syft | CycloneDX JSON | Attached to GitHub Release |

**Monthly security trend report**: Log Analytics query aggregates test results over rolling 30 days → generates trend dashboard → emailed to security team and stored in `compliance/monthly-security-reports/`.
