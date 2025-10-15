# AI Chat History Persistence: Summary & Guide

## Overview

This system allows AI chat history to be persisted for each user (and tenant, if multitenant) for a configurable period (default 7 days, up to 30 days). The retention period is configurable per tenant via settings. The frontend fetches and displays chat history, and shows a notice about how long history is kept.

---

## Backend Implementation

- **Database Model:**
  - `AIChatHistory` table stores each chat message with `user_id`, `tenant_id`, `message`, `sender`, and `created_at`.
- **Retention Setting:**
  - `ai_chat_history_retention_days` field in the `Settings` model/table (default 7, max 30).
- **API Endpoints:**
  - `POST /ai/chat/message`: Save a chat message (user or AI).
  - `GET /ai/chat/history`: Fetch chat history for the user, filtered by the retention period. Also purges old messages.
- **Automatic Purge:**
  - Old messages are deleted each time history is fetched, based on the retention period.

---

## Frontend Integration

- **Fetch History:**
  - On AI chat open, the frontend calls `/ai/chat/history` and displays the messages in the chat window.
- **Retention Notice:**
  - The frontend displays a notice: “Chat history is kept for up to X days,” using the value from settings.
- **i18n:**
  - The retention notice is fully translatable.

---

## How to Change the Retention Period

- Update the `ai_chat_history_retention_days` field in the settings (per tenant or globally).
- The backend will automatically use this value for history fetch and purge.
- The frontend will display the updated value in the retention notice.

---

## Benefits
- **User Experience:** Users can see their recent AI chat history for context.
- **Compliance:** Data is not kept longer than necessary.
- **Configurable:** Each tenant can set their own retention period (within allowed range).
- **Internationalized:** All notices and messages are localized.

---

For more details, see the backend and frontend implementation in `api/routers/ai.py`, `models/models_per_tenant.py`, and `ui/src/components/AIAssistant.tsx`. 