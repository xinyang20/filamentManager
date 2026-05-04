# FilamentManager AI Integrations

This directory contains a read-only AI access layer for FilamentManager.

The integration has two parts:

- `mcp/`: an MCP server that exposes structured, read-only diagnostic tools.
- `skills/filament-manager/`: usage rules for AI assistants working with FilamentManager data.

It is not a backup tool, export tool, management backend, or automatic repair agent.

## Safety Boundary

The MCP server only reads from the existing FilamentManager backend `/api` endpoints. It does not import backend services, does not open a database session, and does not read local configuration files such as `.env`.

Allowed behavior:

- Summarize printer, AMS, filament, print log, event, HMS, and maintenance status.
- Explain likely causes and give human action recommendations.
- Return internal object identifiers such as `printer_id` and `spool_id` when needed for diagnosis.

Forbidden behavior:

- Create, edit, delete, archive, bind, confirm, import, export, scan, refresh, connect, disconnect, or download anything.
- Call any `POST`, `PATCH`, `PUT`, or `DELETE` endpoint.
- Return IP addresses, hosts, serial numbers, access codes, tokens, RFID/UID values, raw MQTT payloads, local paths, camera streams, storage download URLs, notification configuration, or export bundles.

## Transport Allowlist

The HTTP client is hard-wired to `GET` requests against a fixed path allowlist:

- `/api/health`
- `/api/printers`
- `/api/printers/{id}/dashboard`
- `/api/printers/{id}/ams/overview`
- `/api/filament/inventory/summary`
- `/api/filament/spools`
- `/api/print-log`
- `/api/print-log/summary`
- `/api/print-log/analytics`
- `/api/events`
- `/api/hms/codes/{short_code}`
- `/api/hms/codes/{short_code}/stats`
- `/api/maintenance/overview`
- `/api/printers/{id}/maintenance`

There is no generic API request tool. Models cannot provide arbitrary URLs, paths, methods, or headers.

## Redaction Strategy

Every tool builds a safe response object from an explicit field allowlist. Before the response leaves the MCP layer, it is passed through `redact_for_ai()` as a second safety pass.

High-risk keys are removed entirely. Sensitive value patterns such as private IPs, local paths, authorization strings, serial-like identifiers, UUID/RFID-like identifiers, and private URLs are replaced with `[redacted]`.

## Local Startup

From the repository root:

```bash
uv run --project integrations/ai/mcp filament-manager-mcp
```

Configuration is via environment variables:

- `FILAMENT_MANAGER_API_BASE_URL`: defaults to `http://127.0.0.1:8000/api`
- `FILAMENT_MANAGER_MCP_TIMEOUT_SECONDS`: defaults to `5`
- `FILAMENT_MANAGER_MCP_MAX_ITEMS`: defaults to `100`

The first version assumes a trusted local backend. It does not forward authentication or read local secrets.

## FAQ

**Can this modify FilamentManager data?**  
No. The MCP server exposes no write tools and the client refuses every non-GET method.

**Can this refresh printer status or scan storage?**  
No. Those endpoints can create device or network side effects and are intentionally forbidden.

**Can this show access codes, IPs, serial numbers, RFID values, raw MQTT, or file paths?**  
No. Those values are outside the AI data boundary and are removed or redacted.

**Can this export the database or generate a support bundle?**  
No. Export, import, debug, notification, camera, storage download, and support bundle endpoints are not exposed.
