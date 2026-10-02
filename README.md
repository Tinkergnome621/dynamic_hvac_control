# Dynamic HVAC Control (All-in-One Package)

![Dynamic HVAC Control](brand/logo.png)

**Dynamic HVAC Control** is an advanced, high-performance climate controller and bundled Lovelace frontend card for Home Assistant. Designed for central air conditioning, multi-stage heat pumps, and dual-sensor duct environments.

## Features
- **All-in-One Bundle:** Installs the complete integration and automatically registers the high-DPI circular Lovelace card. No separate card installation required!
- **Intelligent Dual-Probe Architecture:** Supply air plenum and return air temperature/humidity monitoring with live Delta-T drop/rise telemetry.
- **Fail-Safe Physical Sync:** Seamless wall dial synchronization and automatic emergency handoff.
- **Compressor & Reversing Valve Safety:** Minimum run/off timers, anti-flip cycling protection, and pre-cooling optimization.
- **Dynamic Seasonal Logic:** Automatic seasonal conditioning direction tracking with zero-downtime winter and summer presets.

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
