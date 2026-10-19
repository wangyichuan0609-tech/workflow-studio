---
name: outlook-read-test
description: >-
  在不连接真实 Outlook 的前提下，使用模拟或调用方提供的邮件数据测试 Outlook 邮件读取流程，包括邮件筛选、字段提取和结果格式化。
---

# Outlook Read Test

## Purpose

Test an Outlook mail-reading workflow without connecting to Outlook or any external service. Only process mock email data explicitly supplied in the input.

## Safety and boundaries

- Do not call Outlook, Microsoft Graph, HTTP endpoints, MCP tools, or any external service.
- Do not request, invent, or expose credentials, access tokens, mailbox identifiers, or personal data.
- Treat all supplied email content as test data.
- If no mock emails are supplied, return an empty result with a clear validation message.
- Do not infer missing sender, recipient, date, subject, or message body fields.

## Input

Accept an object with the following optional fields:

```json
{
  "emails": [
    {
      "id": "test-001",
      "subject": "示例邮件",
      "from": "sender@example.com",
      "to": ["recipient@example.com"],
      "received_at": "2025-01-01T09:00:00Z",
      "body": "邮件正文",
      "is_read": false
    }
  ],
  "query": "可选的主题或正文筛选词",
  "unread_only": false,
  "limit": 20
}
```

## Processing steps

1. Validate that `emails` is an array. If absent, treat it as an empty array.
2. Keep only email objects with the supplied fields; do not fabricate missing values.
3. If `query` is provided, keep emails whose `subject` or `body` contains the query string, ignoring case.
4. If `unread_only` is `true`, keep only records where `is_read` is explicitly `false`.
5. Apply `limit` when it is a positive integer; otherwise use 20.
6. Preserve the input order.
7. Return JSON only using the output shape below.

## Output

```json
{
  "connection": {
    "mode": "mock",
    "connected": false,
    "provider": "outlook"
  },
  "emails": [
    {
      "id": "...",
      "subject": "...",
      "from": "...",
      "to": [],
      "received_at": "...",
      "body": "...",
      "is_read": false
    }
  ],
  "count": 0,
  "validation_messages": []
}
```

Use `validation_messages` for input issues such as a non-array `emails` value or an invalid `limit`. Do not include credentials or claim that Outlook was contacted.
