# Config Management API Contract

**Branch**: `006-llm-config-management` | **Date**: 2026-06-14

**Base Path**: `/api/config`

**Auth**: All endpoints require `Authorization: Bearer <token>` with admin role.

---

## 1. Get All Configs

`GET /api/config`

Returns all configuration items grouped by service category.

**Response 200**:
```json
{
  "categories": [
    {
      "category": "llm",
      "label": "LLM 大模型服务",
      "description": "配置大模型 API 连接参数",
      "icon": "robot",
      "items": [
        {
          "key": "llm.api_key",
          "display_value": "sk-****abcd",
          "value_type": "password",
          "label": "LLM API Key",
          "description": "OpenAI 兼容 API 的访问密钥",
          "is_sensitive": true,
          "is_required": true,
          "default_value": null,
          "choices": [],
          "min_val": null,
          "max_val": null,
          "sort_order": 1,
          "group": "connection",
          "has_value": true
        }
      ],
      "connection_status": "connected",
      "last_tested_at": "2026-06-14T12:00:00",
      "last_error": null
    }
  ]
}
```

**Response 403**: Non-admin user
```json
{"detail": "Admin role required"}
```

---

## 2. Get Configs by Category

`GET /api/config/{category}`

Returns configuration items for a specific service category.

**Path Params**: `category` — one of `llm`, `graph_db`, `object_storage`, `search`, `policy_engine`, `cache`, `auth`, `general`

**Response 200**: Same structure as single category in GET /api/config

**Response 404**: Unknown category
```json
{"detail": "Unknown category: xyz"}
```

---

## 3. Update Configs

`PUT /api/config`

Batch update configuration items. All-or-nothing: if validation fails for any item, no changes are saved.

**Request Body**:
```json
{
  "items": [
    {
      "key": "llm.api_key",
      "value": "sk-new-key-here"
    },
    {
      "key": "llm.model",
      "value": "gpt-4o"
    }
  ],
  "test_connection": true
}
```

**Response 200** (success with connection test):
```json
{
  "status": "success",
  "saved_count": 2,
  "revision_number": 42,
  "validation_results": [
    {
      "category": "llm",
      "success": true,
      "message": "Connection successful",
      "response_time_ms": 850
    }
  ]
}
```

**Response 400** (validation failed):
```json
{
  "status": "validation_failed",
  "saved_count": 0,
  "validation_results": [
    {
      "category": "llm",
      "success": false,
      "message": "API Key invalid: 401 Unauthorized",
      "response_time_ms": 1200
    }
  ]
}
```

**Response 422** (schema validation error):
```json
{
  "detail": [
    {
      "loc": ["items", 0, "key"],
      "msg": "Unknown config key: llm.invalid_key",
      "type": "value_error"
    }
  ]
}
```

---

## 4. Test Connection

`POST /api/config/test`

Test connection for one or more service categories using current or provided config values.

**Request Body**:
```json
{
  "categories": ["llm", "graph_db"],
  "items": [
    {"key": "llm.api_key", "value": "sk-test-key"}
  ]
}
```

If `items` is provided, use those values for testing instead of saved values. If `categories` is empty, test all configured categories.

**Response 200**:
```json
{
  "results": [
    {
      "category": "llm",
      "success": true,
      "message": "Connection successful",
      "response_time_ms": 850,
      "tested_at": "2026-06-14T12:00:00"
    },
    {
      "category": "graph_db",
      "success": false,
      "message": "Connection refused: bolt://localhost:7687",
      "response_time_ms": 5000,
      "tested_at": "2026-06-14T12:00:00"
    }
  ]
}
```

---

## 5. Get Config History

`GET /api/config/history`

Returns configuration change history.

**Query Params**:
- `category` (optional): Filter by service category
- `limit` (default: 50): Max records to return
- `offset` (default: 0): Pagination offset

**Response 200**:
```json
{
  "revisions": [
    {
      "id": "rev-uuid-1",
      "revision_number": 42,
      "operator_id": "user-123",
      "operator_name": "admin",
      "changed_at": "2026-06-14T12:00:00",
      "changes": [
        {
          "key": "llm.model",
          "old_value": "gpt-4",
          "new_value": "gpt-4o",
          "is_sensitive": false
        },
        {
          "key": "llm.api_key",
          "old_value": "****efgh",
          "new_value": "****abcd",
          "is_sensitive": true
        }
      ]
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

---

## 6. Rollback Config

`POST /api/config/rollback`

Rollback configuration to a specific revision.

**Request Body**:
```json
{
  "revision_number": 41
}
```

**Response 200**:
```json
{
  "status": "success",
  "rolled_back_to": 41,
  "new_revision_number": 43,
  "changes": [
    {
      "key": "llm.model",
      "old_value": "gpt-4o",
      "new_value": "gpt-4",
      "is_sensitive": false
    }
  ]
}
```

**Response 404**: Revision not found
```json
{"detail": "Revision 999 not found"}
```

---

## 7. Export Configs

`GET /api/config/export`

Export all configuration items. Sensitive values are replaced with placeholders.

**Response 200**:
```json
{
  "exported_at": "2026-06-14T12:00:00",
  "version": "1.0",
  "items": [
    {
      "key": "llm.api_key",
      "value": "***REDACTED***",
      "value_type": "password",
      "category": "llm"
    },
    {
      "key": "llm.model",
      "value": "gpt-4o",
      "value_type": "string",
      "category": "llm"
    }
  ]
}
```

---

## 8. Import Configs

`POST /api/config/import`

Import configuration items. Sensitive fields with placeholder values are skipped.

**Request Body**:
```json
{
  "items": [
    {"key": "llm.model", "value": "gpt-4o"},
    {"key": "llm.api_key", "value": "***REDACTED***"}
  ]
}
```

**Response 200**:
```json
{
  "status": "success",
  "imported_count": 1,
  "skipped_count": 1,
  "skipped_keys": ["llm.api_key"],
  "revision_number": 44
}
```

---

## 9. Get Config Value (Internal API)

`GET /api/config/value/{key}`

Get the decrypted value of a specific config key. Used by internal services, not exposed to frontend.

**Path Params**: `key` — dot-notation config key (e.g., `llm.api_key`)

**Response 200**:
```json
{
  "key": "llm.api_key",
  "value": "sk-actual-key-value",
  "source": "db"
}
```

**Response 404**: Key not found
```json
{"detail": "Config key not found: llm.invalid"}
```

**Note**: This endpoint is for internal service-to-service calls. It returns decrypted values and must never be exposed to the frontend.
