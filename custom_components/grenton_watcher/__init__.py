"""
==================================================
Author: Jan Nalepka
Script version: 1.0
Date: 19.11.2025
Repository: https://github.com/jnalepka/homeassistant-to-grenton
==================================================
"""

import asyncio
import logging
import time
import aiohttp
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_UNAVAILABLE, STATE_UNKNOWN

_LOGGER = logging.getLogger(__name__)
DOMAIN = "grenton_watcher"
SERVICE_PUSH_ALL = "push_all"
DATA_SEND_LOCK = "_send_lock"
DATA_ENTRIES = "_entries"

def normalize_value(value):
    if value is None:
        return None
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, (list, set, tuple)):
        return ",".join(
            str(v.value if hasattr(v, "value") else v)
            for v in value
        )
    if isinstance(value, (int, float)):
        return value
    return str(value)

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)

def _convert(val, func):
    """Apply the mapping's conversion function to a raw state/attribute value."""
    if func == "convert_state_on_off_to_1_0":
        if isinstance(val, str):
            val = 1 if val.lower() == "on" else 0
    elif func == "convert_brightness_to_1_0":
        try:
            val = round(float(val) / 255.0, 2)
        except Exception:
            val = 0.0
    elif func == "convert_hs_color_to_hue_0_360":
        if isinstance(val, (list, tuple)) and len(val) >= 1:
            try:
                val = int(val[0])
            except Exception:
                val = 0.0
    elif func == "convert_hs_color_to_sat_1_0":
        if isinstance(val, (list, tuple)) and len(val) >= 2:
            try:
                val = float(val[1]) / 100.0
            except Exception:
                val = 0.0
    elif func == "convert_hvac_state_to_coolmaster_state_0_1":
        if isinstance(val, str):
            val = 0 if val.lower() == "off" else 1
    elif func == "convert_hvac_state_to_coolmaster_connection_status":
        if isinstance(val, str):
            val = 0 if val.lower() == "unavailable" else 1
    elif func == "convert_hvac_state_to_coolmaster_mode":
        if isinstance(val, str):
            v = val.lower()
            if v == "cool":
                val = 1
            elif v == "heat":
                val = 2
            elif v == "fan_only":
                val = 3
            elif v == "dry":
                val = 4
            else:
                val = 5 # auto
    elif func == "convert_hvac_fan_mode_to_coolmaster_fan_speed":
        if isinstance(val, str):
            v = val.lower()
            if v == "silent":
                val = 0
            elif v == "low":
                val = 1
            elif v == "medium":
                val = 2
            elif v == "high":
                val = 3
            elif v == "turbo":
                val = 4
            else:
                val = 5 # auto
    elif func == "convert_hvac_swing_mode_to_coolmaster_louver":
        if isinstance(val, str):
            v = val.lower()
            if v == "both":
                val = 1
            elif v == "horizontal":
                val = 2
            elif v == "vertical":
                val = 6
            else:
                val = 7 # off
    return normalize_value(val)


def _feature_command(feature, val, *extra):
    """Lua snippet assigning values to one or more Grenton user features.

    `feature`/`val` is the first assignment; `extra` holds further
    (name, value) pairs written to the same target, e.g. a companion
    timestamp. Two forms, as upstream: "CLU220000000->name" writes on that
    CLU via execute(), a bare "name" writes on the GATE the listener runs
    on. Several assignments to the same CLU share a single execute() -
    Lua runs a chunk of statements just as happily as one - which halves
    the remote calls and makes the value and its timestamp atomic.
    """
    pairs = [(feature, val)] + [tuple(extra[i:i + 2]) for i in range(0, len(extra), 2)]
    if '->' in feature:
        target = feature.split('->')[0]
        statements = []
        for name, value in pairs:
            short = name.split('->')[-1]
            if isinstance(value, str): value = f"\\'{value}\\'"
            statements.append(f"setVar(\\'{short}\\', {value})")
        return f"{target}:execute(0, '{' '.join(statements)}')"
    statements = []
    for name, value in pairs:
        if isinstance(value, str): value = f"\'{value}\'"
        statements.append(f"setVar('{name}', {value})")
    return " ".join(statements)


def _timestamp_feature(feature):
    """Companion timestamp feature name: "<feature>_ts", keeping any CLU prefix."""
    if '->' in feature:
        name_part_0, name_part_1 = feature.split('->')
        return f"{name_part_0}->{name_part_1}_ts"
    return f"{feature}_ts"


def _mapping_commands(m, state, sent_at=None):
    """Lua snippets for one mapping: the value, optionally followed by its
    send timestamp. Empty when the mapping must not be sent at all."""
    if state is None:
        return []
    # Optional per-mapping guard: an entity that is unavailable/unknown
    # has no value worth sending. Without it the literal text
    # "unavailable" is written into the Grenton user feature, which a
    # Thermostat or script downstream reads as a non-number (0).
    if m.get("skip_unavailable") and state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        _LOGGER.debug("Skipping %s for %s: state is %s", m["name"], state.entity_id, state.state)
        return []
    attr = m.get("attribute")
    val = state.state if attr == "state" else state.attributes.get(attr)
    val = _convert(val, m.get("function", "no_convert"))
    feature = m["name"]
    # Optional freshness marker: "<feature>_ts" gets the Unix time (UTC
    # seconds) at which this value was sent. A script on the CLU compares it
    # with its own clock, so a feature whose _ts stops advancing - Home
    # Assistant down, integration unloaded, entity gone unavailable - can be
    # dropped from whatever it feeds instead of being trusted forever. It
    # travels in the same command as the value, so the two cannot diverge.
    if m.get("send_timestamp"):
        stamp = int(sent_at if sent_at is not None else time.time())
        return [_feature_command(feature, val, _timestamp_feature(feature), stamp)]
    return [_feature_command(feature, val)]


def _group_commands(snippets):
    """Pack Lua snippets into one listener request: command, command_2, command_3..."""
    command = {}
    for counter, snippet in enumerate(snippets, start=1):
        add_index = "" if counter == 1 else f"_{counter}"
        command[f"command{add_index}"] = snippet
    return command


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    api_endpoint = entry.data["api_endpoint"]
    mappings = entry.options.get("mappings", [])

    entity_ids = list({m["entity_id"] for m in mappings})

    domain_data = hass.data.setdefault(DOMAIN, {})
    # One lock for the whole integration: the GATE HTTP listener handles a
    # single request at a time, so every send (live or bulk, any entry)
    # waits for the previous one instead of racing it.
    send_lock = domain_data.setdefault(DATA_SEND_LOCK, asyncio.Lock())

    async def send(command):
        if not command:
            return
        async with send_lock:
            async with aiohttp.ClientSession() as session:
                try:
                    _LOGGER.info("Prepared commands: %s", command)
                    await session.post(api_endpoint, json=command)
                except Exception as e:
                    _LOGGER.error("Failed to send update: %s", e)

    async def state_changed(event):
        new_state = event.data.get("new_state")
        if not new_state:
            return
        sent_at = time.time()
        snippets = [
            snippet
            for m in mappings
            if new_state.entity_id == m["entity_id"]
            for snippet in _mapping_commands(m, new_state, sent_at)
        ]
        await send(_group_commands(snippets))

    async def push_all(_event=None):
        """Send every mapping of this entry in one grouped request.

        Runs after Home Assistant has started and on the push_all service, so
        a restarted CLU/GATE (whose user features came back with defaults)
        gets the current values without waiting for each entity to change."""
        sent_at = time.time()
        snippets = [
            snippet
            for m in mappings
            for snippet in _mapping_commands(m, hass.states.get(m["entity_id"]), sent_at)
        ]
        _LOGGER.info("Pushing %d commands for %d mappings of '%s'", len(snippets), len(mappings), entry.title)
        await send(_group_commands(snippets))

    remove_listener = async_track_state_change_event(hass, entity_ids, state_changed)
    domain_data.setdefault(DATA_ENTRIES, {})[entry.entry_id] = {
        "remove_listener": remove_listener,
        "push_all": push_all,
    }

    if hass.is_running:
        hass.async_create_task(push_all())
    else:
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, push_all)
        )

    if not hass.services.has_service(DOMAIN, SERVICE_PUSH_ALL):
        async def handle_push_all(call: ServiceCall):
            wanted = call.data.get("entry_id")
            for entry_id, data in list(domain_data.get(DATA_ENTRIES, {}).items()):
                if wanted and entry_id != wanted:
                    continue
                await data["push_all"]()

        hass.services.async_register(
            DOMAIN, SERVICE_PUSH_ALL, handle_push_all,
            schema=vol.Schema({vol.Optional("entry_id"): str}),
        )

    _LOGGER.info("Grenton Watcher started for mappings: %s", mappings)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data.get(DOMAIN, {}).get(DATA_ENTRIES, {}).pop(entry.entry_id, None)
    if data:
        data["remove_listener"]()
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
