# Time Based Cover

Home Assistant custom integration that wraps an existing cover supporting only
open/close/stop (e.g. a Matter or RF curtain) and adds an estimated position
based on how long the motor has been running.

## Features

- Position 0–100 % estimated from separate travel times up and down
- Up and down buttons stay usable at intermediate positions
- `set_cover_position` moves for the calculated time and then sends stop
- At 0 % / 100 % no stop is sent – the motor runs to its own end stop
- Position is restored after a Home Assistant restart
- Multiple covers move independently of each other
- Set up and edited entirely in the UI (no YAML, no helpers)
- Action `time_based_cover.set_known_position` to correct the position without moving

## Installation

### HACS

1. In HACS, open the menu → **Custom repositories**.
2. Add `https://github.com/nemeier/ha-time-based-cover` with type **Integration**.
3. Install **Time Based Cover** and restart Home Assistant.
4. Continue with step 3 below.

### Manual

1. Copy `custom_components/time_based_cover` to `/config/custom_components/time_based_cover`.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Helpers → Create helper → Time Based Cover**.
4. Enter a name, select the source cover and enter the travel times.
5. Repeat step 3–4 for each window.

Travel times and source cover can be changed later via the helper's **Options**.

## Tips

- Measure the travel times with a stopwatch from fully closed to fully open and back.
- Commands routed through a cloud (e.g. BroadLink) add latency, so the cover may
  travel slightly further than calculated. Fully opening or closing re-syncs the position.
- Hide the original source cover entity in the UI and use only the time based one.
- If you used the earlier YAML package, remove it to avoid duplicate covers.
