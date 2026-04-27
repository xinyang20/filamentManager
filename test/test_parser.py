from __future__ import annotations

import json

from filament_manager.mqtt.parser import extract_command, identify_tray, parse_ams_units


def test_tray_uuid_identity_takes_priority() -> None:
    identity = identify_tray(
        {
            "tray_uuid": "11111111-2222-3333-4444-555555555555",
            "tag_uid": "TAGUID123",
        }
    )

    assert identity.identity_source == "tray_uuid"
    assert identity.identity_key == "bambu:tray_uuid:11111111-2222-3333-4444-555555555555"
    assert identity.identity_confidence == 1.0
    assert identity.identity_warning is None


def test_invalid_tray_uuid_falls_back_to_tag_uid() -> None:
    identity = identify_tray(
        {
            "tray_uuid": "00000000-0000-0000-0000-000000000000",
            "tag_uid": "TAGUID123",
        }
    )

    assert identity.identity_source == "tag_uid"
    assert identity.identity_key == "bambu:tag_uid:TAGUID123"
    assert identity.identity_warning == "tray_uuid_invalid_tag_uid_fallback"


def test_missing_identity_requires_manual_binding() -> None:
    identity = identify_tray({"tray_uuid": "", "tag_uid": ""})

    assert identity.identity_source == "manual_required"
    assert identity.identity_key is None
    assert identity.identity_confidence == 0.0


def test_remain_minus_one_marks_transition_without_inventory_signal(fixture_dir) -> None:
    payload = json.loads((fixture_dir / "push_status_remain_unavailable.json").read_text())

    units = parse_ams_units(payload)
    slot = units[0].slots[0]

    assert slot.remain == -1
    assert slot.is_transitioning is True
    assert "remain_unavailable" in (slot.identity.identity_warning or "")


def test_extract_command_supports_info_and_system_sections() -> None:
    assert extract_command({"info": {"command": "get_version"}}) == "get_version"
    assert extract_command({"system": {"command": "get_accessories"}}) == "get_accessories"
    assert extract_command({"pushing": {"command": "pushall"}}) == "pushall"
