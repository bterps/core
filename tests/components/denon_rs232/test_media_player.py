"""Tests for the Denon RS232 media player platform."""

import json
from pathlib import Path

from denon_rs232 import InputSource, ZoneState
import pytest

from homeassistant.components.denon_rs232.media_player import (
    INPUT_SOURCE_DENON_TO_HA,
    async_setup_entry as async_setup_media_player_entry,
)
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import _default_state

ENTITY_ID = "media_player.avr_3805_avc_3890"
ZONE2_ENTITY_ID = "media_player.avr_3805_avc_3890_zone_2"
ZONE3_ENTITY_ID = "media_player.avr_3805_avc_3890_zone_3"
STRINGS_PATH = Path("homeassistant/components/denon_rs232/strings.json")


@pytest.fixture(autouse=True)
async def auto_init_components(init_components) -> None:
    """Set up the component."""


async def test_entity_created(hass: HomeAssistant) -> None:
    """Test media player entity is created with correct state."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_zone_entities_created(hass: HomeAssistant) -> None:
    """Test Zone 2 and Zone 3 entities are created."""
    zone2 = hass.states.get(ZONE2_ENTITY_ID)
    zone3 = hass.states.get(ZONE3_ENTITY_ID)

    assert zone2 is not None
    assert zone3 is not None
    assert zone2.state == STATE_ON
    assert zone3.state == STATE_OFF


async def test_async_setup_entry_skips_empty_zone_states(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test platform setup only creates zone entities with queried state."""
    state = _default_state()
    state.zone2 = ZoneState()
    state.zone3 = ZoneState()
    mock_receiver.state = state
    mock_config_entry.runtime_data = mock_receiver

    added_entities = []
    await async_setup_media_player_entry(hass, mock_config_entry, added_entities.extend)

    assert len(added_entities) == 1
    assert added_entities[0].unique_id == f"{mock_config_entry.entry_id}_main"


async def test_setup_queries_initial_state(mock_receiver) -> None:
    """Test integration setup explicitly queries initial receiver state."""
    mock_receiver.query_state.assert_awaited_once()


async def test_state_on(hass: HomeAssistant) -> None:
    """Test state is ON when receiver is powered on."""
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_state_off(hass: HomeAssistant, mock_receiver) -> None:
    """Test state is OFF when receiver is in standby."""
    new_state = _default_state()
    new_state.power = False
    mock_receiver.mock_state(new_state)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def test_volume_level(hass: HomeAssistant) -> None:
    """Test volume level is correctly converted from dB to 0..1."""
    # -30 dB: ((-30) - (-80)) / 90 = 50 / 90 ≈ 0.5555
    state = hass.states.get(ENTITY_ID)
    volume = state.attributes[ATTR_MEDIA_VOLUME_LEVEL]
    assert abs(volume - 50.0 / 90.0) < 0.001


async def test_mute_state(hass: HomeAssistant) -> None:
    """Test mute state is reported."""
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False


async def test_source(hass: HomeAssistant) -> None:
    """Test current source is reported."""
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_INPUT_SOURCE] == "cd"


async def test_source_net(hass: HomeAssistant, mock_receiver) -> None:
    """Test NET source is reported with the translation key."""
    new_state = _default_state()
    new_state.input_source = InputSource.NET
    mock_receiver.mock_state(new_state)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_INPUT_SOURCE] == "net"


async def test_source_bluetooth(hass: HomeAssistant, mock_receiver) -> None:
    """Test BT source is reported with the translation key."""
    new_state = _default_state()
    new_state.input_source = InputSource.BT
    mock_receiver.mock_state(new_state)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_INPUT_SOURCE] == "bt"


async def test_source_list(hass: HomeAssistant) -> None:
    """Test source list comes from the model definition."""
    state = hass.states.get(ENTITY_ID)
    source_list = state.attributes[ATTR_INPUT_SOURCE_LIST]
    assert "cd" in source_list
    assert "dvd" in source_list
    assert "tuner" in source_list
    assert source_list == sorted(source_list)


async def test_sound_mode_not_exposed(hass: HomeAssistant) -> None:
    """Test surround mode is not exposed in Home Assistant."""
    state = hass.states.get(ENTITY_ID)
    assert "sound_mode" not in state.attributes
    assert "sound_mode_list" not in state.attributes


def test_input_source_translation_keys_cover_all_enum_members() -> None:
    """Test all input sources have a declared translation key."""
    assert set(INPUT_SOURCE_DENON_TO_HA) == set(InputSource)

    # Verify that all translation keys exist in the strings.json file
    strings = json.loads(STRINGS_PATH.read_text("utf-8"))
    assert set(INPUT_SOURCE_DENON_TO_HA.values()) == set(
        strings["entity"]["media_player"]["receiver"]["state_attributes"]["source"][
            "state"
        ]
    )


async def test_turn_on(hass: HomeAssistant, mock_receiver) -> None:
    """Test turning on the receiver."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_receiver.power_on.assert_awaited_once()


async def test_zone2_turn_on(hass: HomeAssistant, mock_receiver) -> None:
    """Test turning on Zone 2."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ZONE2_ENTITY_ID},
        blocking=True,
    )
    mock_receiver.zone2_power_on.assert_awaited_once()


async def test_turn_off(hass: HomeAssistant, mock_receiver) -> None:
    """Test turning off the receiver."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_receiver.power_standby.assert_awaited_once()


async def test_zone3_turn_off(hass: HomeAssistant, mock_receiver) -> None:
    """Test turning off Zone 3."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ZONE3_ENTITY_ID},
        blocking=True,
    )
    mock_receiver.zone3_power_standby.assert_awaited_once()


async def test_set_volume(hass: HomeAssistant, mock_receiver) -> None:
    """Test setting volume level converts from 0..1 to dB."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )
    # 0.5 * 90 + (-80) = -35.0
    mock_receiver.set_volume.assert_awaited_once_with(-35.0)


async def test_zone2_set_volume(hass: HomeAssistant, mock_receiver) -> None:
    """Test setting Zone 2 volume uses the zone method."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ZONE2_ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )
    mock_receiver.zone2_set_volume.assert_awaited_once_with(-35.0)


async def test_volume_up(hass: HomeAssistant, mock_receiver) -> None:
    """Test volume up."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_receiver.volume_up.assert_awaited_once()


async def test_volume_down(hass: HomeAssistant, mock_receiver) -> None:
    """Test volume down."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_receiver.volume_down.assert_awaited_once()


async def test_mute(hass: HomeAssistant, mock_receiver) -> None:
    """Test muting."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    mock_receiver.mute_on.assert_awaited_once()


async def test_unmute(hass: HomeAssistant, mock_receiver) -> None:
    """Test unmuting."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
        blocking=True,
    )
    mock_receiver.mute_off.assert_awaited_once()


async def test_select_source(hass: HomeAssistant, mock_receiver) -> None:
    """Test selecting input source."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "dvd"},
        blocking=True,
    )
    mock_receiver.select_input_source.assert_awaited_once_with(InputSource.DVD)


async def test_zone3_select_input_source(hass: HomeAssistant, mock_receiver) -> None:
    """Test selecting a source for Zone 3."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ZONE3_ENTITY_ID, ATTR_INPUT_SOURCE: "dvd"},
        blocking=True,
    )
    mock_receiver.zone3_select_input_source.assert_awaited_once_with(InputSource.DVD)


async def test_select_source_net(hass: HomeAssistant, mock_receiver) -> None:
    """Test selecting NET source."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "net"},
        blocking=True,
    )
    mock_receiver.select_input_source.assert_awaited_once_with(InputSource.NET)


async def test_select_source_bluetooth(hass: HomeAssistant, mock_receiver) -> None:
    """Test selecting BT source."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "bt"},
        blocking=True,
    )
    mock_receiver.select_input_source.assert_awaited_once_with(InputSource.BT)


async def test_select_source_unknown_value_raises(hass: HomeAssistant) -> None:
    """Test selecting unknown source value raises error."""
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "NONEXISTENT"},
            blocking=True,
        )


async def test_push_update(hass: HomeAssistant, mock_receiver) -> None:
    """Test state updates from the receiver via subscribe callback."""
    new_state = _default_state()
    new_state.volume = -20.0
    new_state.input_source = InputSource.DVD

    mock_receiver.mock_state(new_state)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_INPUT_SOURCE] == "dvd"
    assert "sound_mode" not in state.attributes
    expected_volume = ((-20.0) - (-80.0)) / 90.0
    assert abs(state.attributes[ATTR_MEDIA_VOLUME_LEVEL] - expected_volume) < 0.001


async def test_zone_push_update(hass: HomeAssistant, mock_receiver) -> None:
    """Test zone entities update from their own state slices."""
    new_state = _default_state()
    new_state.zone2.power = False
    new_state.zone2.input_source = InputSource.DVD
    new_state.zone2.volume = -10.0
    new_state.zone3.power = True
    new_state.zone3.input_source = InputSource.NET

    mock_receiver.mock_state(new_state)
    await hass.async_block_till_done()

    zone2 = hass.states.get(ZONE2_ENTITY_ID)
    zone3 = hass.states.get(ZONE3_ENTITY_ID)
    assert zone2.state == STATE_OFF
    assert zone3.state == STATE_ON
    assert zone3.attributes[ATTR_INPUT_SOURCE] == "net"


async def test_disconnect(hass: HomeAssistant, mock_receiver) -> None:
    """Test entity becomes unavailable after disconnect."""
    mock_receiver.mock_state(None)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == "unavailable"


async def test_unload(hass: HomeAssistant, mock_receiver, mock_config_entry) -> None:
    """Test unloading the integration disconnects the receiver."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_receiver.disconnect.assert_awaited_once()
