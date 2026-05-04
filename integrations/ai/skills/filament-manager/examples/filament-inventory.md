# Filament Inventory Example

User: 哪些耗材快用完了？

Recommended flow:

1. Call `get_filament_inventory_summary`.
2. Call `list_filament_spools` with an appropriate filter if details are needed.
3. Call `find_filament_anomalies` when the question is about AMS mismatch or review-needed spools.

Response should include:

- Material, brand, color, remaining amount, and safe location label.
- Whether a spool needs review.
- Manual frontend actions such as confirming a spool or preparing a replacement.

Do not include RFID UID, `tag_uid`, `tray_uuid`, `identity_key`, raw AMS data, or write payloads.
