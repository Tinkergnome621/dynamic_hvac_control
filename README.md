# Dynamic HVAC Control (All-in-One Package)

![Dynamic HVAC Control](brand/logo.png)

**Dynamic HVAC Control** is an advanced, high-performance climate controller and bundled Lovelace frontend card for Home Assistant. Designed for central air conditioning, multi-stage heat pumps, and dual-sensor duct environments.

## Features
- **All-in-One Bundle:** Installs the complete integration and automatically registers the high-DPI circular Lovelace card. No separate card installation required!
- **Intelligent Dual-Probe Architecture:** Supply air plenum and return air temperature/humidity monitoring with live Delta-T drop/rise telemetry.
- **Fail-Safe Physical Sync:** Seamless wall dial synchronization and automatic emergency handoff.
- **Compressor & Reversing Valve Safety:** Minimum run/off timers, anti-flip cycling protection, and pre-cooling optimization.
- **Dynamic Seasonal Logic:** Automatic seasonal conditioning direction tracking with zero-downtime winter and summer presets.
- **Anchor & Deadzone Band (v1.1.0):** Comfort and Sleep hold one target. In Heat/Cool, heating starts a buffer below it (default 3°), cooling starts a buffer above it, and both stop at the target. Eco, Away and Vacation are ranges: the house drifts freely between a floor and a ceiling. A changeover wait (default 20 minutes) separates heating and cooling runs.

## Presets
| Preset | Type | Heat/Cool | Cool mode | Heat mode |
|---|---|---|---|---|
| Comfort, Sleep | One target | Heats below target − lower buffer, cools above target + upper buffer, stops at target | Target | Target |
| Eco, Away, Vacation | Floor / ceiling | Heats below the floor, cools above the ceiling (plus swing) | Ceiling | Floor |
| Boost | Separate heat / cool | Pushes one way (last direction) | Boost cool | Boost heat |

On the card in Heat/Cool, drag the white knob (or tap −/+ next to **Target**) to move the target, and the deadband moves with it. The orange and blue knobs set how far heating and cooling start from the target, and that spacing stays when presets change.

Upgrading from v1.0.x converts settings automatically. Comfort and Sleep become the midpoint of their old cool/heat values (rounded to 0.5°), and Eco, Away and Vacation keep their values as floor and ceiling. Check Comfort and Sleep under **Settings → Presets, Deadband, Swings & Offsets** after upgrading.

## Installation via HACS
1. Open **HACS** > **Integrations** > **Custom repositories**.
2. Add `https://github.com/Tinkergnome621/dynamic_hvac_control` as an **Integration**.
3. Click **Install**, then restart Home Assistant.
4. Go to **Settings** > **Devices & Services** > **Add Integration** and search for **Dynamic HVAC Control**.

## Dashboard Card
The Lovelace card is automatically available:
```yaml
type: custom:dynamic-hvac-control-card
entity: climate.dynamic_hvac_control
name: Dynamic HVAC
```
