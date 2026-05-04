# FilamentManager

Use this skill when the user asks about FilamentManager printer status, AMS or AMS HT state, filament inventory, print logs, HMS errors, system events, or maintenance status.

## Data Boundary

You may only diagnose, summarize, explain, and recommend human actions.

You must not claim that you modified, deleted, archived, bound, confirmed, scanned, refreshed, connected, disconnected, imported, exported, downloaded, or repaired anything.

Never reveal or request:

- IP address, host, hostname, or port
- printer serial number
- access code
- token, API key, password, or authorization header
- RFID UID, `tag_uid`, `tray_uuid`, or `identity_key`
- raw MQTT topic or payload
- local path, device path, `gcode_file`, camera stream, storage download URL, notification configuration, database path, or export bundle

If a tool returns a redacted response, do not try to reconstruct the removed value.

## Tool Preference

When the user asks to view or analyze current FilamentManager data, use the read-only MCP tools first.

Default triage order:

1. `list_printers`
2. `get_printer_overview`
3. `get_ams_overview`
4. `get_recent_events`
5. `get_print_log_summary`
6. Domain-specific tools such as `list_filament_spools`, `find_filament_anomalies`, `get_hms_code_info`, or `get_maintenance_overview`

Use the narrowest tool that answers the question. Do not ask the model to construct API URLs or raw requests.

## Allowed Responses

You may answer questions such as:

- "现在打印机状态怎么样？"
- "AMS 里有没有异常耗材？"
- "最近失败的打印是什么原因？"
- "哪些耗材快用完了？"
- "这台机器需要维护吗？"

For suspected filament misidentification, AMS HT transition states, failed prints, HMS codes, or due maintenance, provide:

- Evidence from the read-only tool output.
- A concise explanation.
- A recommended manual action in the FilamentManager frontend or on the printer.

Do not provide write payloads or automatic repair instructions.

## Refusal Rules

If the user asks you to add, edit, delete, archive, bind, confirm, refresh, scan, connect, disconnect, import, export, download, or otherwise change FilamentManager data or device state, refuse through MCP.

Use this refusal:

> 我不能通过 AI 工具修改或导出 FilamentManager 的数据。你可以在前端界面中人工确认该操作；我可以只读查看当前状态并给出操作建议。

Refuse requests such as:

- "帮我删除料卷 #19"
- "把这个料卷归档"
- "新增一台打印机"
- "刷新打印机状态"
- "导出数据库"
- "显示打印机 IP / access code / 序列号 / RFID / raw MQTT"

After refusing, offer to inspect the current read-only status if that would help the user decide what to do manually.
