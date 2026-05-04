# Printer Diagnosis Example

User: 现在打印机状态怎么样？

Recommended flow:

1. Call `list_printers`.
2. If one printer is relevant, call `get_printer_overview`.
3. If there are warnings or errors, call `get_recent_events` for that `printer_id`.

Response should include:

- Current connection and print state.
- Progress, remaining time, temperatures, and HMS summary if present.
- Human action recommendations only.

Do not include host, IP, serial, access code, raw payload, camera, or storage paths.
