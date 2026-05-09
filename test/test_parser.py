from __future__ import annotations

import json

from filament_manager.db.models import AmsSlot
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


def test_state_ten_without_filament_payload_is_transition() -> None:
    units = parse_ams_units(
        {
            "print": {
                "ams": {
                    "ams": [
                        {
                            "id": "0",
                            "tray": [{"id": "1", "state": 10}],
                        }
                    ]
                }
            }
        }
    )

    slot = units[0].slots[0]
    assert slot.is_transitioning is True
    assert slot.identity.identity_source == "manual_required"


def test_state_eleven_without_filament_payload_is_transition() -> None:
    units = parse_ams_units(
        {
            "print": {
                "ams": {
                    "ams": [
                        {
                            "id": "128",
                            "tray": [{"id": "0", "state": 11}],
                        }
                    ]
                }
            }
        }
    )

    slot = units[0].slots[0]
    assert slot.is_transitioning is True
    assert slot.identity.identity_source == "manual_required"


def test_ams_ht_state_eight_twenty_three_and_twenty_six_without_filament_payload_are_transitions() -> None:
    for state in (8, 23, 26):
        units = parse_ams_units(
            {
                "print": {
                    "ams": {
                        "ams": [
                            {
                                "id": "128",
                                "tray": [{"id": "0", "state": state}],
                            }
                        ]
                    }
                }
            }
        )

        slot = units[0].slots[0]
        assert slot.is_transitioning is True
        assert slot.identity.identity_source == "manual_required"

        model_slot = AmsSlot(printer_id=1, ams_id="128", tray_id="0", slot_state=str(state), raw={"state": state})
        assert model_slot.state_name == "transitioning"
        assert not model_slot.state_name.startswith("unknown:")


def test_state_ten_with_only_identity_is_transition() -> None:
    units = parse_ams_units(
        {
            "print": {
                "ams": {
                    "ams": [
                        {
                            "id": "0",
                            "tray": [
                                {
                                    "id": "1",
                                    "state": 10,
                                    "tray_uuid": "11111111-2222-3333-4444-555555555555",
                                    "tag_uid": "TAGUID123",
                                }
                            ],
                        }
                    ]
                }
            }
        }
    )

    slot = units[0].slots[0]
    assert slot.is_transitioning is True
    assert slot.identity.identity_source == "tray_uuid"


def test_state_ten_with_filament_payload_is_not_transition() -> None:
    units = parse_ams_units(
        {
            "print": {
                "ams": {
                    "ams": [
                        {
                            "id": "0",
                            "tray": [{"id": "1", "state": 10, "tray_type": "PLA", "tray_color": "FFFFFF"}],
                        }
                    ]
                }
            }
        }
    )

    assert units[0].slots[0].is_transitioning is False


def test_tray_id_name_extracts_readable_color_name() -> None:
    units = parse_ams_units(
        {
            "print": {
                "command": "push_status",
                "ams": {
                    "ams": [
                        {
                            "id": "0",
                            "tray": [
                                {
                                    "id": "0",
                                    "tray_uuid": "11111111-2222-3333-4444-555555555555",
                                    "tray_type": "PLA",
                                    "tray_sub_brands": "Basic",
                                    "tray_color": "A52A2A",
                                    "tray_id_name": "PLA Basic Cocoa Brown",
                                    "remain": 70,
                                }
                            ],
                        }
                    ]
                },
            }
        }
    )

    assert units[0].slots[0].color_name == "Cocoa Brown"


def test_tray_id_name_extracts_color_name_after_brand_prefix() -> None:
    units = parse_ams_units(
        {
            "print": {
                "ams": {
                    "ams": [
                        {
                            "id": "0",
                            "tray": [
                                {
                                    "id": "0",
                                    "tray_uuid": "11111111-2222-3333-4444-555555555555",
                                    "tray_type": "PLA",
                                    "tray_sub_brands": "Basic",
                                    "tray_color": "A52A2A",
                                    "tray_id_name": "Bambu PLA Basic Cocoa Brown",
                                }
                            ],
                        }
                    ]
                },
            }
        }
    )

    assert units[0].slots[0].color_name == "Cocoa Brown"


def test_code_like_tray_id_name_is_not_treated_as_color_name() -> None:
    units = parse_ams_units(
        {
            "print": {
                "ams": {
                    "ams": [
                        {
                            "id": "0",
                            "tray": [
                                {
                                    "id": "0",
                                    "tray_uuid": "11111111-2222-3333-4444-555555555555",
                                    "tray_type": "PLA",
                                    "tray_color": "A52A2A",
                                    "tray_id_name": "A00-K00",
                                }
                            ],
                        }
                    ]
                },
            }
        }
    )

    assert units[0].slots[0].color_name is None


def test_extract_command_supports_info_and_system_sections() -> None:
    assert extract_command({"info": {"command": "get_version"}}) == "get_version"
    assert extract_command({"system": {"command": "get_accessories"}}) == "get_accessories"
    assert extract_command({"pushing": {"command": "pushall"}}) == "pushall"
