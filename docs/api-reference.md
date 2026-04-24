# API Reference

Base URL: `/api`

## Health Check

```
GET /api/health
```

Returns `{"status": "ok", "app": "strategist-cockpit"}`.

---

## Engagements

### List Engagements

```
GET /api/engagements/?fy=FY26&engagement_type=Focus&status=Ongoing&customer=boerse
```

All query parameters are optional.

**Response**: `Engagement[]`

### Get Engagement

```
GET /api/engagements/{engagement_id}
```

**Response**: `Engagement`
**Errors**: 404 if not found.

### Create Engagement

```
POST /api/engagements/
Content-Type: application/json

{
  "customer": "Deutsche Boerse",
  "engagement_title": "AI-centered stock exchange",
  "engagement_type": "Focus",
  "status": "Ongoing",
  "fy": "FY26",
  "quarter": "FY26Q1",
  "ae": "John Smith"
}
```

`customer` is required; all other fields are optional.

**Response**: `Engagement` (201 Created)

### Update Engagement

```
PUT /api/engagements/{engagement_id}
Content-Type: application/json

{
  "status": "Completed",
  "next_steps": "Handoff to account team"
}
```

Only provided fields are updated (partial update).

**Response**: `Engagement`
**Errors**: 404 if not found.

### Delete Engagement

```
DELETE /api/engagements/{engagement_id}
```

**Response**: 204 No Content
**Errors**: 404 if not found.

---

## Projects

### List Projects

```
GET /api/projects/
```

Returns all projects ordered by creation date (newest first).

**Response**: `Project[]`

### Create Project

```
POST /api/projects/
Content-Type: application/json

{
  "name": "Systems of Intelligence",
  "url": "https://docs.google.com/...",
  "description": "Strategic framework presentation",
  "category": "Presentation"
}
```

`name` and `url` are required.

**Response**: `Project` (201 Created)

### Delete Project

```
DELETE /api/projects/{project_id}
```

**Response**: 204 No Content
**Errors**: 404 if not found.

---

## Canvas

### Get Canvas Summary

```
GET /api/canvas/summary/{activity_id}
```

Returns engagement counts and recent engagements matched by keyword relevance to the specified canvas activity.

Activity IDs: `c-level-vision-setting`, `data-ai-strategy`, `strategic-hunting`, `elevate-the-pitch`, `targeted-customer-engagements`, `measuring-success`, `champion-building`, `focused-account-planning`, `customer-mobilization`, `adoption-frameworks`, `community-seeding`, `individual-coaching`, `events`, `market-scouting`, `strategist-role`, `strategy-cop`, `reusable-strategy-assets`, `strategy-research`.

**Response**:
```json
{
  "activity": "data-ai-strategy",
  "engagement_count": 5,
  "accounts": ["Deutsche Boerse", "E.ON"],
  "recent_engagements": [...]
}
```

---

## Chat

### Send Chat Message

```
POST /api/chat/
Content-Type: application/json

{
  "message": "What are my focus accounts?"
}
```

Routes to Databricks Knowledge Assistant if `STRATEGO_ENDPOINT_NAME` is configured, otherwise uses keyword-based fallback.

**Response**:
```json
{
  "response": "Focus engagements are multi-quarter...",
  "source": "stratego"
}
```

---

## Data Types

### Engagement

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | integer | auto | Primary key |
| customer | string (≤255) | yes | Account/customer name |
| engagement_title | string (≤500) | no | Description of the engagement |
| engagement_type | enum | no | `Focus` / `One-off` / `Customer Event` / `Tbc` |
| status | enum | no | `Completed` / `Ongoing` / `Abandoned` / `Not started` / `On hold` |
| fy | string (`^FY\d{2}$`) | no | Fiscal year, e.g. `FY26` |
| quarter | string (≤100) | no | Quarter(s), e.g. `FY26Q1, FY26Q2` |
| ae | string (≤255) | no | Account Executive name |
| asq_id | string (≤100) | no | Salesforce ASQ identifier |
| asq_url | http(s) URL (≤1000) | no | Link to ASQ in Salesforce |
| uco_ids | string (≤500) | no | Comma-separated Salesforce UCO IDs, e.g. `UCO-1234, UCO-5678` |
| timeframe | string (≤255) | no | Human-readable timeframe |
| actionable_outcome | string (≤4000) | no | Key outcomes/deliverables |
| next_steps | string (≤4000) | no | Follow-up actions |
| related_documents | string (≤4000) | no | Links to related materials |

Invalid payloads return `422` (e.g. wrong enum value, malformed URL, oversized string).

### Project

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | integer | auto | Primary key |
| name | string | yes | Project name |
| url | string | yes | Link to the resource |
| description | string | no | Brief description |
| thumbnail_url | string | no | Preview image URL |
| category | string | no | "Presentation", "Application", "Document", "Other" |
| created_at | datetime | auto | Creation timestamp |
