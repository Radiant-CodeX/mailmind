# MailMind Processing Contracts v1.0

## Purpose

This document defines the standard data contracts between all stages of the MailMind processing pipeline. Every service must adhere to these contracts to ensure interoperability and independent development.

---

# Pipeline Overview

```text
Document / Email
        ↓
Stage 1: Ingestion
        ↓
Stage 2: PII Detection & Masking (Presidio)
        ↓
Stage 3: AI Analysis & Extraction
        ↓
Stage 4: Persistence
```

---

# General Principles

1. Every document must have a unique `document_id`.
2. Each stage must preserve the `document_id`.
3. Stages must never modify outputs from previous stages except where explicitly defined.
4. Errors must follow the standardized error contract.
5. Services should validate incoming payloads before processing.

---

# Common Metadata Contract

## Purpose

Metadata shared across all stages.

## Schema

| Field             | Type     | Required | Description                |
| ----------------- | -------- | -------- | -------------------------- |
| document_id       | string   | Yes      | Unique document identifier |
| timestamp         | datetime | Yes      | Processing timestamp       |
| source            | string   | Yes      | Source type                |
| processing_status | string   | Yes      | success or error           |

## Example

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-06-04T12:00:00Z",
  "source": "email",
  "processing_status": "success"
}
```

---

# Stage 1: Ingestion Contract

## Responsibility

- Receive document or email
- Extract raw text
- Generate document identifier
- Extract source metadata

## Supported Sources (v1)

- Email
- PDF
- DOCX
- TXT

## Output Schema

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "source": "email",
  "content": "Hello, my name is John Doe. My phone number is 9876543210.",
  "metadata": {
    "sender": "john@example.com",
    "subject": "Support Request",
    "received_at": "2026-06-04T12:00:00Z"
  }
}
```

## Required Fields

| Field       | Type   |
| ----------- | ------ |
| document_id | string |
| source      | string |
| content     | string |
| metadata    | object |

---

# Stage 2: PII Detection & Masking Contract

## Responsibility

- Detect personally identifiable information
- Mask detected entities
- Return entity metadata

## Input

Stage 1 Output

## Output Schema

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "masked_content": "Hello, my name is [PERSON]. My phone number is [PHONE_NUMBER].",
  "entities": [
    {
      "entity_type": "PERSON",
      "start": 18,
      "end": 26,
      "score": 0.99,
      "original_value": "John Doe"
    },
    {
      "entity_type": "PHONE_NUMBER",
      "start": 47,
      "end": 57,
      "score": 0.97,
      "original_value": "9876543210"
    }
  ]
}
```

## Entity Schema

| Field          | Type    |
| -------------- | ------- |
| entity_type    | string  |
| start          | integer |
| end            | integer |
| score          | float   |
| original_value | string  |

## Required Fields

| Field          | Type   |
| -------------- | ------ |
| document_id    | string |
| masked_content | string |
| entities       | array  |

---

# Stage 3: AI Analysis Contract

## Responsibility

- Document classification
- Information extraction
- Summarization
- Risk assessment

## Input

Stage 2 Output

## Output Schema

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "classification": {
    "category": "Customer Support",
    "confidence": 0.96
  },
  "summary": "Customer requesting support regarding account access issue.",
  "extracted_entities": {
    "issue_type": "Account Access",
    "priority": "Medium"
  },
  "risk_score": 0.12
}
```

## Classification Schema

| Field      | Type   |
| ---------- | ------ |
| category   | string |
| confidence | float  |

## Required Fields

| Field              | Type   |
| ------------------ | ------ |
| document_id        | string |
| classification     | object |
| summary            | string |
| extracted_entities | object |
| risk_score         | float  |

---

# Stage 4: Persistence Contract

## Responsibility

Store the complete processing lifecycle and final results.

## Storage Object

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "raw_content": "original content",
  "masked_content": "masked content",
  "detected_entities": [],
  "classification": {},
  "summary": "summary text",
  "extracted_entities": {},
  "risk_score": 0.12,
  "created_at": "2026-06-04T12:00:00Z"
}
```

---

# Standard Error Contract

All services must return errors in a consistent format.

## Error Schema

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "error",
  "error": {
    "code": "PII_DETECTION_FAILED",
    "message": "Unable to process document."
  }
}
```

## Error Fields

| Field         | Type   |
| ------------- | ------ |
| document_id   | string |
| status        | string |
| error.code    | string |
| error.message | string |

---

# Validation Rules

## document_id

- Must be UUID format
- Must remain unchanged across all stages

## risk_score

- Minimum: 0.0
- Maximum: 1.0

## confidence

- Minimum: 0.0
- Maximum: 1.0

## content

- Cannot be null
- Empty string allowed only for unsupported document types

---

# Versioning

Current Version: **v1.0**

Future contract changes must:

1. Increment contract version.
2. Maintain backward compatibility where possible.
3. Be reviewed by all pipeline owners.

---

# Ownership

| Stage                   | Owner  |
| ----------------------- | ------ |
| Ingestion               | Team A |
| PII Detection & Masking | Team B |
| AI Analysis             | Team C |
| Persistence & APIs      | Team D |

---

# Approval Checklist

- [ ] Ingestion Team Approved
- [ ] Presidio Team Approved
- [ ] AI Processing Team Approved
- [ ] Backend Team Approved
- [ ] Integration Review Complete
- [ ] Contract Version Tagged
