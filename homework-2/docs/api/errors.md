# Error Reference

> Related: [README.md](README.md) · [endpoints.md](endpoints.md)

All error responses return JSON — never HTML. The shape depends on the error type.

---

## Status Codes

| Code | Name | Returned When |
|------|------|---------------|
| `400` | Bad Request | File is malformed and cannot be parsed at all |
| `404` | Not Found | No ticket exists with the given ID |
| `415` | Unsupported Media Type | Uploaded file is not `.csv`, `.json`, or `.xml` |
| `422` | Unprocessable Entity | Request body or query param fails Pydantic validation |
| `500` | Internal Server Error | Unexpected server-side error |

---

## 400 Bad Request — Malformed File

Returned when the uploaded file cannot be parsed (corrupt encoding, invalid XML structure, broken JSON).

```json
{"detail": "Cannot parse CSV file: ..."}
{"detail": "Cannot parse JSON file — invalid JSON (line 3, column 12): Expecting value"}
{"detail": "Cannot parse XML file — malformed XML: syntax error: line 5, column 0"}
```

---

## 404 Not Found

```json
{"detail": "Ticket '550e8400-e29b-41d4-a716-446655440000' not found"}
```

---

## 415 Unsupported Media Type

```json
{"detail": "Unsupported file type. Please upload a .csv, .json, or .xml file."}
```

---

## 422 Unprocessable Entity — Validation Failure

Generated automatically by FastAPI + Pydantic. Contains structured field-level detail.

```json
{
  "detail": [
    {
      "type":  "value_error",
      "loc":   ["body", "description"],
      "msg":   "Value error, description is too short (5 chars); min is 10",
      "input": "short",
      "ctx":   {}
    },
    {
      "type":  "missing",
      "loc":   ["body", "customer_email"],
      "msg":   "Field required",
      "input": {}
    }
  ]
}
```

`loc` is the path to the failing field: `["body", "field_name"]` for request body fields, `["query", "param_name"]` for query parameters.

**Common validation errors:**

| Trigger | `type` | Example `msg` |
|---------|--------|---------------|
| Description < 10 chars | `value_error` | `description is too short (5 chars); min is 10` |
| Subject > 200 chars | `value_error` | `subject is too long (205 chars); max is 200` |
| Invalid email | `value_error` | `value is not a valid email address` |
| Blank required field | `value_error` | `field must not be blank` |
| Invalid enum value | `enum` | `Input should be 'urgent', 'high', 'medium' or 'low'` |
| Missing required field | `missing` | `Field required` |

---

## 500 Internal Server Error

```json
{
  "error":  "Internal server error",
  "detail": "...",
  "path":   "http://localhost:8000/tickets"
}
```

---

## 207 Multi-Status — Partial Import

Not an error — but indicates partial success on `POST /tickets/import`. Some rows were saved, some failed. The full `ImportSummary` is returned so you can inspect exactly which rows failed and why.

```json
{
  "total":      10,
  "successful": 8,
  "failed":     2,
  "tickets":    ["..."],
  "errors": [
    {
      "row":      3,
      "raw_data": {"customer_email": "not-an-email", "subject": "Test issue"},
      "errors":   ["customer_email: value is not a valid email address"]
    },
    {
      "row":      7,
      "raw_data": {"customer_id": "", "subject": "Another issue"},
      "errors":   ["customer_id: field must not be blank"]
    }
  ]
}
```

See [models.md — ImportSummary](models.md#importsummary) for the full schema.
