<img src="https://github.com/user-attachments/assets/85862bb8-87d8-48d8-a5ce-b4046369031c" width="600"/>

# Grenton Watcher (Home Assistant)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/jnalepka/grenton-watcher-home-assistant?style=for-the-badge)](https://github.com/jnalepka/grenton-watcher-home-assistant/releases)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg?style=for-the-badge)](https://github.com/jnalepka/grenton-watcher-home-assistant/graphs/commit-activity)
[![License: Non-Commercial](https://img.shields.io/badge/License-Non--Commercial-red.svg?style=for-the-badge)](LICENSE)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow.svg?style=for-the-badge&logo=buy-me-a-coffee)](https://tipply.pl/@jnalepka)

Grenton Watcher is a custom integration for Home Assistant that allows you to automatically send Home Assistant entity values directly to the Grenton system.
It observes selected entities and synchronizes their state with Grenton user features in real-time.

If you like what I do, buy me a `coffee`!

<a href="https://tipply.pl/@jnalepka">
    <img src="https://img.shields.io/static/v1?label=Donate&message=%E2%9D%A4&logo=GitHub&color=%23fe8e86" alt="Donate" width="130" height="30">
</a>

## ✨ Features

* **Real-time Synchronization:** Pushes changes instantly when HA entity state changes.
* **Built-in Value Converters:** Allows you to select conversion functions to format values specifically for myGrenton widgets.

## 🚀 Installation

### Option 1: HACS (Recommended)

1.  Open [HACS](https://www.hacs.xyz/docs/use/download/download/) in your Home Assistant instance.
2.  Search **Grenton Watcher** and **Download**.
3.  Restart Home Assistant.

### Option 2: Manual Installation

1.  Download the latest release from the [Releases](https://github.com/jnalepka/grenton-watcher-home-assistant/releases) section.
2.  Extract the zip file.
3.  Copy the `grenton_watcher` folder into your `custom_components` directory (usually `/config/custom_components/`).
4.  Restart Home Assistant.


## 🟥 Requirements on the Grenton side

> Note: If you already have a Listener object from the integration https://github.com/jnalepka/grenton-to-homeassistant
, there is no need to create another one.

1. Create a `HTTPListener` virtual object on the `GATE_HTTP` named `HA_Integration_Listener` and configure it as follows:
   * Path - `/HAlistener` (You can edit it if you want)
   * ResponseType - `JSON`

  <img width="836" height="643" alt="image" src="https://github.com/user-attachments/assets/32aef72d-bd06-4ec9-8861-20c48c50b06f" />

2. Create a script on the `GATE_HTTP` named `HA_Integration_Script`.

```lua
-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║                        Author: Jan Nalepka                            ║
-- ║                                                                       ║
-- ║ Script: HA_Integration_Script                                         ║
-- ║ Description: Display and control Grenton objects in Home Assistant.   ║
-- ║                                                                       ║
-- ║ License: Free for non-commercial use                                  ║
-- ║ Github: https://github.com/jnalepka/grenton-watcher-home-assistant    ║
-- ║                                                                       ║
-- ║ Script version: 1.0.0                                                 ║
-- ║                                                                       ║
-- ║ Requirements:                                                         ║
-- ║    Gate Http:                                                         ║
-- ║          1.  Gate Http NAME: "GATE_HTTP" <or change it in this script>║
-- ║                                                                       ║
-- ║    HttpListener virtual object:                                       ║
-- ║          Name: HA_Integration_Listener                                ║
-- ║          Path: /HAlistener                                            ║
-- ║          ResponseType: JSON                                           ║
-- ║                                                                       ║
-- ╚═══════════════════════════════════════════════════════════════════════╝

local reqJson = GATE_HTTP->HA_Integration_Listener->RequestBody
local code = 400
local resp = { g_status = "Grenton script ERROR" }

if reqJson.command or reqJson.status then
    local results = {}

    for key, value in pairs(reqJson) do
        results[key] = load(value)()
    end

    resp = { g_status = "OK" }
    for key, result in pairs(results) do
        resp[key] = result
    end

    code = 200
end

GATE_HTTP->HA_Integration_Listener->SetStatusCode(code)
GATE_HTTP->HA_Integration_Listener->SetResponseBody(resp)
GATE_HTTP->HA_Integration_Listener->SendResponse()
```

> Note: Pay attention to the name of the GATE and the virtual object.

3. Attach `HA_Integration_Script` script to the `OnRequest` event of the `HA_Integration_Listener` virtual object.

<img width="836" height="643" alt="image" src="https://github.com/user-attachments/assets/d5fcac49-6656-4b1b-9964-fb2b280c7792" />



## Fork changes (bwojtyca)

This fork adds, on top of upstream v1.1.0:

* **`skip_unavailable`** — per-mapping checkbox (add/edit form, default off). When enabled, `unavailable` / `unknown` states are not sent, so the Grenton user feature keeps its last value instead of the literal text.
* **Push on start** — after Home Assistant has started (and whenever an object group is reloaded) every mapping of the group is sent in **one** listener request (`command`, `command_2`, …).
* **Service `grenton_watcher.push_all`** — the same grouped push on demand, optionally for one object group (`entry_id`). Call it from an automation when the CLU/GATE comes back after a restart, so its user features get real values instead of defaults.
* **Serialized sending** — all requests to the GATE listener go through one lock, one at a time.
* **`send_timestamp`** — per-mapping checkbox (default off). Sends, right after the value and in the same request, the send time to a companion feature `<feature>_ts` (Unix time, UTC seconds; a `CLU…->name` mapping writes `CLU…->name_ts`). A script on the CLU compares it with its own clock: a feature whose `_ts` stops advancing — Home Assistant down, integration unloaded, entity unavailable — can be dropped from whatever it feeds instead of being trusted forever. Pair it with a periodic `push_all` so the marker keeps advancing while the value itself is unchanged.

## 📖 Usage

1. Navigate to **Settings** > **Devices & Services** and click **+ Add Integration**. Search for **Grenton Watcher**.
2. Enter an **Object Group Name** and the **Gate Http Listener URL**.
   * *The group name can be arbitrary; it is used solely to organize your observed entities.*
3. Proceed to the configuration to add your first watcher:
   * Select the **Entity**.
   * Select the **Attribute** to watch, enter the target **Grenton User Feature**, and optionally choose a **Conversion Function**.

> **Note:** If the user feature is located on a CLU, you must include the CLU identifier (e.g., `CLU220000000->my_feature`). If the feature is directly on the GATE_HTTP, enter only the feature name (e.g., `my_feature`).


## Run the Home Assistant service

### Home Assistant Long-lived access token

In Home Assistant go to the Profile->Security->Long-lived access tokens, and create the long-lived access token. Token will be valid for 10 years from creation.

### Grenton-side requirement for calling Home Assistant services

1. On the Gate HTTP, create an `HttpRequest` virtual object:

   ![image](https://github.com/user-attachments/assets/2de2248c-6992-42a3-b91e-ad0506311d89)

   * `Name`: HA_Request_Set
   * `Host`: http://<your HA IP Address>:8123 (e.g. http://192.168.0.114:8123)
   * `Path`: /api/state (any value)
   * `Method`: POST
   * `RequestType`: JSON
   * `ResponseType`: JSON
   * `RequestHeadres`: Authorization: Bearer <your Long-lived access token> (e.g. Authorization: Bearer eyJhbGciOiJIUz.....)

2. On the Gate HTTP, create a script, named `HA_Integration_Set`:

    ```lua
      -- ╔═══════════════════════════════════════════════════════════════════════╗
      -- ║                        Author: Jan Nalepka                            ║
      -- ║                                                                       ║
      -- ║ Script: HA_Integration_Set                                            ║
      -- ║ Description: Send a service command for an entity in Home Assistant.  ║
      -- ║                                                                       ║
      -- ║ License: MIT License                                                  ║
      -- ║ Github: https://github.com/jnalepka/homeassistant-to-grenton          ║
      -- ║                                                                       ║
      -- ║ Version: 1.0.0                                                        ║
      -- ║                                                                       ║
      -- ║ Requirements:                                                         ║
      -- ║    Gate Http:                                                         ║
      -- ║          1.  Gate Http NAME: "GATE_HTTP" <or change it in this script>║
      -- ║                                                                       ║
      -- ║    Script parameters:                                                 ║
      -- ║          1.  ha_entity, default: "light.my_lamp", string              ║
      -- ║          2.  ha_method, default: "toggle", string                     ║
      -- ║                                                                       ║
      -- ║    Http_Request virtual object:                                       ║
      -- ║          Name: HA_Request_Set                                         ║
      -- ║          Host: http://192.168.0.114:8123  (example)                   ║
      -- ║          Path: /api/state (any value)                                 ║
      -- ║          Method: "POST"                                               ║
      -- ║          RequestType: JSON                                            ║
      -- ║          ResponseType: JSON                                           ║
      -- ║          RequestHeaders: Authorization: Bearer <your HA token>        ║
      -- ║                                                                       ║
      -- ╚═══════════════════════════════════════════════════════════════════════╝
      
      local ha_service, ha_entity_name = string.match(ha_entity, "([^%.]+)%.([^%.]+)")
      local path = "/api/services/"..ha_service.."/"..ha_method
      local reqJson = { entity_id = ha_entity }
      
      GATE_HTTP->HA_Request_Set->SetPath(path)
      GATE_HTTP->HA_Request_Set->SetRequestBody(reqJson)
      GATE_HTTP->HA_Request_Set->SendRequest()

    ```

    > Note: If you use a different name for the Gate HTTP or the virtual object, modify it in the script.

3. Add the script parameters to the `HA_Integration_Set` script:

   ![image](https://github.com/user-attachments/assets/d8e08f3d-7d67-4b77-9d2f-b5a50c7d52d9)

   * `Name`: ha_entity `Type`: string
   * `Name`: ha_method `Type`: string

4. (Optional) Attach the `HA_Request_Timer` Start() method to the `HA_Request_Set` OnResponse event:

   ![image](https://github.com/user-attachments/assets/bb1b97ed-0c33-4530-8390-06ff0992ad0d)

   This operation will update all states from HomeAssistant after the action.

5. Now you can call the `HA_Integration_Set` script from everywhere in the Grenton System!

   ![image](https://github.com/user-attachments/assets/948074ff-c0ac-4ecd-bdfa-75c5f8e74b5c)


### Simple Home Assistant services

   | ha_entity    | ha_method  | description |
   |-------------|-------------|-------------|
   | light.your_lamp | turn_on | Turn on one or more lights. |
   | light.your_lamp | turn_off | Turn off one or more lights. |
   | light.your_lamp | toggle | Toggles one or more lights, from on to off, or, off to on, based on their current state. |
   | cover.your_blinds | open_cover | Opens blinds. |
   | cover.your_blinds | close_cover | Closes blinds. |
   | cover.your_blinds | stop_cover | Stops the cover movement. |
   | cover.your_blinds | toggle | Toggles a cover open/closed. |
   | cover.your_blinds | open_cover_tilt | Tilts a cover open. |
   | cover.your_blinds | close_cover_tilt | Tilts a cover to close. |
   | cover.your_blinds | stop_cover_tilt | Stops a tilting cover movement. |
   | script.your_script | turn_on | Runs the sequence of actions defined in a script. |
   | script.your_script | turn_off | Stops a running script. |
   | script.your_script | toggle | Toggle a script. Starts it, if isn't running, stops it otherwise. |
   | switch.your_switch | turn_on | Turns a switch on. |
   | switch.your_switch | turn_off | Turns a switch off. |
   | switch.your_switch | toggle | Toggles a switch on/off. |
   | climate.your_thermostat | turn_on | Turns climate device on. |
   | climate.your_thermostat | turn_off | Turns climate device off. |
   | climate.your_thermostat | toggle | Toggles climate device, from on to off, or off to on. |

## (Optional) Use custom script to run the Home Assistant service with attributes

### For example, we will use a script located in the custom_scripts/HA_Integration_Set_Light.lua folder

   1. On the Gate HTTP, create a script, named `HA_Integration_Set_Light`:

      ```lua
        -- ╔══════════════════════════════════════════════════════════════════════════════════════════════════════╗
        -- ║                        Author: Jan Nalepka                                                           ║
        -- ║                                                                                                      ║
        -- ║ Script: HA_Integration_Set_Light                                                                     ║
        -- ║ Description: Send a service command for an entity in Home Assistant.                                 ║
        -- ║                                                                                                      ║
        -- ║ License: MIT License                                                                                 ║
        -- ║ Github: https://github.com/jnalepka/homeassistant-to-grenton                                         ║
        -- ║                                                                                                      ║
        -- ║ Version: 1.0.0                                                                                       ║
        -- ║                                                                                                      ║
        -- ║ Requirements:                                                                                        ║
        -- ║    Gate Http:                                                                                        ║
        -- ║          1.  Gate Http NAME: "GATE_HTTP" <or change it in this script>                               ║
        -- ║                                                                                                      ║
        -- ║    Script parameters:                                                                                ║
        -- ║          1.  ha_entity, default: "light.my_lamp", string                                             ║
        -- ║          2.  ha_method, default: "toggle", string                                                    ║
        -- ║          3.  attr_brightness, default: -1, number [0-255]                                            ║
        -- ║          4.  attr_hs_color, default: "-", string "[hue, sat]", "[300, 70]"                           ║
        -- ║          5.  attr_color_temp, default: -1, number [153-500]                                          ║
        -- ║                                                                                                      ║
        -- ║    Http_Request virtual object:                                                                      ║
        -- ║          Name: HA_Request_Set                                                                        ║
        -- ║          Host: http://192.168.0.114:8123  (example)                                                  ║
        -- ║          Path: /api/state (any value)                                                                ║
        -- ║          Method: "POST"                                                                              ║
        -- ║          RequestType: JSON                                                                           ║
        -- ║          ResponseType: JSON                                                                          ║
        -- ║          RequestHeaders: Authorization: Bearer <your HA token>                                       ║
        -- ║                                                                                                      ║
        -- ║    Available methods:                                                                                ║
        -- ║          -  turn_on                                                                                  ║
        -- ║          -  turn_on(attr_brightness)                                                                 ║
        -- ║          -  turn_on(attr_brightness, attr_hs_color)                                                  ║
        -- ║          -  turn_on(attr_brightness, attr_hs_color)                                                  ║
        -- ║          -  turn_off                                                                                 ║
        -- ║          -  toggle                                                                                   ║
        -- ║                                                                                                      ║
        -- ║    Examples:                                                                                         ║
        -- ║          - entity="light.lamp1", method="turn_on"                                                    ║
        -- ║          - entity="light.lamp1", method="turn_on", brightness=255                                    ║
        -- ║          - entity="light.lamp1", method="turn_on", brightness=255, hs_color="[300, 70]"              ║
        -- ║          - entity="light.lamp1", method="turn_on", brightness=255, color_temp=450                    ║
        -- ║                                                                                                      ║
        -- ╚══════════════════════════════════════════════════════════════════════════════════════════════════════╝
        
        local ha_service, ha_entity_name = string.match(ha_entity, "([^%.]+)%.([^%.]+)")
        local path = "/api/services/"..ha_service.."/"..ha_method
        local reqJson = { entity_id = ha_entity }
        
        if attr_brightness ~= -1 then 
        	reqJson.brightness = attr_brightness 
        end
        
        if attr_hs_color ~= "-" then 
        	reqJson.hs_color = attr_hs_color
        end
        
        if attr_color_temp ~= -1 then 
        	reqJson.color_temp = attr_color_temp 
        end
        
        GATE_HTTP->HA_Request_Set->SetPath(path)
        GATE_HTTP->HA_Request_Set->SetRequestBody(reqJson)
        GATE_HTTP->HA_Request_Set->SendRequest()
      ```

      > Note: If you use a different name for the Gate HTTP or the virtual object, modify it in the script.

2. Add the script parameters to the `HA_Integration_Set_Light` script:

   ![image](https://github.com/user-attachments/assets/3e2c6cfc-78a7-4fbe-a50d-8c3e1d2b30b5)

   * `Name`: ha_entity `Type`: string
   * `Name`: ha_method `Type`: string
   * `Name`: attr_brightness `Type`: number `Default`: -1  (range: 0-255)
   * `Name`: attr_hs_color `Type`: string `Default`: "-"  (example: "[300,70]", where 300 - hue in range 0-360, 70 is saturation in range 0-100)
   * `Name`: attr_color_temp `Type`: number `Default`: -1  (range: 153-500), where 153 is cold≈6500K, 500 is warm≈2000K
  

### Examples
   
   | ha_entity    | ha_method  | attr_brightness | attr_hs_color | attr_color_temp |  description |
   |-------------|-------------|-------------|-------------|-------------|-------------|
   | light.your_lamp | turn_on | [0-255] | default | default | Turn on one or more lights and set brightness. |
   | light.your_lamp | turn_on | [0-255] | "[300,70]" | default | Turn on one or more lights and set brightness, hue and saturation. |
   | light.your_lamp | turn_on | [0-255] | default | [153-500] | Turn on one or more lights and set brightness and color temperature. |

## 📄 License

This project is licensed for **Personal, Non-Commercial Use Only**. You are free to use, copy, and modify this software for your own personal home automation setup.

❌ **Commercial use is prohibited** without prior written permission.

See the [LICENSE](LICENSE) file for the full text.
