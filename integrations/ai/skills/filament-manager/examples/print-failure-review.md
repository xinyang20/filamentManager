# Print Failure Review Example

User: 最近失败的打印是什么原因？

Recommended flow:

1. Call `list_printers` if the printer is ambiguous.
2. Call `list_recent_print_logs` with `status="failed"`.
3. Call `get_print_log_summary`.
4. If an HMS code appears, call `get_hms_code_info`.
5. Call `get_recent_events` for nearby warnings if needed.

Response should include:

- Failed print display name, final progress, layer, failure reason, and HMS summary.
- A human-readable interpretation of repeated failure patterns.
- Manual next steps in the frontend or on the printer.

Do not include `task_id`, `project_id`, `profile_id`, `gcode_file`, local paths, raw refs, or raw MQTT.
