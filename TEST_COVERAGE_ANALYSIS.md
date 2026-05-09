# Test Coverage Analysis — doc-scan-gallery

## Current State

The repository contains no application code and no tests. This document serves as
a test coverage baseline and roadmap to ensure quality is built in from the start.

---

## Expected Application Layers

Based on the project name ("doc-scan-gallery"), the app likely involves:

| Layer | Responsibilities |
|---|---|
| **Document ingestion** | Upload, validate, and store scanned documents |
| **Image processing** | Cropping, rotation, contrast enhancement, OCR |
| **Gallery / UI** | Browse, search, filter, and view documents |
| **Storage / persistence** | CRUD operations against a database or file store |
| **Auth** | User authentication and authorization |
| **API** | REST or GraphQL endpoints consumed by the UI |

---

## Coverage Gaps & Proposed Tests

### 1. Document Ingestion

**Gap**: No validation tests for uploaded files.

Proposed tests:
- Accept valid file types (PDF, PNG, JPG, TIFF) and reject unsupported ones.
- Enforce maximum file size limits and return meaningful errors.
- Handle corrupt or truncated files without crashing.
- Ensure duplicate detection (same hash) produces correct behavior (reject or deduplicate).
- Verify that metadata (filename, upload timestamp, uploader ID) is persisted correctly.

```
test("rejects files larger than 10 MB")
test("rejects unsupported MIME types")
test("handles corrupt PDF without throwing unhandled exception")
test("stores correct metadata on successful upload")
```

---

### 2. Image Processing

**Gap**: Image manipulation logic is typically untested because it depends on binary output.

Proposed tests:
- Unit-test pure transformation functions (rotation angles, crop boundaries) against known inputs/outputs.
- Snapshot-test processed images using checksum comparison to catch regressions.
- Test OCR result structure (returned fields, confidence scores) using mocked OCR provider responses.
- Test that processing failures are surfaced as structured errors, not silent nulls.

```
test("rotates image 90° clockwise and returns correct dimensions")
test("crop returns bounding box within original image dimensions")
test("OCR returns expected fields when provider returns success response")
test("OCR propagates structured error when provider is unavailable")
```

---

### 3. Gallery / UI Components

**Gap**: UI components have no unit or interaction tests.

Proposed tests:
- Render tests for the gallery grid: correct number of thumbnails, correct labels.
- Search / filter: entering a query filters the visible document list.
- Pagination: navigating pages updates the displayed items.
- Empty state: gallery with zero documents renders a helpful message, not a blank screen.
- Loading state: while documents fetch, a skeleton/spinner is shown.
- Error state: when the API fails, an error message is shown with a retry option.

```
test("renders one thumbnail per document")
test("filter by date range hides out-of-range documents")
test("empty gallery shows 'No documents found' message")
test("API error shows error banner with retry button")
```

---

### 4. Storage / Persistence

**Gap**: No database interaction tests.

Proposed tests:
- CRUD happy paths: create, read, update, delete a document record.
- Constraint violations: inserting a duplicate ID returns a conflict error.
- Soft-delete: deleted documents are excluded from list queries but recoverable.
- Ordering: list query returns documents sorted by the requested field.
- Pagination: offset/cursor pagination returns correct pages and handles the last page.

Use an in-memory or containerized database (e.g., SQLite, Postgres via Docker) rather than mocking the DB layer — mocking DB calls gives false confidence.

```
test("createDocument persists all fields and returns inserted record")
test("listDocuments excludes soft-deleted records by default")
test("listDocuments paginates correctly at boundary (last page)")
```

---

### 5. Authentication & Authorization

**Gap**: Auth is a high-risk area with no tests.

Proposed tests:
- Unauthenticated requests to protected routes return 401.
- Authenticated requests with insufficient role return 403.
- JWT expiry is detected and returns 401 with a clear error code.
- Users can only access their own documents (ownership check).
- Admin users can access any document.

```
test("GET /documents returns 401 without Authorization header")
test("GET /documents/{other-user-id} returns 403 for non-admin")
test("expired JWT returns 401 with code TOKEN_EXPIRED")
```

---

### 6. API Endpoints (Integration Tests)

**Gap**: No API-level integration tests.

Proposed tests:
- Happy-path request/response shapes match the documented API contract.
- Invalid input (bad JSON, missing required fields) returns 400 with a validation error body.
- Rate limiting returns 429 with a `Retry-After` header.
- Large payloads are rejected with 413.
- Error responses always follow a consistent shape `{ error: { code, message } }`.

```
test("POST /documents with valid payload returns 201 with document ID")
test("POST /documents without required 'file' field returns 400")
test("response error bodies conform to { error: { code, message } } schema")
```

---

### 7. End-to-End (E2E)

**Gap**: No E2E tests covering the full user journey.

Proposed critical paths:
- **Upload flow**: user logs in → uploads a file → sees it in the gallery.
- **Search flow**: user searches by keyword → result list updates → user opens a document.
- **Delete flow**: user deletes a document → it disappears from the gallery.
- **Auth flow**: unauthenticated user is redirected to login.

E2E tests are expensive; keep the suite small and focused on critical paths only.

---

## Recommended Tooling

| Concern | Recommended Tool |
|---|---|
| Unit / component tests | Jest + React Testing Library (if React) |
| API integration tests | Supertest (Node) / pytest + httpx (Python) |
| E2E tests | Playwright |
| Coverage reporting | Istanbul / c8 (JS), coverage.py (Python) |
| Coverage enforcement | CI gate: fail below 80% line coverage |

---

## Prioritization

| Priority | Area | Rationale |
|---|---|---|
| **P0** | Auth & authorization | Security-critical; failures expose user data |
| **P0** | File ingestion validation | Corrupt/malicious input can crash the system |
| **P1** | API contract tests | Prevents regressions in the public interface |
| **P1** | Storage CRUD | Data integrity is core to the product |
| **P2** | Image processing units | Regressions are subtle and hard to debug manually |
| **P2** | Gallery UI components | User-facing quality; caught late without tests |
| **P3** | E2E critical paths | High value, but expensive to maintain |

---

## Next Steps

1. Choose and configure a test runner (`jest`, `vitest`, `pytest`, etc.) with coverage thresholds.
2. Add a CI step that runs tests and fails if coverage drops below the target.
3. Write P0 tests as part of the first feature implementation — not after.
4. Review this document as modules are built and check items off as coverage is achieved.
