/**
 * Dynamic HVAC Control Card (v1.0.2)
 * Custom Lovelace Card for Home Assistant
 * Designed for Central A/C and Heat Pump Dual-Setpoint Range Systems
 * 
 * Features:
 * - Dual-knob circular arc dial (Heat / Cool setpoints with emerald deadband)
 * - Single-knob operation in Cool-only and Heat-only modes with working steppers & drag
 * - Icon-only HVAC status indicator (Green thermometer for Idle, Red flame for Heat, Blue snowflake for Cool)
 * - Vertical duct plenum probe stack on the left (Auto-hides if no plenum sensors are present)
 * - True sensor readouts without dummy fallback numbers ("—" when unavailable)
 * - Minimalist Blower Fan toggle switch (Auto-hides if no fan entity exists)
 * - Non-destructive target range views preserving DOM structure across mode changes
 * - Robust entity unavailable overlay with automatic live recovery
 * - Dragging debounce preventing incoming state jitter
 * - Light and Dark theme compatibility with CSS theme variables
 */

class DynamicHvacControlCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._dragging = null; // 'low' | 'high' | 'single'
    this._tempLow = 64;
    this._tempHigh = 74;
    this._tempSingle = 70;
  }

  static getStubConfig() {
    return {
      entity: "climate.dynamic_hvac_control",
      name: "Dynamic HVAC Control"
    };
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Please define an entity in your card configuration (e.g. climate.dynamic_hvac_control)");
    }
    this._config = {
      name: "Dynamic HVAC Control",
      step: 1.0,
      min_temp: 60,
      max_temp: 85,
      ...config
    };
    this._renderBase();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config || !this._config.entity) return;

    if (!this.shadowRoot.getElementById('card-root')) {
      this._renderBase();
    }

    const entityState = hass.states[this._config.entity];
    if (!entityState || entityState.state === 'unavailable' || entityState.state === 'unknown') {
      this._renderUnavailable();
      return;
    }

    this._hideUnavailable();
    this._updateCard(entityState);
  }

  getCardSize() {
    return 6;
  }

  /* -------------------------------------------------------------------------
   * Base Shadow DOM Structure & CSS with Theme Variables
   * ------------------------------------------------------------------------- */
  _renderBase() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--paper-font-body1_-_font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif);
          color: var(--primary-text-color, #e2e8f0);
          box-sizing: border-box;
        }
        *, *::before, *::after {
          box-sizing: inherit;
        }
        ha-card {
          background: var(--ha-card-background, var(--card-background-color, #141721));
          border: 1px solid var(--divider-color, rgba(255, 255, 255, 0.08));
          border-radius: var(--ha-card-border-radius, 28px);
          padding: 20px;
          box-shadow: var(--ha-card-box-shadow, 0 20px 40px -15px rgba(0, 0, 0, 0.7));
          position: relative;
          overflow: hidden;
          transition: background 0.3s ease, color 0.3s ease;
        }
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
        }
        .header-title {
          font-size: 1.15rem;
          font-weight: 700;
          color: var(--primary-text-color, #ffffff);
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .header-title svg {
          width: 20px;
          height: 20px;
          fill: var(--primary-color, #38bdf8);
        }
        .version-badge {
          font-size: 0.7rem;
          font-weight: 700;
          color: var(--secondary-text-color, #94a3b8);
          background: var(--secondary-background-color, rgba(255, 255, 255, 0.05));
          border: 1px solid var(--divider-color, rgba(255, 255, 255, 0.1));
          padding: 4px 10px;
          border-radius: 9999px;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        /* Top 2-Column Grid: Left Plenum Stack + Right Dial */
        .top-grid {
          display: grid;
          grid-template-columns: 190px 1fr;
          gap: 16px;
          align-items: center;
          transition: grid-template-columns 0.3s ease;
        }
        .top-grid.no-plenum {
          grid-template-columns: 1fr;
        }
        @media (max-width: 480px) {
          .top-grid {
            grid-template-columns: 1fr;
          }
        }

        /* Vertical Stack for Plenum Probes */
        .plenum-stack {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .plenum-box {
          background: var(--secondary-background-color, #191e2b);
          border: 1px solid var(--divider-color, rgba(255, 255, 255, 0.06));
          border-radius: 14px;
          padding: 10px 12px;
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        .plenum-box.highlight {
          border-color: rgba(16, 185, 129, 0.45);
          background: rgba(16, 185, 129, 0.08);
        }
        .plenum-label {
          font-size: 0.65rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: var(--secondary-text-color, #94a3b8);
          display: flex;
          align-items: center;
          gap: 5px;
        }
        .plenum-label.optimal {
          color: #10b981;
        }
        .plenum-value {
          font-size: 1.05rem;
          font-weight: 800;
          color: var(--primary-text-color, #f8fafc);
          font-variant-numeric: tabular-nums;
        }
        .plenum-sub {
          font-size: 0.65rem;
          color: var(--secondary-text-color, #64748b);
        }

        /* Dial Container */
        .dial-container {
          position: relative;
          width: 100%;
          max-width: 250px;
          margin: 0 auto;
          aspect-ratio: 1 / 1;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        svg.dial-svg {
          width: 100%;
          height: 100%;
          overflow: visible;
          touch-action: none;
          user-select: none;
        }
        .dial-track {
          fill: none;
          stroke: var(--secondary-background-color, #222838);
          stroke-width: 12;
          stroke-linecap: round;
        }
        .dial-arc-heat {
          fill: none;
          stroke: #f97316;
          stroke-width: 12;
          stroke-linecap: round;
          filter: drop-shadow(0 0 6px rgba(249, 115, 22, 0.4));
        }
        .dial-arc-deadband {
          fill: none;
          stroke: #10b981;
          stroke-width: 12;
          stroke-linecap: round;
          filter: drop-shadow(0 0 5px rgba(16, 185, 129, 0.35));
        }
        .dial-arc-cool {
          fill: none;
          stroke: #0ea5e9;
          stroke-width: 12;
          stroke-linecap: round;
          filter: drop-shadow(0 0 6px rgba(14, 165, 233, 0.4));
        }
        .dial-knob {
          cursor: grab;
          touch-action: none;
          transition: transform 0.05s ease;
        }
        .dial-knob:active {
          cursor: grabbing;
        }

        /* Center Dial Content (HTML Overlay) */
        .dial-center-overlay {
          position: absolute;
          inset: 0;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          pointer-events: none;
          text-align: center;
          z-index: 5;
        }

        /* Icon-Only Status Indicator */
        .status-icon-circle {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 2px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
        }
        .status-icon-circle svg {
          width: 16px;
          height: 16px;
        }
        .status-idle {
          background: rgba(16, 185, 129, 0.2);
          border: 1.5px solid #10b981;
        }
        .status-idle svg {
          fill: #10b981;
        }
        .status-cool {
          background: rgba(14, 165, 233, 0.25);
          border: 1.5px solid #0ea5e9;
          animation: pulse-cool 2.5s infinite ease-in-out;
        }
        .status-cool svg {
          fill: #38bdf8;
        }
        .status-heat {
          background: rgba(249, 115, 22, 0.25);
          border: 1.5px solid #f97316;
          animation: pulse-heat 2.5s infinite ease-in-out;
        }
        .status-heat svg {
          fill: #fb923c;
        }
        .status-off {
          background: rgba(100, 116, 139, 0.2);
          border: 1.5px solid #64748b;
        }
        .status-off svg {
          fill: #94a3b8;
        }

        @keyframes pulse-cool {
          0%, 100% { box-shadow: 0 0 8px rgba(14, 165, 233, 0.3); }
          50% { box-shadow: 0 0 16px rgba(14, 165, 233, 0.7); }
        }
        @keyframes pulse-heat {
          0%, 100% { box-shadow: 0 0 8px rgba(249, 115, 22, 0.3); }
          50% { box-shadow: 0 0 16px rgba(249, 115, 22, 0.7); }
        }

        /* Current Temperature Display */
        .temp-display {
          font-size: 2.85rem;
          font-weight: 900;
          color: var(--primary-text-color, #ffffff);
          line-height: 1;
          letter-spacing: -0.03em;
          display: flex;
          align-items: baseline;
          justify-content: center;
          margin: 3px 0;
        }
        .temp-unit {
          font-size: 1.35rem;
          font-weight: 400;
          color: var(--secondary-text-color, #94a3b8);
          margin-left: 2px;
        }

        /* Minimalist Fan Toggle Switch */
        .fan-toggle-wrap {
          pointer-events: auto;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
          cursor: pointer;
          margin-top: 4px;
        }
        .fan-icon-btn {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: var(--secondary-background-color, #191e2b);
          border: 1.5px solid var(--divider-color, #334155);
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s ease;
        }
        .fan-icon-btn svg {
          width: 17px;
          height: 17px;
          fill: var(--secondary-text-color, #64748b);
          transition: transform 0.2s ease;
        }
        .fan-toggle-wrap.active .fan-icon-btn {
          background: rgba(14, 165, 233, 0.18);
          border-color: #0ea5e9;
          box-shadow: 0 0 12px rgba(14, 165, 233, 0.4);
        }
        .fan-toggle-wrap.active .fan-icon-btn svg {
          fill: #38bdf8;
          animation: spin-fan 2s linear infinite;
        }
        .fan-text-label {
          font-size: 0.65rem;
          font-weight: 800;
          letter-spacing: 0.08em;
          color: var(--secondary-text-color, #64748b);
          text-transform: uppercase;
        }
        .fan-toggle-wrap.active .fan-text-label {
          color: #38bdf8;
        }

        @keyframes spin-fan {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        /* Target Range Box (Centered Below Dial & Stack) */
        .target-range-box {
          margin-top: 18px;
          background: var(--secondary-background-color, #161a25);
          border: 1px solid var(--divider-color, rgba(255, 255, 255, 0.07));
          border-radius: 16px;
          padding: 12px 16px;
          text-align: center;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 5px;
        }
        .target-range-headline {
          font-size: 0.95rem;
          font-weight: 800;
          color: var(--primary-text-color, #ffffff);
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .target-heat-tag {
          color: #fb923c;
        }
        .target-cool-tag {
          color: #38bdf8;
        }
        .target-range-subline {
          font-size: 0.75rem;
          color: var(--secondary-text-color, #94a3b8);
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
          justify-content: center;
        }
        .target-range-subline strong {
          color: var(--primary-text-color, #f1f5f9);
        }

        /* Steppers Row */
        .stepper-row {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
          margin-top: 12px;
        }
        .stepper-group {
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .btn-step {
          width: 34px;
          height: 34px;
          border-radius: 10px;
          background: var(--secondary-background-color, #1f2533);
          border: 1px solid var(--divider-color, rgba(255, 255, 255, 0.1));
          color: var(--primary-text-color, #ffffff);
          font-size: 1.1rem;
          font-weight: 800;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.15s ease;
        }
        .btn-step:hover {
          filter: brightness(1.2);
        }
        .btn-step:active {
          transform: scale(0.92);
        }
        .stepper-label {
          font-size: 0.7rem;
          font-weight: 700;
          text-transform: uppercase;
          color: var(--secondary-text-color, #64748b);
          padding: 0 4px;
        }

        /* Mode Selector Buttons */
        .mode-row {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 8px;
          margin-top: 14px;
        }
        .btn-mode {
          background: var(--secondary-background-color, #191e2b);
          border: 1px solid var(--divider-color, rgba(255, 255, 255, 0.07));
          border-radius: 12px;
          padding: 9px 4px;
          color: var(--secondary-text-color, #94a3b8);
          font-size: 0.75rem;
          font-weight: 700;
          cursor: pointer;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
          transition: all 0.2s ease;
        }
        .btn-mode:hover {
          filter: brightness(1.2);
          color: var(--primary-text-color, #ffffff);
        }
        .btn-mode svg {
          width: 14px;
          height: 14px;
          fill: currentColor;
        }
        .btn-mode.active {
          background: rgba(14, 165, 233, 0.18);
          border-color: #0ea5e9;
          color: #38bdf8;
          box-shadow: 0 0 10px rgba(14, 165, 233, 0.25);
        }
        .btn-mode.active-heat {
          background: rgba(249, 115, 22, 0.18);
          border-color: #f97316;
          color: #fb923c;
          box-shadow: 0 0 10px rgba(249, 115, 22, 0.25);
        }
        .btn-mode.active-cool {
          background: rgba(14, 165, 233, 0.18);
          border-color: #0ea5e9;
          color: #38bdf8;
          box-shadow: 0 0 10px rgba(14, 165, 233, 0.25);
        }
        .btn-mode.active-off {
          background: rgba(100, 116, 139, 0.2);
          border-color: #64748b;
          color: var(--primary-text-color, #e2e8f0);
        }

        /* Preset Buttons */
        .preset-row {
          display: grid;
          grid-template-columns: repeat(6, 1fr);
          gap: 6px;
          margin-top: 10px;
        }
        @media (max-width: 480px) {
          .preset-row {
            grid-template-columns: repeat(3, 1fr);
          }
        }
        .btn-preset {
          background: var(--secondary-background-color, #161a25);
          border: 1px solid var(--divider-color, rgba(255, 255, 255, 0.06));
          border-radius: 10px;
          padding: 8px 2px;
          color: var(--secondary-text-color, #94a3b8);
          font-size: 0.7rem;
          font-weight: 700;
          cursor: pointer;
          text-align: center;
          transition: all 0.15s ease;
        }
        .btn-preset:hover {
          filter: brightness(1.2);
          color: var(--primary-text-color, #ffffff);
        }
        .btn-preset.active {
          background: rgba(16, 185, 129, 0.18);
          border-color: #10b981;
          color: #34d399;
          box-shadow: 0 0 8px rgba(16, 185, 129, 0.25);
        }

        /* Unavailable Overlay */
        #unavailable-overlay {
          position: absolute;
          inset: 0;
          background: rgba(20, 23, 33, 0.88);
          backdrop-filter: blur(4px);
          display: none;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          z-index: 50;
          border-radius: 28px;
          padding: 20px;
          text-align: center;
        }
      </style>

      <ha-card id="card-root">
        <div id="unavailable-overlay">
          <h3 style="color: #ef4444; margin: 0 0 8px 0;">Entity Unavailable</h3>
          <p style="margin: 0; font-size: 0.85rem; color: #94a3b8;">Connecting to <strong id="unavail-entity-id">${this._config.entity}</strong>...</p>
        </div>

        <!-- HEADER -->
        <div class="header">
          <div class="header-title">
            <svg viewBox="0 0 24 24">
              <path d="M15 13V5a3 3 0 0 0-6 0v8a5 5 0 1 0 6 0m-3-10a1 1 0 0 1 1 1v4.5a.5.5 0 0 0 1 0V4a1 1 0 0 1 2 0v5.5a.5.5 0 0 0 1 0V7a1 1 0 0 1 2 0v6a7 7 0 1 1-14 0V4a1 1 0 0 1 2 0v3a.5.5 0 0 0 1 0V4a1 1 0 0 1 2 0v5.5a.5.5 0 0 0 1 0V4a1 1 0 0 1 1-1"/>
            </svg>
            <span id="title-text">Dynamic HVAC Control</span>
          </div>
          <div class="version-badge" id="version-badge">v1.0.2 • LOCAL PUSH</div>
        </div>

        <!-- TOP 2-COLUMN GRID (LEFT VERTICAL PLENUM STACK, RIGHT DIAL) -->
        <div class="top-grid" id="top-grid">
          <!-- VERTICAL PLENUM PROBE STACK (Auto-hides if no probes) -->
          <div class="plenum-stack" id="plenum-stack">
            <!-- Box 1: Return Air -->
            <div class="plenum-box">
              <div class="plenum-label">
                <span>📥</span> RETURN AIR (INPUT)
              </div>
              <div class="plenum-value" id="val-return-air">—</div>
              <div class="plenum-sub">Duct Return Intake</div>
            </div>

            <!-- Box 2: Delta-T Split -->
            <div class="plenum-box" id="box-delta-t">
              <div class="plenum-label" id="label-delta-t">
                <span>⚡</span> DELTA-T SPLIT
              </div>
              <div class="plenum-value" id="val-delta-t">—</div>
              <div class="plenum-sub" id="sub-delta-t">Expected: 14°F - 20°F</div>
            </div>

            <!-- Box 3: Supply Air -->
            <div class="plenum-box">
              <div class="plenum-label">
                <span>📤</span> SUPPLY AIR (OUTPUT)
              </div>
              <div class="plenum-value" id="val-supply-air">—</div>
              <div class="plenum-sub">Plenum Supply Duct</div>
            </div>
          </div>

          <!-- CIRCULAR ARC DIAL -->
          <div class="dial-container" id="dial-wrap">
            <svg class="dial-svg" viewBox="0 0 240 240" id="dial-svg">
              <defs>
                <filter id="shadow-knob" x="-40%" y="-40%" width="180%" height="180%">
                  <feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#000000" flood-opacity="0.6"/>
                </filter>
              </defs>

              <!-- Gray Background Track Arc -->
              <path class="dial-track" id="path-track" />

              <!-- Active Colored Arcs -->
              <path class="dial-arc-heat" id="path-arc-heat" />
              <path class="dial-arc-deadband" id="path-arc-deadband" />
              <path class="dial-arc-cool" id="path-arc-cool" />

              <!-- Draggable Knobs -->
              <!-- Heat Knob (Orange) -->
              <g class="dial-knob" id="knob-heat" filter="url(#shadow-knob)">
                <circle id="knob-heat-outer" r="14" fill="#141721" stroke="#f97316" stroke-width="3.5" />
                <circle r="4.5" fill="#ffffff" />
              </g>

              <!-- Cool Knob (Blue) -->
              <g class="dial-knob" id="knob-cool" filter="url(#shadow-knob)">
                <circle id="knob-cool-outer" r="14" fill="#141721" stroke="#0ea5e9" stroke-width="3.5" />
                <circle r="4.5" fill="#ffffff" />
              </g>

              <!-- Single Setpoint Knob (Used for Cool-only or Heat-only) -->
              <g class="dial-knob" id="knob-single" filter="url(#shadow-knob)" style="display: none;">
                <circle id="knob-single-outer" r="14" fill="#141721" stroke="#0ea5e9" stroke-width="3.5" />
                <circle r="4.5" fill="#ffffff" />
              </g>
            </svg>

            <!-- Centered Overlay (Icon, Temp, Fan) -->
            <div class="dial-center-overlay">
              <!-- Top: Status Indicator (Icon-Only) -->
              <div class="status-icon-circle status-idle" id="status-icon-circle" title="System Status">
                <svg id="status-icon-svg" viewBox="0 0 24 24">
                  <path d="M15 13V5a3 3 0 0 0-6 0v8a5 5 0 1 0 6 0m-3-10a1 1 0 0 1 1 1v7.2a2 2 0 0 1 1 1.8 3 3 0 1 1-4-2.8V4a1 1 0 0 1 2 0"/>
                </svg>
              </div>

              <!-- Center: Large Current Temp -->
              <div class="temp-display">
                <span id="current-temp-val">—</span>
                <span class="temp-unit">°F</span>
              </div>

              <!-- Bottom: Minimal Fan Control -->
              <div class="fan-toggle-wrap" id="fan-toggle-btn" title="Toggle Blower Fan" style="display: none;">
                <div class="fan-icon-btn">
                  <svg viewBox="0 0 24 24">
                    <path d="M12 11a1 1 0 1 0 1 1 1 1 0 0 0-1-1m0-9a4 4 0 0 0-4 4c0 1.9 1.3 3.5 3 3.9V4a1 1 0 0 1 2 0v5.9c1.7-.4 3-2 3-3.9a4 4 0 0 0-4-4m-9 14a4 4 0 0 0 4 4c1.9 0 3.5-1.3 3.9-3H5a1 1 0 0 1 0-2h5.9c-.4-1.7-2-3-3.9-3a4 4 0 0 0-4 4m18-4a4 4 0 0 0-4-4c-1.9 0-3.5 1.3-3.9 3H19a1 1 0 0 1 0 2h-5.9c.4 1.7 2 3 3.9 3a4 4 0 0 0 4-4m-9 5a4 4 0 0 0 4-4c0-1.9-1.3-3.5-3-3.9V19a1 1 0 0 1-2 0v-5.9c-1.7.4-3 2-3 3.9a4 4 0 0 0 4 4"/>
                  </svg>
                </div>
                <div class="fan-text-label" id="fan-text-label">FAN OFF</div>
              </div>
            </div>
          </div>
        </div>

        <!-- TARGET RANGE SECTION (Non-destructive DOM elements) -->
        <div class="target-range-box">
          <!-- View 1: Heat/Cool Range -->
          <div class="target-range-headline" id="range-headline-heat-cool">
            <span>Target Range:</span>
            <span class="target-heat-tag" id="target-heat-label">64°F (Heat)</span>
            <span>—</span>
            <span class="target-cool-tag" id="target-cool-label">74°F (Cool)</span>
          </div>

          <!-- View 2: Single Setpoint (Cool only or Heat only) -->
          <div class="target-range-headline" id="range-headline-single" style="display: none;">
            <span>Target Setpoint:</span>
            <span id="target-single-label" class="target-cool-tag">72°F</span>
          </div>

          <!-- View 3: System Off -->
          <div class="target-range-headline" id="range-headline-off" style="display: none;">
            <span>System Mode:</span>
            <span style="color: var(--secondary-text-color, #94a3b8);">OFF</span>
          </div>

          <!-- Subline: House Average & Wall Breakdown -->
          <div class="target-range-subline" id="target-range-subline">
            <span>Average House: <strong id="sub-avg-temp">—</strong></span>
            <span>•</span>
            <span>Wall Thermostat: <strong id="sub-wall-temp">—</strong></span>
          </div>
        </div>

        <!-- STEPPERS FOR PRECISE TARGET ADJUSTMENT -->
        <!-- Dual Steppers (Heat/Cool Mode) -->
        <div class="stepper-row" id="stepper-row-dual">
          <div class="stepper-group">
            <button class="btn-step" id="btn-minus-low" title="Lower Heat Target">−</button>
            <span class="stepper-label target-heat-tag">Heat</span>
            <button class="btn-step" id="btn-plus-low" title="Raise Heat Target">+</button>
          </div>
          <span style="font-size: 0.75rem; color: var(--secondary-text-color, #64748b);">|</span>
          <div class="stepper-group">
            <button class="btn-step" id="btn-minus-high" title="Lower Cool Target">−</button>
            <span class="stepper-label target-cool-tag">Cool</span>
            <button class="btn-step" id="btn-plus-high" title="Raise Cool Target">+</button>
          </div>
        </div>

        <!-- Single Steppers (Cool or Heat Mode) -->
        <div class="stepper-row" id="stepper-row-single" style="display: none;">
          <div class="stepper-group">
            <button class="btn-step" id="btn-minus-single" title="Lower Target">−</button>
            <span class="stepper-label" id="label-step-single">Target</span>
            <button class="btn-step" id="btn-plus-single" title="Raise Target">+</button>
          </div>
        </div>

        <!-- MODE SELECTOR BUTTONS -->
        <div class="mode-row">
          <button class="btn-mode active" id="btn-mode-heat-cool" data-mode="heat_cool">
            <svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 0 0-7.07 17.07l14.14-14.14A9.95 9.95 0 0 0 12 2m0 20a10 10 0 0 0 7.07-17.07L4.93 19.07A9.95 9.95 0 0 0 12 22"/></svg>
            <span>Heat/Cool</span>
          </button>
          <button class="btn-mode" id="btn-mode-cool" data-mode="cool">
            <svg viewBox="0 0 24 24"><path d="M19 11h-4.17l2.59-2.59-1.42-1.41L12 11V6h2V4h-2V2h-2v2H8v2h2v5L5.99 6.99 4.58 8.41 7.17 11H3v2h4.17l-2.58 2.59 1.41 1.41L10 13v5H8v2h2v2h2v-2h2v-2h-2v-5l4.01 4.01 1.41-1.41L16.83 13H21z"/></svg>
            <span>Cool</span>
          </button>
          <button class="btn-mode" id="btn-mode-heat" data-mode="heat">
            <svg viewBox="0 0 24 24"><path d="M12 23c-4.97 0-9-4.03-9-9 0-3.32 1.83-6.23 4.57-7.74.37-.2.83.05.86.48.15 2.16 1.4 3.99 3.27 4.78.29.12.59-.14.53-.45-.42-2.12.18-4.32 1.6-5.83.33-.35.88-.13.91.35.15 2.45 1.54 4.52 3.6 5.48.33.15.68-.13.62-.49-.24-1.44-.06-2.91.53-4.22.18-.39.73-.39.88.02C20.44 11.23 21 12.83 21 14.5c0 4.97-4.03 8.5-9 8.5"/></svg>
            <span>Heat</span>
          </button>
          <button class="btn-mode" id="btn-mode-off" data-mode="off">
            <svg viewBox="0 0 24 24"><path d="M16.56 5.44l-1.45 1.45A5.969 5.969 0 0 1 18 12c0 3.31-2.69 6-6 6s-6-2.69-6-6c0-2.12 1.1-3.99 2.89-5.11L7.44 5.44A7.96 7.96 0 0 0 4 12c0 4.42 3.58 8 8 8s8-3.58 8-8c0-2.55-1.19-4.83-3.44-6.56M13 3h-2v10h2V3z"/></svg>
            <span>Off</span>
          </button>
        </div>

        <!-- PRESET BUTTONS -->
        <div class="preset-row">
          <button class="btn-preset" id="btn-preset-eco" data-preset="eco">Eco</button>
          <button class="btn-preset active" id="btn-preset-comfort" data-preset="comfort">Comfort</button>
          <button class="btn-preset" id="btn-preset-sleep" data-preset="sleep">Sleep</button>
          <button class="btn-preset" id="btn-preset-away" data-preset="away">Away</button>
          <button class="btn-preset" id="btn-preset-vacation" data-preset="vacation">Vacation</button>
          <button class="btn-preset" id="btn-preset-none" data-preset="none">Hold</button>
        </div>
      </ha-card>
    `;

    this._bindEvents();
    this._initArcGeometry();
  }

  _renderUnavailable() {
    const overlay = this.shadowRoot.getElementById('unavailable-overlay');
    if (overlay) {
      overlay.style.display = 'flex';
      const entityLabel = this.shadowRoot.getElementById('unavail-entity-id');
      if (entityLabel) entityLabel.textContent = this._config.entity;
    }
  }

  _hideUnavailable() {
    const overlay = this.shadowRoot.getElementById('unavailable-overlay');
    if (overlay) {
      overlay.style.display = 'none';
    }
  }

  /* -------------------------------------------------------------------------
   * Dial Arc Geometry Calculation (240x240 SVG, Center 120, 120, Radius 86)
   * Arc spans from 135 deg (bottom-left) to 45 deg (bottom-right) -> 270 deg
   * ------------------------------------------------------------------------- */
  _initArcGeometry() {
    this._cx = 120;
    this._cy = 120;
    this._radius = 86;
    this._startAngle = 135; // degrees
    this._endAngle = 405;   // degrees (135 + 270)
    this._totalAngle = 270;

    const track = this.shadowRoot.getElementById('path-track');
    if (track) {
      track.setAttribute('d', this._describeArc(this._cx, this._cy, this._radius, this._startAngle, this._endAngle));
    }
  }

  _polarToCartesian(cx, cy, radius, angleDegrees) {
    const rad = (angleDegrees - 90) * Math.PI / 180.0;
    return {
      x: cx + (radius * Math.cos(rad)),
      y: cy + (radius * Math.sin(rad))
    };
  }

  _describeArc(x, y, radius, startAngle, endAngle) {
    const start = this._polarToCartesian(x, y, radius, endAngle);
    const end = this._polarToCartesian(x, y, radius, startAngle);
    const largeArcFlag = (endAngle - startAngle) <= 180 ? "0" : "1";
    return [
      "M", start.x, start.y,
      "A", radius, radius, 0, largeArcFlag, 0, end.x, end.y
    ].join(" ");
  }

  _tempToAngle(temp) {
    const min = this._config.min_temp || 60;
    const max = this._config.max_temp || 85;
    const clamped = Math.max(min, Math.min(max, temp));
    const fraction = (clamped - min) / (max - min);
    return this._startAngle + (fraction * this._totalAngle);
  }

  _angleToTemp(angle) {
    const min = this._config.min_temp || 60;
    const max = this._config.max_temp || 85;
    let normalized = angle;
    while (normalized < this._startAngle) normalized += 360;
    while (normalized > this._endAngle) normalized -= 360;
    const fraction = Math.max(0, Math.min(1, (normalized - this._startAngle) / this._totalAngle));
    const raw = min + (fraction * (max - min));
    const step = this._config.step || 1.0;
    return Math.round(raw / step) * step;
  }

  /* -------------------------------------------------------------------------
   * State Updates & Data Binding
   * ------------------------------------------------------------------------- */
  _updateCard(stateObj) {
    const attrs = stateObj.attributes || {};
    const root = this.shadowRoot;

    // Header title
    const titleEl = root.getElementById('title-text');
    if (titleEl) titleEl.textContent = this._config.name || attrs.friendly_name || "Dynamic HVAC Control";

    // Current Room Temperature
    const currentTemp = attrs.current_temperature !== undefined ? attrs.current_temperature : null;
    const tempValEl = root.getElementById('current-temp-val');
    if (tempValEl) {
      tempValEl.textContent = (typeof currentTemp === 'number') ? currentTemp.toFixed(1) : (currentTemp ? currentTemp : '—');
    }

    const minT = this._config.min_temp || 60;
    const maxT = this._config.max_temp || 85;
    const hvacMode = stateObj.state || 'off';
    const isHeatCool = hvacMode === 'heat_cool';

    // Only sync setpoints from attributes if user is not currently dragging knobs
    if (!this._dragging) {
      this._tempLow = attrs.target_temp_low !== undefined ? attrs.target_temp_low : (attrs.target_temperature_low || 64);
      this._tempHigh = attrs.target_temp_high !== undefined ? attrs.target_temp_high : (attrs.target_temperature_high || 74);
      this._tempSingle = attrs.temperature !== undefined ? attrs.temperature : (isHeatCool ? 70 : (hvacMode === 'heat' ? this._tempLow : this._tempHigh));
    }

    // Update Arc paths and Knob Positions
    const pathHeat = root.getElementById('path-arc-heat');
    const pathDeadband = root.getElementById('path-arc-deadband');
    const pathCool = root.getElementById('path-arc-cool');
    const knobHeat = root.getElementById('knob-heat');
    const knobCool = root.getElementById('knob-cool');
    const knobSingle = root.getElementById('knob-single');
    const knobSingleOuter = root.getElementById('knob-single-outer');

    if (isHeatCool) {
      const angleHeat = this._tempToAngle(this._tempLow);
      const angleCool = this._tempToAngle(this._tempHigh);

      if (pathHeat) {
        pathHeat.setAttribute('d', this._describeArc(this._cx, this._cy, this._radius, this._startAngle, angleHeat));
        pathHeat.style.display = 'block';
      }
      if (pathDeadband && angleCool > angleHeat) {
        pathDeadband.setAttribute('d', this._describeArc(this._cx, this._cy, this._radius, angleHeat, angleCool));
        pathDeadband.style.display = 'block';
      }
      if (pathCool) {
        pathCool.setAttribute('d', this._describeArc(this._cx, this._cy, this._radius, angleCool, this._endAngle));
        pathCool.style.display = 'block';
      }

      if (knobHeat) {
        const posH = this._polarToCartesian(this._cx, this._cy, this._radius, angleHeat);
        knobHeat.setAttribute('transform', `translate(${posH.x}, ${posH.y})`);
        knobHeat.style.display = 'block';
      }
      if (knobCool) {
        const posC = this._polarToCartesian(this._cx, this._cy, this._radius, angleCool);
        knobCool.setAttribute('transform', `translate(${posC.x}, ${posC.y})`);
        knobCool.style.display = 'block';
      }
      if (knobSingle) knobSingle.style.display = 'none';

    } else if (hvacMode === 'cool') {
      const angleSingle = this._tempToAngle(this._tempSingle);
      if (pathHeat) pathHeat.style.display = 'none';
      if (pathDeadband) pathDeadband.style.display = 'none';
      if (pathCool) {
        pathCool.setAttribute('d', this._describeArc(this._cx, this._cy, this._radius, angleSingle, this._endAngle));
        pathCool.style.display = 'block';
      }
      if (knobHeat) knobHeat.style.display = 'none';
      if (knobCool) knobCool.style.display = 'none';
      if (knobSingle && knobSingleOuter) {
        const posS = this._polarToCartesian(this._cx, this._cy, this._radius, angleSingle);
        knobSingle.setAttribute('transform', `translate(${posS.x}, ${posS.y})`);
        knobSingleOuter.setAttribute('stroke', '#0ea5e9');
        knobSingle.style.display = 'block';
      }

    } else if (hvacMode === 'heat') {
      const angleSingle = this._tempToAngle(this._tempSingle);
      if (pathHeat) {
        pathHeat.setAttribute('d', this._describeArc(this._cx, this._cy, this._radius, this._startAngle, angleSingle));
        pathHeat.style.display = 'block';
      }
      if (pathDeadband) pathDeadband.style.display = 'none';
      if (pathCool) pathCool.style.display = 'none';
      if (knobHeat) knobHeat.style.display = 'none';
      if (knobCool) knobCool.style.display = 'none';
      if (knobSingle && knobSingleOuter) {
        const posS = this._polarToCartesian(this._cx, this._cy, this._radius, angleSingle);
        knobSingle.setAttribute('transform', `translate(${posS.x}, ${posS.y})`);
        knobSingleOuter.setAttribute('stroke', '#f97316');
        knobSingle.style.display = 'block';
      }

    } else {
      // Off
      if (pathHeat) pathHeat.style.display = 'none';
      if (pathDeadband) pathDeadband.style.display = 'none';
      if (pathCool) pathCool.style.display = 'none';
      if (knobHeat) knobHeat.style.display = 'none';
      if (knobCool) knobCool.style.display = 'none';
      if (knobSingle) knobSingle.style.display = 'none';
    }

    // Status Indicator Icon (Icon-Only)
    const statusWrap = root.getElementById('status-icon-circle');
    const statusSvg = root.getElementById('status-icon-svg');
    const hvacAction = attrs.hvac_action || (hvacMode === 'off' ? 'off' : 'idle');

    if (statusWrap && statusSvg) {
      statusWrap.className = 'status-icon-circle';
      if (hvacAction === 'cooling') {
        statusWrap.classList.add('status-cool');
        statusSvg.innerHTML = `<path d="M19 11h-4.17l2.59-2.59-1.42-1.41L12 11V6h2V4h-2V2h-2v2H8v2h2v5L5.99 6.99 4.58 8.41 7.17 11H3v2h4.17l-2.58 2.59 1.41 1.41L10 13v5H8v2h2v2h2v-2h2v-2h-2v-5l4.01 4.01 1.41-1.41L16.83 13H21z"/>`;
      } else if (hvacAction === 'heating') {
        statusWrap.classList.add('status-heat');
        statusSvg.innerHTML = `<path d="M12 23c-4.97 0-9-4.03-9-9 0-3.32 1.83-6.23 4.57-7.74.37-.2.83.05.86.48.15 2.16 1.4 3.99 3.27 4.78.29.12.59-.14.53-.45-.42-2.12.18-4.32 1.6-5.83.33-.35.88-.13.91.35.15 2.45 1.54 4.52 3.6 5.48.33.15.68-.13.62-.49-.24-1.44-.06-2.91.53-4.22.18-.39.73-.39.88.02C20.44 11.23 21 12.83 21 14.5c0 4.97-4.03 8.5-9 8.5"/>`;
      } else if (hvacMode === 'off') {
        statusWrap.classList.add('status-off');
        statusSvg.innerHTML = `<path d="M16.56 5.44l-1.45 1.45A5.969 5.969 0 0 1 18 12c0 3.31-2.69 6-6 6s-6-2.69-6-6c0-2.12 1.1-3.99 2.89-5.11L7.44 5.44A7.96 7.96 0 0 0 4 12c0 4.42 3.58 8 8 8s8-3.58 8-8c0-2.55-1.19-4.83-3.44-6.56M13 3h-2v10h2V3z"/>`;
      } else {
        // Idle (Green thermometer)
        statusWrap.classList.add('status-idle');
        statusSvg.innerHTML = `<path d="M15 13V5a3 3 0 0 0-6 0v8a5 5 0 1 0 6 0m-3-10a1 1 0 0 1 1 1v7.2a2 2 0 0 1 1 1.8 3 3 0 1 1-4-2.8V4a1 1 0 0 1 2 0"/>`;
      }
    }

    // Fan Status & Visibility (Hide if no fan entity configured)
    const fanWrap = root.getElementById('fan-toggle-btn');
    const fanLabel = root.getElementById('fan-text-label');
    const hasFanEntity = Boolean(attrs.fan_entity || (attrs.fan_modes && attrs.fan_modes.length > 0) || this._config.fan_switch);

    const fanState = attrs.fan_state || attrs.fan_mode || 'off';
    const isFanOn = fanState === 'on' || fanState === 'low' || fanState === 'medium' || fanState === 'high';

    if (fanWrap && fanLabel) {
      if (!hasFanEntity) {
        fanWrap.style.display = 'none';
      } else {
        fanWrap.style.display = 'flex';
        if (isFanOn) {
          fanWrap.classList.add('active');
          fanLabel.textContent = 'FAN ON';
        } else {
          fanWrap.classList.remove('active');
          fanLabel.textContent = 'FAN OFF';
        }
      }
    }

    // Duct Plenum Probes (Auto-hide if no probes configured, show "—" when missing)
    const rTemp = attrs.return_air_temperature;
    const rHum = attrs.return_air_humidity;
    const sTemp = attrs.supply_air_temperature;
    const sHum = attrs.supply_air_humidity;
    const deltaT = attrs.delta_t;

    const hasPlenum = (rTemp !== undefined && rTemp !== null) ||
                      (sTemp !== undefined && sTemp !== null) ||
                      Boolean(attrs.return_temp_sensor || attrs.supply_temp_sensor);

    const plenumStack = root.getElementById('plenum-stack');
    const topGrid = root.getElementById('top-grid');
    if (plenumStack && topGrid) {
      if (!hasPlenum) {
        plenumStack.style.display = 'none';
        topGrid.classList.add('no-plenum');
      } else {
        plenumStack.style.display = 'flex';
        topGrid.classList.remove('no-plenum');
      }
    }

    const valReturnAir = root.getElementById('val-return-air');
    if (valReturnAir) {
      if (rTemp !== undefined && rTemp !== null) {
        valReturnAir.textContent = `${Number(rTemp).toFixed(1)}°F${(rHum !== undefined && rHum !== null) ? ' / ' + Number(rHum).toFixed(0) + '% RH' : ''}`;
      } else {
        valReturnAir.textContent = '—';
      }
    }

    const valSupplyAir = root.getElementById('val-supply-air');
    if (valSupplyAir) {
      if (sTemp !== undefined && sTemp !== null) {
        valSupplyAir.textContent = `${Number(sTemp).toFixed(1)}°F${(sHum !== undefined && sHum !== null) ? ' / ' + Number(sHum).toFixed(0) + '% RH' : ''}`;
      } else {
        valSupplyAir.textContent = '—';
      }
    }

    const valDeltaT = root.getElementById('val-delta-t');
    const boxDeltaT = root.getElementById('box-delta-t');
    const labelDeltaT = root.getElementById('label-delta-t');
    const subDeltaT = root.getElementById('sub-delta-t');

    if (valDeltaT) {
      if (deltaT !== undefined && deltaT !== null) {
        const absDelta = Math.abs(deltaT).toFixed(1);
        const isCooling = hvacAction === 'cooling';
        const isHeating = hvacAction === 'heating';

        // Delta-T Optimal Check: Mode and Blower aware!
        const isOptimalCool = isCooling && isFanOn && absDelta >= 14.0 && absDelta <= 20.0;
        const isOptimalHeat = isHeating && isFanOn && absDelta >= 20.0 && absDelta <= 45.0;
        const isOptimal = isOptimalCool || isOptimalHeat;

        const dirStr = deltaT < 0 ? 'Drop' : 'Rise';
        valDeltaT.textContent = `${absDelta}°F ${dirStr}${isOptimal ? ' (Optimal)' : ''}`;

        if (subDeltaT) {
          subDeltaT.textContent = isHeating ? 'Expected: 20°F - 45°F Rise' : 'Expected: 14°F - 20°F Drop';
        }
        if (boxDeltaT) boxDeltaT.className = `plenum-box ${isOptimal ? 'highlight' : ''}`;
        if (labelDeltaT) labelDeltaT.className = `plenum-label ${isOptimal ? 'optimal' : ''}`;
      } else {
        valDeltaT.textContent = '—';
        if (boxDeltaT) boxDeltaT.className = 'plenum-box';
        if (labelDeltaT) labelDeltaT.className = 'plenum-label';
      }
    }

    // Target Range Headline Views (Non-destructive DOM switching)
    const viewHeatCool = root.getElementById('range-headline-heat-cool');
    const viewSingle = root.getElementById('range-headline-single');
    const viewOff = root.getElementById('range-headline-off');
    const heatLabel = root.getElementById('target-heat-label');
    const coolLabel = root.getElementById('target-cool-label');
    const singleLabel = root.getElementById('target-single-label');

    if (viewHeatCool && viewSingle && viewOff) {
      if (isHeatCool) {
        if (heatLabel) heatLabel.textContent = `${this._tempLow.toFixed(0)}°F (Heat)`;
        if (coolLabel) coolLabel.textContent = `${this._tempHigh.toFixed(0)}°F (Cool)`;
        viewHeatCool.style.display = 'flex';
        viewSingle.style.display = 'none';
        viewOff.style.display = 'none';
      } else if (hvacMode === 'cool') {
        if (singleLabel) {
          singleLabel.textContent = `${this._tempSingle.toFixed(0)}°F (Cool)`;
          singleLabel.className = 'target-cool-tag';
        }
        viewHeatCool.style.display = 'none';
        viewSingle.style.display = 'flex';
        viewOff.style.display = 'none';
      } else if (hvacMode === 'heat') {
        if (singleLabel) {
          singleLabel.textContent = `${this._tempSingle.toFixed(0)}°F (Heat)`;
          singleLabel.className = 'target-heat-tag';
        }
        viewHeatCool.style.display = 'none';
        viewSingle.style.display = 'flex';
        viewOff.style.display = 'none';
      } else {
        viewHeatCool.style.display = 'none';
        viewSingle.style.display = 'none';
        viewOff.style.display = 'flex';
      }
    }

    // Steppers Row Visibility & Adaptability
    const dualSteppers = root.getElementById('stepper-row-dual');
    const singleSteppers = root.getElementById('stepper-row-single');
    const labelStepSingle = root.getElementById('label-step-single');

    if (dualSteppers && singleSteppers) {
      if (isHeatCool) {
        dualSteppers.style.display = 'flex';
        singleSteppers.style.display = 'none';
      } else if (hvacMode === 'cool' || hvacMode === 'heat') {
        dualSteppers.style.display = 'none';
        singleSteppers.style.display = 'flex';
        if (labelStepSingle) {
          labelStepSingle.textContent = hvacMode === 'heat' ? 'Heat' : 'Cool';
          labelStepSingle.className = hvacMode === 'heat' ? 'stepper-label target-heat-tag' : 'stepper-label target-cool-tag';
        }
      } else {
        dualSteppers.style.display = 'none';
        singleSteppers.style.display = 'none';
      }
    }

    // Average House & Wall Thermostat Breakdown (True data, no hardcoded dummy fallbacks)
    const subAvg = root.getElementById('sub-avg-temp');
    const subWall = root.getElementById('sub-wall-temp');
    const inHum = attrs.indoor_humidity;
    if (subAvg) {
      if (currentTemp !== null && currentTemp !== undefined) {
        const avgStr = (typeof currentTemp === 'number') ? `${currentTemp.toFixed(1)}°F` : `${currentTemp}°F`;
        subAvg.textContent = (inHum !== null && inHum !== undefined) ? `${avgStr} / ${inHum}% RH` : avgStr;
      } else {
        subAvg.textContent = '—';
      }
    }

    if (subWall) {
      const wTemp = attrs.wall_thermostat_temperature;
      const wHum = attrs.wall_thermostat_humidity;
      if (wTemp !== undefined && wTemp !== null) {
        subWall.textContent = `${Number(wTemp).toFixed(1)}°F${(wHum !== undefined && wHum !== null) ? ' / ' + wHum + '% RH' : ''}`;
      } else {
        subWall.textContent = '—';
      }
    }

    // Update Mode Buttons Active State
    root.querySelectorAll('.btn-mode').forEach(btn => {
      const m = btn.getAttribute('data-mode');
      btn.className = 'btn-mode';
      if (m === hvacMode) {
        if (m === 'heat_cool') btn.classList.add('active');
        else if (m === 'heat') btn.classList.add('active-heat');
        else if (m === 'cool') btn.classList.add('active-cool');
        else if (m === 'off') btn.classList.add('active-off');
      }
    });

    // Update Preset Buttons Active State
    const activePreset = attrs.preset_mode || 'none';
    root.querySelectorAll('.btn-preset').forEach(btn => {
      const p = btn.getAttribute('data-preset');
      if (p === activePreset || (p === 'none' && (!activePreset || activePreset === 'none'))) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
  }

  /* -------------------------------------------------------------------------
   * Interactive Event Listeners (Dragging, Steppers, Service Calls)
   * ------------------------------------------------------------------------- */
  _bindEvents() {
    const root = this.shadowRoot;

    // Fan Toggle click
    const fanBtn = root.getElementById('fan-toggle-btn');
    if (fanBtn) {
      fanBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this._toggleFan();
      });
    }

    // Mode Buttons
    root.querySelectorAll('.btn-mode').forEach(btn => {
      btn.addEventListener('click', () => {
        const mode = btn.getAttribute('data-mode');
        this._setHvacMode(mode);
      });
    });

    // Preset Buttons
    root.querySelectorAll('.btn-preset').forEach(btn => {
      btn.addEventListener('click', () => {
        const preset = btn.getAttribute('data-preset');
        this._setPresetMode(preset);
      });
    });

    // Dual Mode Steppers
    const btnMinusLow = root.getElementById('btn-minus-low');
    const btnPlusLow = root.getElementById('btn-plus-low');
    const btnMinusHigh = root.getElementById('btn-minus-high');
    const btnPlusHigh = root.getElementById('btn-plus-high');

    if (btnMinusLow) btnMinusLow.addEventListener('click', () => this._stepTemp('low', -1));
    if (btnPlusLow) btnPlusLow.addEventListener('click', () => this._stepTemp('low', 1));
    if (btnMinusHigh) btnMinusHigh.addEventListener('click', () => this._stepTemp('high', -1));
    if (btnPlusHigh) btnPlusHigh.addEventListener('click', () => this._stepTemp('high', 1));

    // Single Mode Steppers (Works in Cool and Heat mode)
    const btnMinusSingle = root.getElementById('btn-minus-single');
    const btnPlusSingle = root.getElementById('btn-plus-single');

    if (btnMinusSingle) btnMinusSingle.addEventListener('click', () => this._stepTemp('single', -1));
    if (btnPlusSingle) btnPlusSingle.addEventListener('click', () => this._stepTemp('single', 1));

    // Knob Dragging Interaction
    const knobHeat = root.getElementById('knob-heat');
    const knobCool = root.getElementById('knob-cool');
    const knobSingle = root.getElementById('knob-single');

    if (knobHeat) {
      knobHeat.addEventListener('pointerdown', (e) => this._startDrag('low', e));
    }
    if (knobCool) {
      knobCool.addEventListener('pointerdown', (e) => this._startDrag('high', e));
    }
    if (knobSingle) {
      knobSingle.addEventListener('pointerdown', (e) => this._startDrag('single', e));
    }

    window.addEventListener('pointermove', (e) => this._onDrag(e));
    window.addEventListener('pointerup', () => this._endDrag());
  }

  _getMinGap() {
    if (!this._hass || !this._config.entity) return 3.0;
    const stateObj = this._hass.states[this._config.entity];
    const attrs = stateObj ? stateObj.attributes || {} : {};
    const cSwing = typeof attrs.cooling_swing === 'number' ? attrs.cooling_swing : 2.0;
    const hSwing = typeof attrs.heating_swing === 'number' ? attrs.heating_swing : 1.0;
    return Math.max(3.0, cSwing + hSwing);
  }

  _startDrag(target, event) {
    this._dragging = target;
    event.preventDefault();
  }

  _onDrag(event) {
    if (!this._dragging) return;
    const svg = this.shadowRoot.getElementById('dial-svg');
    if (!svg) return;

    const rect = svg.getBoundingClientRect();
    const x = event.clientX - rect.left - (rect.width / 2);
    const y = event.clientY - rect.top - (rect.height / 2);

    let rad = Math.atan2(y, x);
    let deg = (rad * 180 / Math.PI) + 90;
    if (deg < 0) deg += 360;

    const temp = this._angleToTemp(deg);
    const minT = this._config.min_temp || 60;
    const maxT = this._config.max_temp || 85;

    const minGap = this._getMinGap();
    if (this._dragging === 'low') {
      const newLow = Math.min(temp, this._tempHigh - minGap);
      this._tempLow = Math.max(minT, newLow);
    } else if (this._dragging === 'high') {
      const newHigh = Math.max(temp, this._tempLow + minGap);
      this._tempHigh = Math.min(maxT, newHigh);
    } else if (this._dragging === 'single') {
      this._tempSingle = Math.max(minT, Math.min(maxT, temp));
    }

    // Instant local visual feedback
    const stateObj = this._hass.states[this._config.entity];
    if (stateObj) this._updateCard(stateObj);
  }

  _endDrag() {
    if (!this._dragging) return;
    this._dragging = null;
    this._commitTemperature();
  }

  _stepTemp(target, delta) {
    const minT = this._config.min_temp || 60;
    const maxT = this._config.max_temp || 85;

    const minGap = this._getMinGap();
    if (target === 'low') {
      this._tempLow = Math.max(minT, Math.min(this._tempHigh - minGap, this._tempLow + delta));
    } else if (target === 'high') {
      this._tempHigh = Math.max(this._tempLow + minGap, Math.min(maxT, this._tempHigh + delta));
    } else if (target === 'single') {
      this._tempSingle = Math.max(minT, Math.min(maxT, this._tempSingle + delta));
    }

    const stateObj = this._hass.states[this._config.entity];
    if (stateObj) this._updateCard(stateObj);
    this._commitTemperature();
  }

  _commitTemperature() {
    if (!this._hass || !this._config.entity) return;
    const stateObj = this._hass.states[this._config.entity];
    const isHeatCool = stateObj && stateObj.state === 'heat_cool';

    if (isHeatCool) {
      this._hass.callService("climate", "set_temperature", {
        entity_id: this._config.entity,
        target_temp_low: this._tempLow,
        target_temp_high: this._tempHigh
      });
    } else {
      this._hass.callService("climate", "set_temperature", {
        entity_id: this._config.entity,
        temperature: this._tempSingle
      });
    }
  }

  _setHvacMode(mode) {
    if (!this._hass || !this._config.entity) return;
    this._hass.callService("climate", "set_hvac_mode", {
      entity_id: this._config.entity,
      hvac_mode: mode
    });
  }

  _setPresetMode(preset) {
    if (!this._hass || !this._config.entity) return;
    this._hass.callService("climate", "set_preset_mode", {
      entity_id: this._config.entity,
      preset_mode: preset
    });
  }

  _toggleFan() {
    if (!this._hass || !this._config.entity) return;
    const stateObj = this._hass.states[this._config.entity];
    const attrs = stateObj ? stateObj.attributes : {};
    const fanState = attrs.fan_state || attrs.fan_mode || 'off';
    const isFanOn = fanState === 'on' || fanState === 'low' || fanState === 'medium' || fanState === 'high';
    const nextMode = isFanOn ? 'auto' : 'on';

    if (this._config.fan_switch) {
      this._hass.callService("switch", isFanOn ? "turn_off" : "turn_on", {
        entity_id: this._config.fan_switch
      });
    } else {
      this._hass.callService("climate", "set_fan_mode", {
        entity_id: this._config.entity,
        fan_mode: nextMode
      });
    }
  }
}

// Register with Home Assistant Lovelace
if (!customElements.get('dynamic-hvac-control-card')) {
  customElements.define('dynamic-hvac-control-card', DynamicHvacControlCard);
}

// Add Card to HA UI Card Picker
window.customCards = window.customCards || [];
window.customCards.push({
  type: "dynamic-hvac-control-card",
  name: "Dynamic HVAC Control Card",
  description: "Redesigned circular dual-slider thermostat with plenum diagnostics, Delta-T split, and fan control",
  preview: true,
  documentationURL: "https://github.com/Tinkergnome621/dynamic_hvac_control"
});

console.info(
  "%c DYNAMIC-HVAC-CONTROL-CARD %c v1.0.2 ",
  "color: white; background: #0284c7; font-weight: 700; border-radius: 4px 0 0 4px; padding: 2px 6px;",
  "color: white; background: #0f172a; font-weight: 700; border-radius: 0 4px 4px 0; padding: 2px 6px;"
);
