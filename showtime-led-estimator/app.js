/* ============================================================================
   SHOWTIME LED — "Build Your Screen Package" Estimator
   Plain HTML / CSS / vanilla JavaScript. No frameworks, no build step.
   ============================================================================
   FILE MAP
     - SHOWTIME_CONFIG   : all pricing, inventory, and rule data lives here.
     - Utilities          : formatting / escaping / small helpers.
     - State              : load/save/reset of the wizard's answers.
     - Recommendation     : transparent rule-based screen suggestions.
     - Pricing             : turns state into a low/high estimate breakdown.
     - Rendering           : builds each wizard step's HTML.
     - Navigation          : step changes, validation, progress.
     - Lead capture/output : URL build, postMessage, mailto, clipboard.
     - Iframe height       : keeps the Wix embed sized to its content.
   ==========================================================================*/

/* ============================================================================
   SHOWTIME_CONFIG
   Every price, inventory count, and rule the calculator uses lives in this
   single object. Nothing outside this object should contain a dollar amount.

   ****************************************************************
   *  REPLACE SAMPLE VALUES WITH APPROVED SHOWTIME LED PRICING     *
   *  BEFORE PUBLISHING.                                            *
   ****************************************************************
   ==========================================================================*/
const SHOWTIME_CONFIG = {

  // --------------------------------------------------------------------
  // COMPANY INFORMATION — REPLACE SAMPLE VALUES BEFORE PUBLISHING.
  // --------------------------------------------------------------------
  company: {
    name: "Showtime LED",
    email: "quotes@showtimeled.com",       // used by the "Email Me This Estimate" mailto link
    phone: "(816) 555-0100",
    website: "https://www.showtimeled.com"
  },

  // The Wix page the "Request Exact Quote" button opens (target="_top").
  // REPLACE with the live Wix quote-request page URL before publishing.
  quotePageUrl: "https://www.showtimeled.com/get-a-quote",

  // Home base used for the travel-tier labels and as the reference point
  // for the manual distance selector (no live mileage lookups are performed).
  startingLocation: {
    label: "Kansas City, MO",
    zip: "64105"
  },

  // --------------------------------------------------------------------
  // SCREEN INVENTORY
  // dailyRate = equipment cost per unit, per operating day (sample values).
  // transportWeight = how much of a delivery vehicle one unit consumes,
  //   used to estimate how many vehicles a package requires.
  // large = counts toward the "more than two large screens" custom-quote rule.
  // --------------------------------------------------------------------
  inventory: [
    {
      id: "trailer-12x7",
      name: "12×7 Mobile LED Trailer",
      dims: "12 ft × 7 ft LED wall",
      shortDescription: "A self-contained, road-ready mobile LED trailer sized for neighborhood and mid-size events.",
      bestFor: ["Movie nights", "Schools", "Pools", "Community events", "Medium-size watch parties", "Corporate gatherings"],
      totalInventory: 2,
      unitLabel: "trailer",
      dailyRate: { low: 900, high: 1300 },
      transportWeight: 1,
      large: true,
      doubleSided: false,
      configurable: false
    },
    {
      id: "trailer-16x9",
      name: "16×9 Mobile LED Trailer",
      dims: "16 ft × 9 ft LED wall",
      shortDescription: "Our largest single-face trailer, built for big crowds and high-impact productions.",
      bestFor: ["Major watch parties", "Festivals", "Sporting events", "Concerts", "Large crowds", "High-impact productions"],
      totalInventory: 2,
      unitLabel: "trailer",
      dailyRate: { low: 1500, high: 2100 },
      transportWeight: 1,
      large: true,
      doubleSided: false,
      configurable: false
    },
    {
      id: "trailer-10x6-double",
      name: "10×6 Double-Sided Mobile LED Trailer",
      dims: "10 ft × 6 ft LED per side",
      shortDescription: "One trailer with two LED viewing faces.",
      bestFor: ["Streets", "Concourses", "Entrances", "Audiences approaching from opposite directions", "Events requiring two viewing directions from one position"],
      totalInventory: 1,
      unitLabel: "trailer",
      dailyRate: { low: 1400, high: 1900 },
      transportWeight: 1,
      large: true,
      doubleSided: true,
      configurable: false
    },
    {
      id: "modular-led",
      name: "Modular LED Screen",
      dims: "Configurable — approx. 12×7, 16×9, or custom",
      shortDescription: "A build-to-fit modular LED wall for stage integration and custom installs. Every modular project is reviewed by our production team before final pricing.",
      bestFor: ["Concert stages", "Custom installations", "Branded environments", "Locations where a trailer cannot be positioned", "Stage-integrated video"],
      totalInventory: 1,
      unitLabel: "system",
      dailyRate: { low: 2200, high: 3800 },
      transportWeight: 2,
      large: true,
      doubleSided: false,
      configurable: true,
      configOptions: {
        sizes: [
          { id: "approx-12x7", label: "Approximately 12×7" },
          { id: "approx-16x9", label: "Approximately 16×9" },
          { id: "custom", label: "Custom size" }
        ],
        mounts: [
          { id: "ground-stacked", label: "Ground stacked" },
          { id: "stage-mounted", label: "Stage mounted" },
          { id: "truss-mounted", label: "Truss mounted" },
          { id: "unsure", label: "Unsure" }
        ]
      }
    },
    {
      id: "display-2x7",
      name: "2×7 Advertising Display",
      dims: "2 ft × 7 ft LED display",
      shortDescription: "A compact display for sponsor loops, schedules, and directional information alongside a larger screen.",
      bestFor: ["Sponsor loops", "Branding", "Schedules", "Entrance displays", "Directional information", "Supporting displays around a larger event"],
      totalInventory: 2,
      unitLabel: "display",
      dailyRate: { low: 350, high: 550 },
      transportWeight: 0.5,
      large: false,
      doubleSided: false,
      configurable: false
    }
  ],

  // --------------------------------------------------------------------
  // PRESET PACKAGES — quick-select buttons that pick inventory automatically.
  // Presets are not separate inventory; each maps to real inventory lines.
  // --------------------------------------------------------------------
  presets: [
    {
      id: "twin-16x9",
      name: "Twin 16×9 Package",
      description: "Two 16×9 trailers for two audiences or maximum coverage of one large audience.",
      lines: [{ screenId: "trailer-16x9", qty: 2 }]
    },
    {
      id: "main-sponsor",
      name: "Main Screen + Sponsor Displays",
      description: "One 16×9 trailer with two 2×7 advertising displays for sponsor loops and schedules.",
      lines: [{ screenId: "trailer-16x9", qty: 1 }, { screenId: "display-2x7", qty: 2 }]
    },
    {
      id: "double-sided-street",
      name: "Double-Sided Street Package",
      description: "One double-sided trailer covering audiences approaching from two directions.",
      lines: [{ screenId: "trailer-10x6-double", qty: 1 }]
    },
    {
      id: "festival-coverage",
      name: "Festival Coverage Package",
      description: "Two 16×9 trailers plus two advertising displays distributed across a larger venue.",
      lines: [{ screenId: "trailer-16x9", qty: 2 }, { screenId: "display-2x7", qty: 2 }]
    },
    {
      id: "custom-production",
      name: "Custom Production Package",
      description: "A modular LED system for stage-integrated or fully custom productions. Always reviewed for a custom quote.",
      lines: [{ screenId: "modular-led", qty: 1 }]
    }
  ],

  // --------------------------------------------------------------------
  // DURATION ADJUSTMENT — added per unit, per operating day, based on how
  // many hours per day the screens run (more hours = more staffing/power).
  // --------------------------------------------------------------------
  durationTiers: {
    "up-to-4":     { label: "Up to 4 hours",      addPerUnitPerDay: { low: 0,   high: 0 } },
    "4-8":         { label: "4–8 hours",          addPerUnitPerDay: { low: 125, high: 225 } },
    "8-12":        { label: "8–12 hours",         addPerUnitPerDay: { low: 250, high: 425 } },
    "more-than-12":{ label: "More than 12 hours", addPerUnitPerDay: { low: 450, high: 750 } }
  },

  // --------------------------------------------------------------------
  // MULTI-DAY DISCOUNT — applied to the equipment + duration cost of each
  // day after the first. Low estimate uses the larger discount, high
  // estimate uses the smaller discount, which is what keeps the range honest.
  // --------------------------------------------------------------------
  multiDayDiscount: {
    minimumDays: 2,
    percentOffAdditionalDaysLow: 10,
    percentOffAdditionalDaysHigh: 18
  },

  // --------------------------------------------------------------------
  // MULTI-SCREEN DISCOUNT — a modest discount on shared setup/overhead
  // costs (not equipment or transport) when two or more units are booked.
  // --------------------------------------------------------------------
  multiScreenDiscount: {
    minimumUnits: 2,
    percentOffSharedLow: 8,
    percentOffSharedHigh: 15
  },

  // --------------------------------------------------------------------
  // TRAVEL — manual distance tiers, since ZIP codes alone can't produce a
  // trustworthy mileage figure without a real mapping service.
  // ratePerVehicle is charged once per delivery vehicle the package needs.
  // --------------------------------------------------------------------
  travel: {
    tiers: {
      "within-30":   { label: "Within 30 miles of Kansas City", flatFee: { low: 0,   high: 0 },   ratePerVehicle: { low: 0,   high: 0 } },
      "31-75":       { label: "31–75 miles",                    flatFee: { low: 50,  high: 100 }, ratePerVehicle: { low: 75,  high: 125 } },
      "76-150":      { label: "76–150 miles",                   flatFee: { low: 100, high: 175 }, ratePerVehicle: { low: 150, high: 250 } },
      "151-300":     { label: "151–300 miles",                  flatFee: { low: 175, high: 300 }, ratePerVehicle: { low: 300, high: 500 } },
      "more-than-300": { label: "More than 300 miles", customQuote: true },
      "unsure":      { label: "Unsure", flatFee: { low: 100, high: 175 }, ratePerVehicle: { low: 150, high: 250 }, pendingConfirmation: true }
    }
  },

  // --------------------------------------------------------------------
  // SETUP CHARGES — crew time to deliver, set up, and strike the package.
  // --------------------------------------------------------------------
  setup: {
    baseFirstUnit: { low: 150, high: 300 },
    perAdditionalUnit: { low: 75, high: 150 },
    dayBeforeSetupAdd: { low: 100, high: 200 },
    multipleSetupDaysPerExtraDay: { low: 150, high: 300 }
  },

  // --------------------------------------------------------------------
  // HOLD-DAY CHARGES — per day the equipment sits on site without being
  // actively struck (overnight holds, multi-day festivals, etc).
  // --------------------------------------------------------------------
  holdDay: {
    perLargeUnitPerDay: { low: 75, high: 150 },
    perSmallUnitPerDay: { low: 25, high: 50 }
  },

  // --------------------------------------------------------------------
  // CREW ADD-ONS — a standard operator is included in the equipment rate.
  // --------------------------------------------------------------------
  crew: {
    additionalOperatorPerDay: { low: 250, high: 400 },
    imagIntegrationPerDay: { low: 400, high: 800 }
  },

  // --------------------------------------------------------------------
  // PRODUCTION SUPPORT ADD-ONS (flat, per event unless noted)
  // --------------------------------------------------------------------
  productionAddons: {
    "on-screen-graphics":     { label: "On-screen graphics",              low: 100, high: 250 },
    "sponsor-loop-playback":  { label: "Sponsor-loop playback",           low: 75,  high: 150 },
    "remote-content-mgmt":    { label: "Remote content management",      low: 100, high: 200 },
    "client-provides-feed":   { label: "Client provides the finished feed", low: 0, high: 0 },
    "additional-planning":    { label: "Additional production planning", low: 150, high: 350 },
    "multiple-video-sources": { label: "Multiple video sources",         low: 200, high: 450 }
  },

  // --------------------------------------------------------------------
  // AUDIO ADD-ONS
  // --------------------------------------------------------------------
  audioOptions: {
    "standard":       { label: "Built-in standard audio",        low: 0,   high: 0 },
    "large-system":   { label: "Larger event audio system needed", low: 300, high: 700 },
    "venue-provides": { label: "Venue provides audio",            low: 0,   high: 0 },
    "none":           { label: "No audio required",               low: 0,   high: 0 },
    "unsure":         { label: "Unsure", low: 0, high: 0, pendingConfirmation: true }
  },

  // --------------------------------------------------------------------
  // POWER ADD-ONS
  // --------------------------------------------------------------------
  powerOptions: {
    "venue-power":     { label: "Venue power available",              low: 0,   high: 0 },
    "battery":         { label: "Battery operation requested",        low: 150, high: 350 },
    "generator":       { label: "Generator required",                 low: 250, high: 500 },
    "far-power":       { label: "Power source more than 100 feet away", low: 75, high: 150 },
    "separate-drops":  { label: "Separate power drops available",     low: 0,   high: 0 },
    "unsure":          { label: "Unsure", low: 0, high: 0, pendingConfirmation: true }
  },

  // --------------------------------------------------------------------
  // CONNECTIVITY ADD-ONS
  // --------------------------------------------------------------------
  connectivityOptions: {
    "venue-hdmi":            { label: "Venue provides HDMI feed",           low: 0,   high: 0 },
    "venue-sdi":             { label: "Venue provides SDI feed",            low: 0,   high: 0 },
    "venue-internet":        { label: "Venue internet available",           low: 0,   high: 0 },
    "showtime-connectivity": { label: "Showtime connectivity requested",    low: 150, high: 300 },
    "antenna-tv":            { label: "Digital antenna or local television", low: 75, high: 150 },
    "starlink-cellular":     { label: "Starlink or cellular backup",        low: 200, high: 400 },
    "unsure":                { label: "Unsure", low: 0, high: 0, pendingConfirmation: true }
  },

  // --------------------------------------------------------------------
  // VENUE ACCESS ADJUSTMENTS — folded into the "Setup and crew" line
  // because they change how long setup and teardown take.
  // --------------------------------------------------------------------
  venueAccessOptions: {
    "paved":               { label: "Paved vehicle access",                    low: 0,   high: 0 },
    "grass-uneven":        { label: "Grass or uneven terrain",                 low: 100, high: 250 },
    "restricted-loading":  { label: "Restricted loading area",                 low: 150, high: 350 },
    "indoor-dock":         { label: "Indoor loading dock",                     low: 75,  high: 150 },
    "limited-window":      { label: "Limited setup window",                    low: 150, high: 300 },
    "long-cable-run":      { label: "Long cable run",                          low: 100, high: 200 },
    "far-from-vehicles":   { label: "Screen must be placed far from support vehicles", low: 75, high: 150 },
    "trailer-must-move":   { label: "Trailer must move during the event",      low: 0,   high: 0, triggersCustomQuote: true },
    "overnight":           { label: "Equipment remains overnight",             low: 0,   high: 0, impliesHoldDay: true },
    "security":            { label: "Security may be required",                low: 0,   high: 0, pendingConfirmation: true },
    "unsure":               { label: "Unsure", low: 0, high: 0, pendingConfirmation: true }
  },

  // --------------------------------------------------------------------
  // CUSTOM-QUOTE THRESHOLDS — plain numeric limits referenced by the rule
  // engine below, kept here so they're easy to find and adjust.
  // --------------------------------------------------------------------
  customQuoteThresholds: {
    maxLargeScreensBeforeCustom: 2,
    maxIndependentVideoFeedsBeforeCustom: 2,
    maxEventDaysBeforeCustom: 7,
    maxRecurringDatesBeforeCustom: 5,
    maxUnsureAnswersBeforeCustom: 3
  }
};

/* ============================================================================
   UTILITIES
   ==========================================================================*/

// Escapes user-entered text before it is placed into innerHTML.
function escapeHTML(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0
});

function formatCurrency(amount) {
  return currencyFormatter.format(Math.max(0, Math.round(amount)));
}

// Rounds to the nearest $10 and never returns a negative number.
function roundMoney(amount) {
  const clean = Number.isFinite(amount) ? amount : 0;
  return Math.max(0, Math.round(clean / 10) * 10);
}

function toPositiveInt(value, fallback) {
  const n = parseInt(value, 10);
  if (!Number.isFinite(n) || n < 0) return fallback;
  return n;
}

function clampInt(value, min, max, fallback) {
  const n = parseInt(value, 10);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, n));
}

function generateQuoteId() {
  return "SLQ-" + Date.now().toString(36).toUpperCase() + "-" + Math.floor(Math.random() * 900 + 100);
}

function findInventoryItem(id) {
  return SHOWTIME_CONFIG.inventory.find((item) => item.id === id) || null;
}

function debounce(fn, delay) {
  let timer = null;
  return function debounced(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

/* ============================================================================
   STATE
   The wizard's entire set of answers lives in one object. It is persisted to
   localStorage after every change so progress survives a page reload.
   ==========================================================================*/

const STORAGE_KEY = "showtimeLedEstimatorState_v1";
const STEP_IDS = ["event", "coverage", "screens", "schedule", "production", "logistics", "estimate"];

function defaultState() {
  return {
    mode: null, // "recommend" | "choose"
    currentStep: 0, // 0 = mode select, 1-7 = wizard steps
    event: {
      eventType: "",
      eventDate: "",
      eventDays: "1",
      zip: "",
      attendance: "",
      venueSetting: "", // "indoor" | "outdoor"
      orgName: ""
    },
    coverage: {
      goal: "",
      viewingAreas: "1",
      viewingDistance: "",
      sameContent: "", // "same" | "different" | "unsure"
    },
    screens: {
      selections: {}, // { screenId: qty }
      modularSize: "",
      modularMount: "",
      activePreset: null,
      recommendation: null // computed recommendation object, cached
    },
    schedule: {
      dailyDuration: "",
      scheduleType: "",
      setupTiming: "",
      eventDays: "1",
      holdDays: "0",
      setupDays: "0",
      recurringDates: "0"
    },
    production: {
      contentTypes: [],
      multiScreenContent: "",
      support: [],
      audio: "",
      videoFeeds: "1"
    },
    logistics: {
      zip: "",
      distanceTier: "",
      venueAccess: [],
      power: [],
      connectivity: []
    },
    lead: {
      name: "",
      email: "",
      phone: "",
      company: "",
      eventDate: "",
      zip: "",
      notes: ""
    }
  };
}

let state = defaultState();

function saveState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (err) {
    // Storage can fail (private browsing, quota). The app still works
    // in-memory for the current session, so this is safe to ignore.
    console.warn("Showtime estimator: could not save progress.", err);
  }
}

// Merges saved data onto a fresh default state so missing/malformed keys
// never crash the app, even if an older version of the tool wrote the data.
function loadState() {
  const fresh = defaultState();
  let raw;
  try {
    raw = localStorage.getItem(STORAGE_KEY);
  } catch (err) {
    return fresh;
  }
  if (!raw) return fresh;
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return fresh;
    return deepMerge(fresh, parsed);
  } catch (err) {
    console.warn("Showtime estimator: saved progress was unreadable, starting fresh.", err);
    return fresh;
  }
}

function deepMerge(target, source) {
  if (Array.isArray(target)) return Array.isArray(source) ? source : target;
  if (typeof target !== "object" || target === null) return source === undefined ? target : source;
  const out = { ...target };
  Object.keys(target).forEach((key) => {
    if (source && Object.prototype.hasOwnProperty.call(source, key)) {
      out[key] = deepMerge(target[key], source[key]);
    }
  });
  return out;
}

function clearState(skipConfirm) {
  const doClear = () => {
    try { localStorage.removeItem(STORAGE_KEY); } catch (err) { /* ignore */ }
    state = defaultState();
    renderApp();
  };
  if (skipConfirm) {
    doClear();
    return;
  }
  openConfirmDialog(
    "Start over?",
    "This clears every answer you've entered and cannot be undone.",
    doClear
  );
}

/* ============================================================================
   SCREEN SELECTION HELPERS
   ==========================================================================*/

function getSelectedLines() {
  return Object.keys(state.screens.selections)
    .map((id) => ({ item: findInventoryItem(id), qty: toPositiveInt(state.screens.selections[id], 0) }))
    .filter((line) => line.item && line.qty > 0);
}

function totalSelectedUnits() {
  return getSelectedLines().reduce((sum, l) => sum + l.qty, 0);
}

function setScreenQty(screenId, qty) {
  const item = findInventoryItem(screenId);
  if (!item) return;
  const clamped = clampInt(qty, 0, item.totalInventory, 0);
  if (clamped <= 0) {
    delete state.screens.selections[screenId];
  } else {
    state.screens.selections[screenId] = clamped;
  }
  state.screens.activePreset = null;
  saveState();
}

function applyPreset(presetId) {
  const preset = SHOWTIME_CONFIG.presets.find((p) => p.id === presetId);
  if (!preset) return;
  state.screens.selections = {};
  preset.lines.forEach((line) => {
    const item = findInventoryItem(line.screenId);
    if (!item) return;
    state.screens.selections[line.screenId] = Math.min(line.qty, item.totalInventory);
  });
  state.screens.activePreset = presetId;
  saveState();
}

function applyRecommendation(rec) {
  if (!rec || !rec.lines) return;
  state.screens.selections = {};
  rec.lines.forEach((line) => {
    const item = findInventoryItem(line.screenId);
    if (!item) return;
    state.screens.selections[line.screenId] = Math.min(line.qty, item.totalInventory);
  });
  state.screens.activePreset = null;
  saveState();
}

/* ============================================================================
   RECOMMENDATION ENGINE
   Transparent, rule-based. Every recommendation returns a short plain-English
   explanation so the customer can see exactly why it was suggested.
   ==========================================================================*/

const ATTENDANCE_APPROX = {
  "under-100": 75,
  "100-300": 200,
  "300-750": 500,
  "750-1500": 1100,
  "1500-3000": 2200,
  "more-than-3000": 4000,
  "unsure": null
};

const ATTENDANCE_LABELS = {
  "under-100": "under 100",
  "100-300": "100–300",
  "300-750": "300–750",
  "750-1500": "750–1,500",
  "1500-3000": "1,500–3,000",
  "more-than-3000": "more than 3,000",
  "unsure": "an unconfirmed number of"
};

function addLine(lines, screenId, qty) {
  const existing = lines.find((l) => l.screenId === screenId);
  if (existing) existing.qty += qty;
  else lines.push({ screenId, qty });
}

function clampLinesToInventory(lines) {
  const clamped = [];
  const notes = [];
  lines.forEach((line) => {
    const item = findInventoryItem(line.screenId);
    if (!item) return;
    const qty = Math.min(line.qty, item.totalInventory);
    if (qty < line.qty) {
      notes.push(`Only ${item.totalInventory} ${item.name}${item.totalInventory === 1 ? "" : "s"} available, so the recommendation was limited to what's in the fleet.`);
    }
    if (qty > 0) clamped.push({ screenId: line.screenId, qty });
  });
  return { lines: clamped, notes };
}

function computeRecommendation(s) {
  const attendance = ATTENDANCE_APPROX[s.event.attendance] ?? null;
  const attendanceLabel = ATTENDANCE_LABELS[s.event.attendance] || "";
  const goal = s.coverage.goal;
  const viewingAreas = clampInt(s.coverage.viewingAreas, 1, 12, 1);
  const farDistance = ["100-200", "more-than-200"].includes(s.coverage.viewingDistance);
  let lines = [];
  let reason = "";
  let customFlag = false;

  const attendPhrase = s.event.attendance ? `an estimated attendance of ${attendanceLabel}` : "an unspecified attendance";

  switch (goal) {
    case "two-directions":
      addLine(lines, "trailer-10x6-double", 1);
      reason = "Recommended because you need visibility from two directions — the double-sided trailer covers both with one unit instead of two.";
      break;

    case "two-areas": {
      const big = attendance === null || attendance > 750;
      addLine(lines, big ? "trailer-16x9" : "trailer-12x7", 2);
      reason = `Recommended because you selected two separate viewing areas and ${attendPhrase}.`;
      break;
    }

    case "main-sponsor": {
      const big = attendance !== null && attendance > 750;
      const sponsorQty = big ? 2 : 1;
      addLine(lines, big ? "trailer-16x9" : "trailer-12x7", 1);
      addLine(lines, "display-2x7", sponsorQty);
      reason = `Recommended a main screen plus ${sponsorQty} sponsor display${sponsorQty > 1 ? "s" : ""} based on ${attendPhrase}.`;
      break;
    }

    case "stage-integrated":
      addLine(lines, "modular-led", 1);
      reason = "Recommended because your screen needs to be integrated into the stage design. Modular projects are custom-built, so this one is flagged for a custom quote.";
      customFlag = true;
      break;

    case "distributed": {
      const zones = Math.min(Math.max(viewingAreas, 2), 4);
      const big = attendance !== null && attendance > 1000;
      const mainQty = Math.min(zones, 2);
      addLine(lines, big ? "trailer-16x9" : "trailer-12x7", mainQty);
      if (zones > mainQty) addLine(lines, "display-2x7", Math.min(zones - mainQty, 2));
      reason = `Recommended coverage across ${viewingAreas} viewing zone${viewingAreas === 1 ? "" : "s"} distributed through the venue.`;
      break;
    }

    case "ads-only":
      addLine(lines, "display-2x7", Math.min(Math.max(viewingAreas, 1), 2));
      reason = "Recommended advertising displays for sponsor loops and directional information.";
      break;

    case "one-audience":
    case "unsure":
    default: {
      if (farDistance || (attendance !== null && attendance > 1000)) {
        addLine(lines, "trailer-16x9", 1);
        reason = farDistance
          ? "Recommended because your maximum viewing distance is over 100 feet, which calls for the larger format. Consider a second screen if your venue has multiple sightlines."
          : `Recommended because ${attendPhrase} calls for the larger format. Consider a second screen if your venue has multiple sightlines.`;
      } else if (attendance !== null && attendance >= 300) {
        addLine(lines, "trailer-16x9", 1);
        reason = `Recommended because ${attendPhrase} calls for a larger-format screen with one primary viewing area.`;
      } else {
        addLine(lines, "trailer-12x7", 1);
        reason = `Recommended because ${attendPhrase} with one primary viewing area fits our standard trailer well.`;
      }
      break;
    }
  }

  const { lines: clampedLines, notes } = clampLinesToInventory(lines);
  if (notes.length) reason += " " + notes.join(" ");

  return { lines: clampedLines, reason, customFlag };
}

/* ============================================================================
   PRICING ENGINE
   Every dollar figure below is pulled from SHOWTIME_CONFIG. This function
   never hard-codes a price.
   ==========================================================================*/

function countUnsureAnswers(s) {
  let count = 0;
  if (s.coverage.goal === "unsure") count++;
  if (s.coverage.viewingDistance === "unsure") count++;
  if (s.coverage.sameContent === "unsure") count++;
  if (s.production.contentTypes.includes("unsure")) count++;
  if (s.production.multiScreenContent === "unsure") count++;
  if (s.production.support.includes("unsure")) count++;
  if (s.production.audio === "unsure") count++;
  if (s.logistics.distanceTier === "unsure") count++;
  if (s.logistics.venueAccess.includes("unsure")) count++;
  if (s.logistics.power.includes("unsure")) count++;
  if (s.logistics.connectivity.includes("unsure")) count++;
  return count;
}

function evaluateCustomQuoteRules(s, selections) {
  const reasons = [];
  const cfg = SHOWTIME_CONFIG.customQuoteThresholds;
  const largeUnits = selections.filter((l) => l.item.large).reduce((sum, l) => sum + l.qty, 0);
  const hasModular = selections.some((l) => l.item.id === "modular-led");
  const eventDays = toPositiveInt(s.schedule.eventDays, 1);
  const recurringDates = toPositiveInt(s.schedule.recurringDates, 0);
  const videoFeeds = toPositiveInt(s.production.videoFeeds, 1);
  const restrictiveVenueCount = ["restricted-loading", "limited-window", "long-cable-run", "far-from-vehicles"]
    .filter((id) => s.logistics.venueAccess.includes(id)).length;

  if (hasModular && s.screens.modularSize === "custom") {
    reasons.push("Custom modular screen size");
  }
  if (hasModular && s.screens.modularMount === "truss-mounted") {
    reasons.push("Truss-mounted or flown screen");
  }
  if (hasModular) {
    reasons.push("Stage-integrated / modular screen configuration requires design review");
  }
  if (s.production.contentTypes.includes("live-camera-imag") && videoFeeds > cfg.maxIndependentVideoFeedsBeforeCustom) {
    reasons.push("Major live-camera production");
  }
  if (videoFeeds > cfg.maxIndependentVideoFeedsBeforeCustom) {
    reasons.push(`More than ${cfg.maxIndependentVideoFeedsBeforeCustom} independent video feeds`);
  }
  if (largeUnits > cfg.maxLargeScreensBeforeCustom) {
    reasons.push(`More than ${cfg.maxLargeScreensBeforeCustom} large screens`);
  }
  if (s.logistics.distanceTier === "more-than-300") {
    reasons.push("Delivery distance greater than 300 miles");
  }
  if (s.schedule.scheduleType === "extended-tour") {
    reasons.push("Touring or extended production");
  }
  if (s.schedule.setupTiming === "relocate" || s.logistics.venueAccess.includes("trailer-must-move")) {
    reasons.push("Equipment must be relocated during the event");
  }
  if (restrictiveVenueCount >= 2) {
    reasons.push("Highly restricted venue access");
  }
  if (eventDays > cfg.maxEventDaysBeforeCustom) {
    reasons.push(`More than ${cfg.maxEventDaysBeforeCustom} event days`);
  }
  if (s.schedule.scheduleType === "recurring" && recurringDates > cfg.maxRecurringDatesBeforeCustom) {
    reasons.push(`More than ${cfg.maxRecurringDatesBeforeCustom} recurring dates`);
  }
  if (countUnsureAnswers(s) >= cfg.maxUnsureAnswersBeforeCustom) {
    reasons.push("Several key answers are still unsure, so requirements can't be priced responsibly yet");
  }

  return reasons;
}

function collectPendingConfirmationItems(s, selections) {
  const items = [];
  if (s.coverage.goal === "unsure") items.push("Screen coverage goal");
  if (s.coverage.viewingDistance === "unsure") items.push("Maximum viewing distance");
  if (s.production.audio === "unsure") items.push("Audio requirements");
  if (s.logistics.distanceTier === "unsure") items.push("Travel distance");
  if (s.logistics.venueAccess.includes("unsure")) items.push("Venue access conditions");
  if (s.logistics.venueAccess.includes("security")) items.push("On-site security requirements");
  if (s.logistics.power.includes("unsure")) items.push("Power availability");
  if (s.logistics.connectivity.includes("unsure")) items.push("Connectivity / signal source");
  if (selections.some((l) => l.item.id === "modular-led")) items.push("Modular screen configuration and rigging plan");
  const hasCopyrighted = s.production.contentTypes.some((t) => ["movie-prerecorded", "live-tv-sports"].includes(t));
  if (hasCopyrighted) items.push("Content licensing / broadcast rights");
  return items;
}

// Main entry point: returns the full pricing breakdown for the current state.
function calculateEstimate(s) {
  const cfg = SHOWTIME_CONFIG;
  const selections = getSelectedLines();
  const totalUnits = selections.reduce((sum, l) => sum + l.qty, 0);
  const largeUnits = selections.filter((l) => l.item.large).reduce((sum, l) => sum + l.qty, 0);

  if (totalUnits === 0) {
    return { noScreens: true };
  }

  const eventDays = clampInt(s.schedule.eventDays || s.event.eventDays, 1, 60, 1);
  const holdDays = clampInt(s.schedule.holdDays, 0, 60, 0);
  const setupDays = clampInt(s.schedule.setupDays, 0, 10, 0);
  const durationTier = cfg.durationTiers[s.schedule.dailyDuration] || cfg.durationTiers["up-to-4"];

  const breakdown = [];
  let totalLow = 0;
  let totalHigh = 0;

  // 1) Equipment rental — base daily rate x quantity x event days.
  let equipLow = 0, equipHigh = 0;
  selections.forEach((line) => {
    equipLow += line.item.dailyRate.low * line.qty * eventDays;
    equipHigh += line.item.dailyRate.high * line.qty * eventDays;
  });
  breakdown.push({ key: "equipment", label: "Equipment rental", low: equipLow, high: equipHigh });
  totalLow += equipLow; totalHigh += equipHigh;

  // 2) Duration adjustment — extra cost for longer operating hours.
  const durationLow = durationTier.addPerUnitPerDay.low * totalUnits * eventDays;
  const durationHigh = durationTier.addPerUnitPerDay.high * totalUnits * eventDays;
  breakdown.push({ key: "duration", label: "Duration adjustment", low: durationLow, high: durationHigh });
  totalLow += durationLow; totalHigh += durationHigh;

  // 3) Multi-day adjustment — discount on days after the first.
  let multiDayLow = 0, multiDayHigh = 0;
  if (eventDays >= cfg.multiDayDiscount.minimumDays) {
    const perDayLow = (equipLow + durationLow) / eventDays;
    const perDayHigh = (equipHigh + durationHigh) / eventDays;
    const extraDays = eventDays - 1;
    multiDayLow = -(perDayLow * extraDays * (cfg.multiDayDiscount.percentOffAdditionalDaysHigh / 100));
    multiDayHigh = -(perDayHigh * extraDays * (cfg.multiDayDiscount.percentOffAdditionalDaysLow / 100));
  }
  breakdown.push({ key: "multiDay", label: "Multi-day adjustment", low: multiDayLow, high: multiDayHigh });
  totalLow += multiDayLow; totalHigh += multiDayHigh;

  // 4) Multi-screen package adjustment — discount on shared overhead only.
  let multiScreenLow = 0, multiScreenHigh = 0;
  const sharedBaseLow = cfg.setup.baseFirstUnit.low + cfg.setup.perAdditionalUnit.low * Math.max(0, totalUnits - 1);
  const sharedBaseHigh = cfg.setup.baseFirstUnit.high + cfg.setup.perAdditionalUnit.high * Math.max(0, totalUnits - 1);
  if (totalUnits >= cfg.multiScreenDiscount.minimumUnits) {
    multiScreenLow = -(sharedBaseLow * (cfg.multiScreenDiscount.percentOffSharedHigh / 100));
    multiScreenHigh = -(sharedBaseHigh * (cfg.multiScreenDiscount.percentOffSharedLow / 100));
  }
  breakdown.push({ key: "multiScreen", label: "Multi-screen package adjustment", low: multiScreenLow, high: multiScreenHigh });
  totalLow += multiScreenLow; totalHigh += multiScreenHigh;

  // 5) Travel — manual distance tier x number of delivery vehicles needed.
  const tier = cfg.travel.tiers[s.logistics.distanceTier] || null;
  let travelLow = 0, travelHigh = 0;
  let travelIsCustom = false;
  if (!tier) {
    // No distance selected yet — treat as unpriced rather than guessing.
    travelIsCustom = false;
  } else if (tier.customQuote) {
    travelIsCustom = true;
  } else {
    const vehicles = Math.max(1, Math.ceil(selections.reduce((sum, l) => sum + l.item.transportWeight * l.qty, 0)));
    travelLow = tier.flatFee.low + tier.ratePerVehicle.low * vehicles;
    travelHigh = tier.flatFee.high + tier.ratePerVehicle.high * vehicles;
  }
  breakdown.push({ key: "travel", label: "Travel", low: travelLow, high: travelHigh, isCustom: travelIsCustom });
  if (!travelIsCustom) { totalLow += travelLow; totalHigh += travelHigh; }

  // 6) Setup and crew — shared setup base, venue-access effort, crew add-ons, hold days.
  let setupLow = sharedBaseLow, setupHigh = sharedBaseHigh;
  if (s.schedule.setupTiming === "day-before") {
    setupLow += cfg.setup.dayBeforeSetupAdd.low;
    setupHigh += cfg.setup.dayBeforeSetupAdd.high;
  }
  if (setupDays > 0) {
    setupLow += cfg.setup.multipleSetupDaysPerExtraDay.low * setupDays;
    setupHigh += cfg.setup.multipleSetupDaysPerExtraDay.high * setupDays;
  }
  s.logistics.venueAccess.forEach((id) => {
    const opt = cfg.venueAccessOptions[id];
    if (opt) { setupLow += opt.low; setupHigh += opt.high; }
  });
  if (s.production.support.includes("additional-operator")) {
    setupLow += cfg.crew.additionalOperatorPerDay.low * eventDays;
    setupHigh += cfg.crew.additionalOperatorPerDay.high * eventDays;
  }
  if (s.production.support.includes("live-camera-imag")) {
    setupLow += cfg.crew.imagIntegrationPerDay.low * eventDays;
    setupHigh += cfg.crew.imagIntegrationPerDay.high * eventDays;
  }
  const impliesOvernight = s.logistics.venueAccess.includes("overnight");
  const effectiveHoldDays = Math.max(holdDays, impliesOvernight ? 1 : 0);
  if (effectiveHoldDays > 0) {
    const smallUnits = totalUnits - largeUnits;
    setupLow += (cfg.holdDay.perLargeUnitPerDay.low * largeUnits + cfg.holdDay.perSmallUnitPerDay.low * smallUnits) * effectiveHoldDays;
    setupHigh += (cfg.holdDay.perLargeUnitPerDay.high * largeUnits + cfg.holdDay.perSmallUnitPerDay.high * smallUnits) * effectiveHoldDays;
  }
  breakdown.push({ key: "setupCrew", label: "Setup and crew", low: setupLow, high: setupHigh });
  totalLow += setupLow; totalHigh += setupHigh;

  // 7) Production support add-ons.
  let productionLow = 0, productionHigh = 0;
  s.production.support.forEach((id) => {
    if (id === "additional-operator" || id === "live-camera-imag" || id === "unsure") return;
    const opt = cfg.productionAddons[id];
    if (opt) { productionLow += opt.low; productionHigh += opt.high; }
  });
  if (s.production.multiScreenContent === "different" || s.production.multiScreenContent === "combination") {
    const opt = cfg.productionAddons["multiple-video-sources"];
    if (opt && !s.production.support.includes("multiple-video-sources")) {
      productionLow += opt.low; productionHigh += opt.high;
    }
  }
  breakdown.push({ key: "production", label: "Production support", low: productionLow, high: productionHigh });
  totalLow += productionLow; totalHigh += productionHigh;

  // 8) Power or connectivity.
  let powerConnLow = 0, powerConnHigh = 0;
  s.logistics.power.forEach((id) => {
    const opt = cfg.powerOptions[id];
    if (opt) { powerConnLow += opt.low; powerConnHigh += opt.high; }
  });
  s.logistics.connectivity.forEach((id) => {
    const opt = cfg.connectivityOptions[id];
    if (opt) { powerConnLow += opt.low; powerConnHigh += opt.high; }
  });
  const audioOpt = cfg.audioOptions[s.production.audio];
  if (audioOpt) { powerConnLow += audioOpt.low; powerConnHigh += audioOpt.high; }
  breakdown.push({ key: "powerConn", label: "Power or connectivity", low: powerConnLow, high: powerConnHigh });
  totalLow += powerConnLow; totalHigh += powerConnHigh;

  // 9) Pending confirmation items — informational only, no dollar impact.
  const pendingItems = collectPendingConfirmationItems(s, selections);
  breakdown.push({ key: "pending", label: "Pending confirmation items", low: 0, high: 0, isInfo: true, items: pendingItems });

  // Custom-quote rules
  const customReasons = evaluateCustomQuoteRules(s, selections);
  const customQuoteRequired = customReasons.length > 0;

  totalLow = roundMoney(totalLow);
  totalHigh = roundMoney(Math.max(totalHigh, totalLow));

  return {
    noScreens: false,
    selections,
    totalUnits,
    eventDays,
    breakdown,
    totalLow,
    totalHigh,
    customQuoteRequired,
    customReasons,
    pendingItems,
    travelIsCustom
  };
}

/* ============================================================================
   STATIC OPTION LISTS
   Kept separate from SHOWTIME_CONFIG because these are form choices, not
   prices — SHOWTIME_CONFIG is reserved for anything with a dollar value or
   an inventory count.
   ==========================================================================*/

const EVENT_TYPES = [
  "Live Event", "Watch Party", "Movie Night", "Festival", "Sporting Event",
  "Concert", "Corporate Event", "Ceremony", "Sponsor Advertising",
  "Touring or Extended Production", "Other"
];

const ATTENDANCE_OPTIONS = [
  { id: "under-100", label: "Under 100" },
  { id: "100-300", label: "100–300" },
  { id: "300-750", label: "300–750" },
  { id: "750-1500", label: "750–1,500" },
  { id: "1500-3000", label: "1,500–3,000" },
  { id: "more-than-3000", label: "More than 3,000" },
  { id: "unsure", label: "Unsure" }
];

const COVERAGE_GOALS = [
  { id: "one-audience", label: "One primary audience" },
  { id: "two-areas", label: "Two separate viewing areas" },
  { id: "two-directions", label: "Visible from two directions" },
  { id: "distributed", label: "Screens distributed throughout a venue" },
  { id: "main-sponsor", label: "Main screen plus sponsor displays" },
  { id: "stage-integrated", label: "Stage-integrated custom screen" },
  { id: "ads-only", label: "Advertising or directional displays only" },
  { id: "unsure", label: "Unsure" }
];

const VIEWING_DISTANCES = [
  { id: "under-50", label: "Under 50 feet" },
  { id: "50-100", label: "50–100 feet" },
  { id: "100-200", label: "100–200 feet" },
  { id: "more-than-200", label: "More than 200 feet" },
  { id: "unsure", label: "Unsure" }
];

const DAILY_DURATIONS = [
  { id: "up-to-4", label: "Up to 4 hours" },
  { id: "4-8", label: "4–8 hours" },
  { id: "8-12", label: "8–12 hours" },
  { id: "more-than-12", label: "More than 12 hours" }
];

const SCHEDULE_TYPES = [
  { id: "one-time", label: "One-time event" },
  { id: "consecutive-multi-day", label: "Consecutive multi-day event" },
  { id: "recurring", label: "Recurring event series" },
  { id: "nonconsecutive", label: "Multiple nonconsecutive dates" },
  { id: "extended-tour", label: "Extended production or tour" }
];

const SETUP_TIMINGS = [
  { id: "same-day", label: "Same-day setup" },
  { id: "day-before", label: "Setup the day before" },
  { id: "overnight", label: "Equipment remains overnight" },
  { id: "multiple-setup-days", label: "Multiple setup days" },
  { id: "relocate", label: "Equipment must be relocated during the event" },
  { id: "unsure", label: "Unsure" }
];

const CONTENT_TYPES = [
  { id: "movie-prerecorded", label: "Movie or prerecorded video" },
  { id: "live-tv-sports", label: "Live television or sporting event" },
  { id: "live-camera-imag", label: "Live camera production or IMAG" },
  { id: "presentations", label: "Presentations or corporate content" },
  { id: "sponsor-ads", label: "Sponsor advertisements" },
  { id: "multiple-sources", label: "Multiple content sources" },
  { id: "client-feed", label: "Client-provided finished video feed" },
  { id: "unsure", label: "Unsure" }
];

const MULTI_SCREEN_CONTENT_OPTIONS = [
  { id: "same", label: "Same content on every screen" },
  { id: "different", label: "Different content on different screens" },
  { id: "one-feed", label: "One live feed distributed to all screens" },
  { id: "combination", label: "Combination of live content and sponsor content" },
  { id: "unsure", label: "Unsure" }
];

const PRODUCTION_SUPPORT_OPTIONS = [
  { id: "standard-operator", label: "Standard screen operator" },
  { id: "additional-operator", label: "Additional technical operator" },
  { id: "live-camera-imag", label: "Live camera or IMAG integration" },
  { id: "multiple-video-sources", label: "Multiple video sources" },
  { id: "on-screen-graphics", label: "On-screen graphics" },
  { id: "sponsor-loop-playback", label: "Sponsor-loop playback" },
  { id: "remote-content-mgmt", label: "Remote content management" },
  { id: "client-provides-feed", label: "Client provides the finished feed" },
  { id: "additional-planning", label: "Additional production planning" },
  { id: "unsure", label: "Unsure" }
];

const AUDIO_CHOICES = [
  { id: "standard", label: "Built-in standard audio" },
  { id: "large-system", label: "Larger event audio system needed" },
  { id: "venue-provides", label: "Venue provides audio" },
  { id: "none", label: "No audio required" },
  { id: "unsure", label: "Unsure" }
];

const DISTANCE_TIERS = [
  { id: "within-30", label: "Within 30 miles of Kansas City" },
  { id: "31-75", label: "31–75 miles" },
  { id: "76-150", label: "76–150 miles" },
  { id: "151-300", label: "151–300 miles" },
  { id: "more-than-300", label: "More than 300 miles" },
  { id: "unsure", label: "Unsure" }
];

const VENUE_ACCESS_CHOICES = [
  { id: "paved", label: "Paved vehicle access" },
  { id: "grass-uneven", label: "Grass or uneven terrain" },
  { id: "restricted-loading", label: "Restricted loading area" },
  { id: "indoor-dock", label: "Indoor loading dock" },
  { id: "limited-window", label: "Limited setup window" },
  { id: "long-cable-run", label: "Long cable run" },
  { id: "far-from-vehicles", label: "Screen must be placed far from support vehicles" },
  { id: "trailer-must-move", label: "Trailer must move during the event" },
  { id: "overnight", label: "Equipment remains overnight" },
  { id: "security", label: "Security may be required" },
  { id: "unsure", label: "Unsure" }
];

const POWER_CHOICES = [
  { id: "venue-power", label: "Venue power available" },
  { id: "battery", label: "Battery operation requested" },
  { id: "generator", label: "Generator required" },
  { id: "far-power", label: "Power source more than 100 feet away" },
  { id: "separate-drops", label: "Separate power drops available" },
  { id: "unsure", label: "Unsure" }
];

const CONNECTIVITY_CHOICES = [
  { id: "venue-hdmi", label: "Venue provides HDMI feed" },
  { id: "venue-sdi", label: "Venue provides SDI feed" },
  { id: "venue-internet", label: "Venue internet available" },
  { id: "showtime-connectivity", label: "Showtime connectivity requested" },
  { id: "antenna-tv", label: "Digital antenna or local television" },
  { id: "starlink-cellular", label: "Starlink or cellular backup" },
  { id: "unsure", label: "Unsure" }
];

const STEP_LABELS = ["Event", "Coverage", "Screens", "Schedule", "Production", "Logistics", "Estimate"];

/* ============================================================================
   RENDERING
   Each render* function returns an HTML string for one step. All dynamic
   text drawn from user input goes through escapeHTML first.
   ==========================================================================*/

const appRoot = () => document.getElementById("app");

function renderApp() {
  const root = appRoot();
  if (!root) return;
  if (state.currentStep === 0) {
    root.innerHTML = renderModeSelect();
  } else {
    root.innerHTML = renderWizard();
  }
  attachGlobalListeners();
  postIframeHeight();
}

function renderModeSelect() {
  return `
    <div class="mode-select" role="region" aria-label="Get started">
      <p class="eyebrow">Showtime LED</p>
      <h1 class="hero-heading">Build Your Screen Package</h1>
      <p class="hero-sub">Answer a few questions about your event and get an estimated price range in minutes. This is a planning estimate, not a confirmed reservation or final price.</p>
      <div class="mode-cards">
        <button type="button" class="mode-card" data-action="start-mode" data-mode="recommend">
          <span class="mode-card-title">Recommend a Setup</span>
          <span class="mode-card-desc">Answer a few questions and we'll suggest a screen package to start from.</span>
        </button>
        <button type="button" class="mode-card" data-action="start-mode" data-mode="choose">
          <span class="mode-card-title">Choose My Screens</span>
          <span class="mode-card-desc">Go straight to selecting screens yourself. We'll still ask what's needed for accurate pricing.</span>
        </button>
      </div>
      <p class="restore-note" data-restore-note hidden>
        You have a saved quote in progress.
        <button type="button" class="link-button" data-action="resume-progress">Resume it</button>
        or
        <button type="button" class="link-button" data-action="clear-progress">start over</button>.
      </p>
    </div>
  `;
}

function renderWizard() {
  return `
    <div class="wizard">
      ${renderProgressBar()}
      <div class="wizard-layout">
        <main class="wizard-main" id="wizardMain" aria-live="polite">
          ${renderStepHeader()}
          <form id="stepForm" novalidate>
            ${renderCurrentStep()}
          </form>
          ${renderStepNav()}
        </main>
        <aside class="wizard-summary" id="wizardSummary" aria-label="Quote summary">
          ${renderSummaryPanel()}
        </aside>
      </div>
      ${renderMobileBar()}
    </div>
    ${renderLeadModal()}
    ${renderConfirmDialog()}
    <div class="toast" id="toast" role="status" aria-live="polite" hidden></div>
  `;
}

function renderProgressBar() {
  const items = STEP_LABELS.map((label, idx) => {
    const stepNum = idx + 1;
    const isActive = stepNum === state.currentStep;
    const isDone = stepNum < state.currentStep;
    return `
      <li class="progress-step ${isActive ? "is-active" : ""} ${isDone ? "is-done" : ""}">
        <button type="button" class="progress-step-btn" data-action="jump-step" data-step="${stepNum}" ${isDone || isActive ? "" : "disabled"} aria-current="${isActive ? "step" : "false"}">
          <span class="progress-step-num">${isDone ? "✓" : stepNum}</span>
          <span class="progress-step-label">${label}</span>
        </button>
      </li>`;
  }).join("");
  return `<nav class="progress-bar" aria-label="Estimator steps"><ol>${items}</ol></nav>`;
}

function renderStepHeader() {
  const stepName = STEP_LABELS[state.currentStep - 1];
  return `
    <div class="step-header">
      <div>
        <p class="step-eyebrow">Step ${state.currentStep} of 7</p>
        <h2 class="step-title">${stepName}</h2>
      </div>
      <button type="button" class="link-button step-header-restart" data-action="start-over">Start Over</button>
    </div>
  `;
}

function renderCurrentStep() {
  switch (state.currentStep) {
    case 1: return renderStepEvent();
    case 2: return renderStepCoverage();
    case 3: return renderStepScreens();
    case 4: return renderStepSchedule();
    case 5: return renderStepProduction();
    case 6: return renderStepLogistics();
    case 7: return renderStepEstimate();
    default: return "";
  }
}

function renderStepNav() {
  const isFirst = state.currentStep === 1;
  const isLast = state.currentStep === 7;
  return `
    <div class="step-nav">
      <button type="button" class="btn btn-secondary" data-action="prev-step" ${isFirst ? "disabled" : ""}>Back</button>
      ${isLast ? "" : `<button type="button" class="btn btn-primary" data-action="next-step">Continue</button>`}
    </div>
  `;
}

/* ---- Step 1: Event ---- */
function renderStepEvent() {
  const e = state.event;
  return `
    <div class="field-group">
      <label class="field-label" for="eventType">Event type</label>
      <select class="field-input" id="eventType" data-bind="event.eventType" required>
        <option value="">Select an event type</option>
        ${EVENT_TYPES.map((t) => `<option value="${escapeHTML(t)}" ${e.eventType === t ? "selected" : ""}>${escapeHTML(t)}</option>`).join("")}
      </select>
      <p class="field-error" data-error-for="event.eventType" hidden></p>
    </div>

    <div class="field-row">
      <div class="field-group">
        <label class="field-label" for="eventDate">Event date</label>
        <input class="field-input" type="date" id="eventDate" data-bind="event.eventDate" value="${escapeHTML(e.eventDate)}" required />
        <p class="field-error" data-error-for="event.eventDate" hidden></p>
      </div>
      <div class="field-group">
        <label class="field-label" for="eventDays">Number of event days</label>
        <input class="field-input" type="number" min="1" max="60" id="eventDays" data-bind="event.eventDays" value="${escapeHTML(e.eventDays)}" required />
        <p class="field-error" data-error-for="event.eventDays" hidden></p>
      </div>
    </div>

    <div class="field-row">
      <div class="field-group">
        <label class="field-label" for="eventZip">Event ZIP code</label>
        <input class="field-input" type="text" inputmode="numeric" pattern="[0-9]{5}" maxlength="5" id="eventZip" data-bind="event.zip" value="${escapeHTML(e.zip)}" placeholder="e.g. 64105" required />
        <p class="field-error" data-error-for="event.zip" hidden></p>
      </div>
      <div class="field-group">
        <label class="field-label" for="attendance">Estimated attendance</label>
        <select class="field-input" id="attendance" data-bind="event.attendance" required>
          <option value="">Select a range</option>
          ${ATTENDANCE_OPTIONS.map((o) => `<option value="${o.id}" ${e.attendance === o.id ? "selected" : ""}>${o.label}</option>`).join("")}
        </select>
        <p class="field-error" data-error-for="event.attendance" hidden></p>
      </div>
    </div>

    <div class="field-group">
      <span class="field-label">Indoor or outdoor</span>
      <div class="radio-row" role="radiogroup" aria-label="Indoor or outdoor">
        ${["indoor", "outdoor"].map((v) => `
          <label class="radio-pill">
            <input type="radio" name="venueSetting" value="${v}" data-bind="event.venueSetting" ${e.venueSetting === v ? "checked" : ""} required />
            <span>${v[0].toUpperCase() + v.slice(1)}</span>
          </label>`).join("")}
      </div>
      <p class="field-error" data-error-for="event.venueSetting" hidden></p>
    </div>

    <div class="field-group">
      <label class="field-label" for="orgName">Company or organization <span class="optional-tag">Optional</span></label>
      <input class="field-input" type="text" id="orgName" data-bind="event.orgName" value="${escapeHTML(e.orgName)}" maxlength="120" />
    </div>
  `;
}

/* ---- Step 2: Coverage ---- */
function renderStepCoverage() {
  const c = state.coverage;
  return `
    <div class="field-group">
      <span class="field-label">What do you need the screens to accomplish?</span>
      <div class="option-grid" role="radiogroup" aria-label="Coverage goal">
        ${COVERAGE_GOALS.map((o) => `
          <label class="option-card">
            <input type="radio" name="coverageGoal" value="${o.id}" data-bind="coverage.goal" ${c.goal === o.id ? "checked" : ""} required />
            <span>${o.label}</span>
          </label>`).join("")}
      </div>
      <p class="field-error" data-error-for="coverage.goal" hidden></p>
    </div>

    <div class="field-row">
      <div class="field-group">
        <label class="field-label" for="viewingAreas">Number of viewing areas</label>
        <input class="field-input" type="number" min="1" max="12" id="viewingAreas" data-bind="coverage.viewingAreas" value="${escapeHTML(c.viewingAreas)}" />
      </div>
      <div class="field-group">
        <label class="field-label" for="viewingDistance">Approximate maximum viewing distance</label>
        <select class="field-input" id="viewingDistance" data-bind="coverage.viewingDistance" required>
          <option value="">Select a distance</option>
          ${VIEWING_DISTANCES.map((o) => `<option value="${o.id}" ${c.viewingDistance === o.id ? "selected" : ""}>${o.label}</option>`).join("")}
        </select>
        <p class="field-error" data-error-for="coverage.viewingDistance" hidden></p>
      </div>
    </div>

    <div class="field-group">
      <span class="field-label">Will every screen show the same content?</span>
      <div class="radio-row" role="radiogroup" aria-label="Same content on every screen">
        ${[["same", "Yes, same content"], ["different", "No, different content per screen"], ["unsure", "Unsure"]].map(([v, l]) => `
          <label class="radio-pill">
            <input type="radio" name="sameContent" value="${v}" data-bind="coverage.sameContent" ${c.sameContent === v ? "checked" : ""} />
            <span>${l}</span>
          </label>`).join("")}
      </div>
    </div>
  `;
}

/* ---- Step 3: Screens ---- */
function renderStepScreens() {
  const rec = state.mode === "recommend" ? getOrComputeRecommendation() : null;
  const recommendedIds = rec ? rec.lines.map((l) => l.screenId) : [];

  return `
    ${state.mode === "recommend" ? renderRecommendationBanner(rec) : ""}

    <div class="field-group">
      <span class="field-label">Preset packages</span>
      <div class="preset-row">
        ${SHOWTIME_CONFIG.presets.map((p) => `
          <button type="button" class="preset-chip ${state.screens.activePreset === p.id ? "is-active" : ""}" data-action="apply-preset" data-preset="${p.id}" title="${escapeHTML(p.description)}">
            ${escapeHTML(p.name)}
          </button>`).join("")}
      </div>
    </div>

    <div class="screen-cards">
      ${SHOWTIME_CONFIG.inventory.map((item) => renderScreenCard(item, recommendedIds.includes(item.id))).join("")}
    </div>

    ${totalSelectedUnits() === 0 ? `<p class="field-error" data-error-for="screens.selections">Select at least one screen to continue.</p>` : ""}
  `;
}

function renderRecommendationBanner(rec) {
  if (!rec || rec.lines.length === 0) {
    return `<div class="callout callout-info"><p>Complete Step 1 and Step 2 to see a recommended package here. You can still select screens manually below.</p></div>`;
  }
  const lineText = rec.lines.map((l) => {
    const item = findInventoryItem(l.screenId);
    return item ? `${l.qty} × ${item.name}` : "";
  }).filter(Boolean).join(", ");
  return `
    <div class="callout callout-recommend">
      <p class="callout-title">Recommended package: ${escapeHTML(lineText)}</p>
      <p class="callout-body">${escapeHTML(rec.reason)}</p>
      <div class="callout-actions">
        <button type="button" class="btn btn-primary btn-small" data-action="apply-recommendation">Use this recommendation</button>
        <span class="callout-note">You can change screens and quantities any time below.</span>
      </div>
    </div>
  `;
}

function renderScreenCard(item, isRecommended) {
  const qty = toPositiveInt(state.screens.selections[item.id], 0);
  const atLimit = qty >= item.totalInventory;
  const cardId = `screen-${item.id}`;
  return `
    <article class="screen-card" data-screen-id="${item.id}">
      <header class="screen-card-header">
        <div>
          <h3 class="screen-card-name">${escapeHTML(item.name)}</h3>
          <p class="screen-card-dims">${escapeHTML(item.dims)}</p>
        </div>
        ${isRecommended ? `<span class="badge badge-recommended">Recommended</span>` : ""}
      </header>
      <p class="screen-card-desc">${escapeHTML(item.shortDescription)}</p>
      <p class="screen-card-inventory">${item.totalInventory} ${item.unitLabel}${item.totalInventory === 1 ? "" : "s"} available</p>

      <details class="why-screen">
        <summary>Why this screen?</summary>
        <ul class="best-for-list">
          ${item.bestFor.map((use) => `<li>${escapeHTML(use)}</li>`).join("")}
        </ul>
      </details>

      ${item.configurable ? renderModularConfig(item) : ""}

      <div class="screen-card-footer">
        <div class="qty-stepper" role="group" aria-label="Quantity for ${escapeHTML(item.name)}">
          <button type="button" class="qty-btn" data-action="qty-decrement" data-screen="${item.id}" aria-label="Decrease quantity" ${qty <= 0 ? "disabled" : ""}>−</button>
          <span class="qty-value" id="${cardId}-qty" aria-live="polite">${qty}</span>
          <button type="button" class="qty-btn" data-action="qty-increment" data-screen="${item.id}" aria-label="Increase quantity" ${atLimit ? "disabled" : ""}>+</button>
        </div>
      </div>
      ${atLimit ? `<p class="inventory-warning">You've reached the available inventory for this screen (${item.totalInventory}).</p>` : ""}
    </article>
  `;
}

function renderModularConfig(item) {
  const s = state.screens;
  return `
    <div class="modular-config">
      <div class="field-group">
        <label class="field-label" for="modularSize">Configuration size</label>
        <select class="field-input" id="modularSize" data-bind="screens.modularSize">
          <option value="">Select a size</option>
          ${item.configOptions.sizes.map((o) => `<option value="${o.id}" ${s.modularSize === o.id ? "selected" : ""}>${o.label}</option>`).join("")}
        </select>
      </div>
      <div class="field-group">
        <label class="field-label" for="modularMount">Mounting</label>
        <select class="field-input" id="modularMount" data-bind="screens.modularMount">
          <option value="">Select a mount type</option>
          ${item.configOptions.mounts.map((o) => `<option value="${o.id}" ${s.modularMount === o.id ? "selected" : ""}>${o.label}</option>`).join("")}
        </select>
      </div>
    </div>
  `;
}

function getOrComputeRecommendation() {
  const rec = computeRecommendation(state);
  state.screens.recommendation = rec;
  return rec;
}

/* ---- Step 4: Schedule ---- */
function renderStepSchedule() {
  const sc = state.schedule;
  return `
    <div class="field-group">
      <span class="field-label">Daily operating duration</span>
      <div class="option-grid" role="radiogroup" aria-label="Daily operating duration">
        ${DAILY_DURATIONS.map((o) => `
          <label class="option-card">
            <input type="radio" name="dailyDuration" value="${o.id}" data-bind="schedule.dailyDuration" ${sc.dailyDuration === o.id ? "checked" : ""} required />
            <span>${o.label}</span>
          </label>`).join("")}
      </div>
      <p class="field-error" data-error-for="schedule.dailyDuration" hidden></p>
    </div>

    <div class="field-group">
      <span class="field-label">Event schedule type</span>
      <div class="option-grid" role="radiogroup" aria-label="Event schedule type">
        ${SCHEDULE_TYPES.map((o) => `
          <label class="option-card">
            <input type="radio" name="scheduleType" value="${o.id}" data-bind="schedule.scheduleType" ${sc.scheduleType === o.id ? "checked" : ""} required />
            <span>${o.label}</span>
          </label>`).join("")}
      </div>
      <p class="field-error" data-error-for="schedule.scheduleType" hidden></p>
    </div>

    <div class="field-group">
      <span class="field-label">Setup timing</span>
      <div class="option-grid" role="radiogroup" aria-label="Setup timing">
        ${SETUP_TIMINGS.map((o) => `
          <label class="option-card">
            <input type="radio" name="setupTiming" value="${o.id}" data-bind="schedule.setupTiming" ${sc.setupTiming === o.id ? "checked" : ""} required />
            <span>${o.label}</span>
          </label>`).join("")}
      </div>
      <p class="field-error" data-error-for="schedule.setupTiming" hidden></p>
    </div>

    <div class="field-row">
      <div class="field-group">
        <label class="field-label" for="scheduleEventDays">Number of event days</label>
        <input class="field-input" type="number" min="1" max="60" id="scheduleEventDays" data-bind="schedule.eventDays" value="${escapeHTML(sc.eventDays)}" />
      </div>
      <div class="field-group">
        <label class="field-label" for="holdDays">Number of equipment hold days</label>
        <input class="field-input" type="number" min="0" max="60" id="holdDays" data-bind="schedule.holdDays" value="${escapeHTML(sc.holdDays)}" />
      </div>
    </div>
    <div class="field-row">
      <div class="field-group">
        <label class="field-label" for="setupDays">Number of setup or teardown days</label>
        <input class="field-input" type="number" min="0" max="10" id="setupDays" data-bind="schedule.setupDays" value="${escapeHTML(sc.setupDays)}" />
      </div>
      ${sc.scheduleType === "recurring" || sc.scheduleType === "nonconsecutive" ? `
      <div class="field-group">
        <label class="field-label" for="recurringDates">Number of recurring dates</label>
        <input class="field-input" type="number" min="0" max="60" id="recurringDates" data-bind="schedule.recurringDates" value="${escapeHTML(sc.recurringDates)}" />
      </div>` : ""}
    </div>
    <p class="field-hint">Day-before setup, overnight holds, and multi-day teardown are priced separately from the hours screens are actually running.</p>
  `;
}

/* ---- Step 5: Production ---- */
function renderStepProduction() {
  const p = state.production;
  const showLicenseNote = p.contentTypes.some((t) => ["movie-prerecorded", "live-tv-sports"].includes(t));
  const showMultiScreenQuestion = totalSelectedUnits() > 1 || p.contentTypes.includes("multiple-sources");

  return `
    <div class="field-group">
      <span class="field-label">What will appear on the screens?</span>
      <div class="option-grid" role="group" aria-label="Content types">
        ${CONTENT_TYPES.map((o) => `
          <label class="option-card">
            <input type="checkbox" name="contentTypes" value="${o.id}" data-bind-array="production.contentTypes" ${p.contentTypes.includes(o.id) ? "checked" : ""} />
            <span>${o.label}</span>
          </label>`).join("")}
      </div>
    </div>

    ${showLicenseNote ? `<div class="callout callout-note"><p>Content licenses, movie licenses, subscriptions, and commercial broadcast rights are not included unless specifically stated.</p></div>` : ""}

    ${showMultiScreenQuestion ? `
    <div class="field-group">
      <span class="field-label">For multiple screens, what's the content plan?</span>
      <div class="option-grid" role="radiogroup" aria-label="Multi-screen content plan">
        ${MULTI_SCREEN_CONTENT_OPTIONS.map((o) => `
          <label class="option-card">
            <input type="radio" name="multiScreenContent" value="${o.id}" data-bind="production.multiScreenContent" ${p.multiScreenContent === o.id ? "checked" : ""} />
            <span>${o.label}</span>
          </label>`).join("")}
      </div>
    </div>
    <div class="field-group">
      <label class="field-label" for="videoFeeds">Number of independent video feeds</label>
      <input class="field-input" type="number" min="1" max="20" id="videoFeeds" data-bind="production.videoFeeds" value="${escapeHTML(p.videoFeeds)}" />
      <p class="field-hint">Count separate live or camera sources feeding the screens.</p>
    </div>` : ""}

    <div class="field-group">
      <span class="field-label">Production support</span>
      <div class="option-grid" role="group" aria-label="Production support">
        ${PRODUCTION_SUPPORT_OPTIONS.map((o) => `
          <label class="option-card">
            <input type="checkbox" name="support" value="${o.id}" data-bind-array="production.support" ${p.support.includes(o.id) ? "checked" : ""} />
            <span>${o.label}</span>
          </label>`).join("")}
      </div>
    </div>

    <div class="field-group">
      <span class="field-label">Audio</span>
      <div class="option-grid" role="radiogroup" aria-label="Audio">
        ${AUDIO_CHOICES.map((o) => `
          <label class="option-card">
            <input type="radio" name="audio" value="${o.id}" data-bind="production.audio" ${p.audio === o.id ? "checked" : ""} required />
            <span>${o.label}</span>
          </label>`).join("")}
      </div>
      <p class="field-error" data-error-for="production.audio" hidden></p>
    </div>
  `;
}

/* ---- Step 6: Logistics ---- */
function renderStepLogistics() {
  const l = state.logistics;
  return `
    <div class="field-group">
      <label class="field-label" for="logisticsZip">Event ZIP code</label>
      <input class="field-input" type="text" inputmode="numeric" pattern="[0-9]{5}" maxlength="5" id="logisticsZip" data-bind="logistics.zip" value="${escapeHTML(l.zip)}" placeholder="e.g. 64105" />
      <p class="field-hint">We use ZIP code as a lead field, not for live mileage calculation. Pick your travel range below for pricing.</p>
    </div>

    <div class="field-group">
      <span class="field-label">Distance from Kansas City</span>
      <div class="option-grid" role="radiogroup" aria-label="Distance from Kansas City">
        ${DISTANCE_TIERS.map((o) => `
          <label class="option-card">
            <input type="radio" name="distanceTier" value="${o.id}" data-bind="logistics.distanceTier" ${l.distanceTier === o.id ? "checked" : ""} required />
            <span>${o.label}</span>
          </label>`).join("")}
      </div>
      <p class="field-error" data-error-for="logistics.distanceTier" hidden></p>
    </div>

    <div class="field-group">
      <span class="field-label">Venue access</span>
      <div class="option-grid" role="group" aria-label="Venue access">
        ${VENUE_ACCESS_CHOICES.map((o) => `
          <label class="option-card">
            <input type="checkbox" name="venueAccess" value="${o.id}" data-bind-array="logistics.venueAccess" ${l.venueAccess.includes(o.id) ? "checked" : ""} />
            <span>${o.label}</span>
          </label>`).join("")}
      </div>
    </div>

    <div class="field-group">
      <span class="field-label">Power</span>
      <div class="option-grid" role="group" aria-label="Power">
        ${POWER_CHOICES.map((o) => `
          <label class="option-card">
            <input type="checkbox" name="power" value="${o.id}" data-bind-array="logistics.power" ${l.power.includes(o.id) ? "checked" : ""} />
            <span>${o.label}</span>
          </label>`).join("")}
      </div>
    </div>

    <div class="field-group">
      <span class="field-label">Connectivity and signal</span>
      <div class="option-grid" role="group" aria-label="Connectivity and signal">
        ${CONNECTIVITY_CHOICES.map((o) => `
          <label class="option-card">
            <input type="checkbox" name="connectivity" value="${o.id}" data-bind-array="logistics.connectivity" ${l.connectivity.includes(o.id) ? "checked" : ""} />
            <span>${o.label}</span>
          </label>`).join("")}
      </div>
    </div>
  `;
}

/* ---- Step 7: Estimate ---- */
function renderStepEstimate() {
  const est = calculateEstimate(state);
  if (est.noScreens) {
    return `
      <div class="callout callout-warning">
        <p>No screens selected yet. Go back to the Screens step to choose your package before viewing an estimate.</p>
        <button type="button" class="btn btn-secondary btn-small" data-action="jump-step" data-step="3">Back to Screens</button>
      </div>
    `;
  }

  const rangeBlock = est.customQuoteRequired
    ? `
      <div class="estimate-range estimate-range-custom">
        <p class="estimate-range-label">Custom Quote Required</p>
        <p class="estimate-range-note">Your project includes details our team reviews individually before quoting a final price.</p>
      </div>`
    : `
      <div class="estimate-range">
        <p class="estimate-range-label">Estimated Range</p>
        <p class="estimate-range-value">${formatCurrency(est.totalLow)}–${formatCurrency(est.totalHigh)}</p>
      </div>`;

  return `
    <div class="estimate-block">
      ${rangeBlock}

      ${est.customQuoteRequired ? `
        <div class="callout callout-warning">
          <p class="callout-title">Items requiring manual confirmation</p>
          <ul class="reason-list">
            ${est.customReasons.map((r) => `<li>${escapeHTML(r)}</li>`).join("")}
          </ul>
          <p class="callout-body">A preliminary breakdown is shown below. Our team will follow up with exact pricing after reviewing these details.</p>
        </div>
      ` : ""}

      <h3 class="estimate-subhead">Selected screens</h3>
      <ul class="summary-screen-list">
        ${est.selections.map((l) => `<li>${l.qty} × ${escapeHTML(l.item.name)}${l.item.doubleSided ? " (double-sided)" : ""}</li>`).join("")}
      </ul>
      ${state.screens.activePreset ? `<p class="field-hint">Preset package: ${escapeHTML(SHOWTIME_CONFIG.presets.find((p) => p.id === state.screens.activePreset)?.name || "")}</p>` : ""}

      <h3 class="estimate-subhead">Event details</h3>
      <ul class="summary-detail-list">
        <li>Event days: ${escapeHTML(est.eventDays)}</li>
        <li>Daily operating duration: ${escapeHTML(labelFor(DAILY_DURATIONS, state.schedule.dailyDuration))}</li>
        <li>Setup timing: ${escapeHTML(labelFor(SETUP_TIMINGS, state.schedule.setupTiming))}</li>
        <li>Travel: ${escapeHTML(labelFor(DISTANCE_TIERS, state.logistics.distanceTier))}</li>
        <li>Audio: ${escapeHTML(labelFor(AUDIO_CHOICES, state.production.audio))}</li>
        <li>Power: ${state.logistics.power.length ? escapeHTML(state.logistics.power.map((id) => labelFor(POWER_CHOICES, id)).join(", ")) : "Not specified"}</li>
        <li>Connectivity: ${state.logistics.connectivity.length ? escapeHTML(state.logistics.connectivity.map((id) => labelFor(CONNECTIVITY_CHOICES, id)).join(", ")) : "Not specified"}</li>
      </ul>

      <h3 class="estimate-subhead">Package breakdown</h3>
      <table class="breakdown-table">
        <tbody>
          ${est.breakdown.map((row) => renderBreakdownRow(row, est.customQuoteRequired)).join("")}
        </tbody>
      </table>

      ${est.pendingItems.length ? `
        <div class="callout callout-note">
          <p class="callout-title">Pending confirmation</p>
          <ul class="reason-list">${est.pendingItems.map((i) => `<li>${escapeHTML(i)}</li>`).join("")}</ul>
        </div>` : ""}

      <p class="disclaimer">This is an estimate for planning purposes only. It is not a confirmed reservation or a guaranteed final price. Showtime LED will confirm exact pricing and availability.</p>

      <div class="estimate-actions">
        <button type="button" class="btn btn-primary btn-large" data-action="open-lead-modal">Request Exact Quote</button>
      </div>
      <div class="estimate-secondary-actions">
        <button type="button" class="btn btn-tertiary" data-action="email-estimate">Email Me This Estimate</button>
        <button type="button" class="btn btn-tertiary" data-action="copy-estimate">Copy Estimate</button>
        <button type="button" class="btn btn-tertiary" data-action="start-over">Start Over</button>
      </div>
    </div>
  `;
}

function renderBreakdownRow(row, customQuoteRequired) {
  if (row.isInfo) {
    return `<tr class="breakdown-row breakdown-row-info"><td>${escapeHTML(row.label)}</td><td>${row.items.length ? row.items.length + " item" + (row.items.length === 1 ? "" : "s") : "None"}</td></tr>`;
  }
  if (row.isCustom) {
    return `<tr class="breakdown-row"><td>${escapeHTML(row.label)}</td><td>Pending review</td></tr>`;
  }
  const sign = row.low < 0 || row.high < 0 ? "−" : "";
  const lowAbs = Math.abs(roundMoney(row.low));
  const highAbs = Math.abs(roundMoney(row.high));
  const display = lowAbs === 0 && highAbs === 0 ? "No additional charge" : `${sign}${formatCurrency(lowAbs)}–${sign}${formatCurrency(highAbs)}`;
  return `<tr class="breakdown-row"><td>${escapeHTML(row.label)}</td><td>${display}</td></tr>`;
}

function labelFor(list, id) {
  const found = list.find((o) => o.id === id);
  return found ? found.label : "Not specified";
}

/* ============================================================================
   SUMMARY PANEL (desktop sticky sidebar) + MOBILE BOTTOM BAR
   ==========================================================================*/

function renderSummaryPanel() {
  const est = calculateEstimate(state);
  const units = totalSelectedUnits();
  return `
    <div class="summary-card">
      <p class="summary-eyebrow">Your Package So Far</p>
      <p class="summary-screens">${units} screen${units === 1 ? "" : "s"} selected</p>
      ${renderSummaryRange(est)}
      ${units > 0 ? `
        <ul class="summary-screen-list summary-screen-list-compact">
          ${getSelectedLines().map((l) => `<li>${l.qty} × ${escapeHTML(l.item.name)}</li>`).join("")}
        </ul>` : `<p class="field-hint">Select screens in Step 3 to see them here.</p>`}
      <p class="disclaimer disclaimer-small">Estimate only — not a confirmed reservation or final price.</p>
    </div>
  `;
}

function renderSummaryRange(est) {
  if (est.noScreens) return `<p class="summary-range-placeholder">No screens selected yet</p>`;
  if (est.customQuoteRequired) return `<p class="summary-range-value summary-range-custom">Custom Quote Required</p>`;
  return `<p class="summary-range-value">${formatCurrency(est.totalLow)}–${formatCurrency(est.totalHigh)}</p>`;
}

function renderMobileBar() {
  const est = calculateEstimate(state);
  const units = totalSelectedUnits();
  const isFirst = state.currentStep === 1;
  const isLast = state.currentStep === 7;
  let rangeText = "Add screens to see pricing";
  if (!est.noScreens) {
    rangeText = est.customQuoteRequired ? "Custom Quote Required" : `${formatCurrency(est.totalLow)}–${formatCurrency(est.totalHigh)}`;
  }
  return `
    <div class="mobile-bar">
      <div class="mobile-bar-info">
        <span class="mobile-bar-count">${units} screen${units === 1 ? "" : "s"}</span>
        <span class="mobile-bar-range">${rangeText}</span>
      </div>
      <div class="mobile-bar-actions">
        <button type="button" class="btn btn-secondary btn-small" data-action="prev-step" ${isFirst ? "disabled" : ""}>Back</button>
        ${isLast
          ? `<button type="button" class="btn btn-primary btn-small" data-action="open-lead-modal" ${est.noScreens ? "disabled" : ""}>Get Quote</button>`
          : `<button type="button" class="btn btn-primary btn-small" data-action="next-step">Continue</button>`}
      </div>
    </div>
  `;
}

/* ============================================================================
   LEAD CAPTURE MODAL
   ==========================================================================*/

function renderLeadModal() {
  const l = state.lead;
  return `
    <div class="modal-overlay" id="leadModalOverlay" hidden>
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="leadModalTitle">
        <button type="button" class="modal-close" data-action="close-lead-modal" aria-label="Close">&times;</button>
        <h2 class="modal-title" id="leadModalTitle">Request Exact Quote</h2>
        <p class="modal-sub">Tell us how to reach you and we'll follow up with exact pricing and availability. This does not reserve equipment.</p>
        <form id="leadForm" novalidate>
          <div class="field-row">
            <div class="field-group">
              <label class="field-label" for="leadName">Name</label>
              <input class="field-input" type="text" id="leadName" data-bind="lead.name" value="${escapeHTML(l.name)}" maxlength="120" required />
              <p class="field-error" data-error-for="lead.name" hidden></p>
            </div>
            <div class="field-group">
              <label class="field-label" for="leadEmail">Email</label>
              <input class="field-input" type="email" id="leadEmail" data-bind="lead.email" value="${escapeHTML(l.email)}" maxlength="180" required />
              <p class="field-error" data-error-for="lead.email" hidden></p>
            </div>
          </div>
          <div class="field-row">
            <div class="field-group">
              <label class="field-label" for="leadPhone">Phone</label>
              <input class="field-input" type="tel" id="leadPhone" data-bind="lead.phone" value="${escapeHTML(l.phone)}" maxlength="30" required />
              <p class="field-error" data-error-for="lead.phone" hidden></p>
            </div>
            <div class="field-group">
              <label class="field-label" for="leadCompany">Company or organization <span class="optional-tag">Optional</span></label>
              <input class="field-input" type="text" id="leadCompany" data-bind="lead.company" value="${escapeHTML(l.company)}" maxlength="120" />
            </div>
          </div>
          <div class="field-row">
            <div class="field-group">
              <label class="field-label" for="leadEventDate">Event date</label>
              <input class="field-input" type="date" id="leadEventDate" data-bind="lead.eventDate" value="${escapeHTML(l.eventDate)}" required />
              <p class="field-error" data-error-for="lead.eventDate" hidden></p>
            </div>
            <div class="field-group">
              <label class="field-label" for="leadZip">Event ZIP code</label>
              <input class="field-input" type="text" inputmode="numeric" pattern="[0-9]{5}" maxlength="5" id="leadZip" data-bind="lead.zip" value="${escapeHTML(l.zip)}" required />
              <p class="field-error" data-error-for="lead.zip" hidden></p>
            </div>
          </div>
          <div class="field-group">
            <label class="field-label" for="leadNotes">Notes <span class="optional-tag">Optional</span></label>
            <textarea class="field-input" id="leadNotes" data-bind="lead.notes" maxlength="600" rows="3">${escapeHTML(l.notes)}</textarea>
          </div>
          <p class="disclaimer">Submitting sends your selections to Showtime LED for review. This is not a confirmed reservation or final price.</p>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary" data-action="close-lead-modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Send to Showtime LED</button>
          </div>
        </form>
      </div>
    </div>
  `;
}

function renderConfirmDialog() {
  return `
    <div class="modal-overlay" id="confirmOverlay" hidden>
      <div class="modal modal-small" role="alertdialog" aria-modal="true" aria-labelledby="confirmTitle">
        <h2 class="modal-title" id="confirmTitle" data-confirm-title></h2>
        <p class="modal-sub" data-confirm-body></p>
        <div class="modal-actions">
          <button type="button" class="btn btn-secondary" data-action="confirm-cancel">Cancel</button>
          <button type="button" class="btn btn-primary" data-action="confirm-accept">Confirm</button>
        </div>
      </div>
    </div>
  `;
}

let pendingConfirmCallback = null;

function openConfirmDialog(title, body, onConfirm) {
  pendingConfirmCallback = onConfirm;
  const overlay = document.getElementById("confirmOverlay");
  if (!overlay) return;
  overlay.querySelector("[data-confirm-title]").textContent = title;
  overlay.querySelector("[data-confirm-body]").textContent = body;
  overlay.hidden = false;
  postIframeHeight();
}

function closeConfirmDialog() {
  const overlay = document.getElementById("confirmOverlay");
  if (overlay) overlay.hidden = true;
  pendingConfirmCallback = null;
}

function openLeadModal() {
  // Pre-fill lead fields from event answers when available.
  if (!state.lead.eventDate) state.lead.eventDate = state.event.eventDate;
  if (!state.lead.zip) state.lead.zip = state.event.zip || state.logistics.zip;
  const overlay = document.getElementById("leadModalOverlay");
  if (!overlay) return;
  // Re-render the modal body so pre-filled values show.
  overlay.outerHTML = renderLeadModal();
  document.getElementById("leadModalOverlay").hidden = false;
  attachGlobalListeners();
  postIframeHeight();
  const firstInput = document.getElementById("leadName");
  if (firstInput) firstInput.focus();
}

function closeLeadModal() {
  const overlay = document.getElementById("leadModalOverlay");
  if (overlay) overlay.hidden = true;
  postIframeHeight();
}

/* ============================================================================
   VALIDATION
   ==========================================================================*/

const STEP_REQUIRED_FIELDS = {
  1: [
    { path: "event.eventType", message: "Select an event type." },
    { path: "event.eventDate", message: "Enter the event date." },
    { path: "event.eventDays", message: "Enter the number of event days.", numeric: true },
    { path: "event.zip", message: "Enter a valid 5-digit ZIP code.", zip: true },
    { path: "event.attendance", message: "Select an attendance range." },
    { path: "event.venueSetting", message: "Select indoor or outdoor." }
  ],
  2: [
    { path: "coverage.goal", message: "Select what you need the screens to accomplish." },
    { path: "coverage.viewingDistance", message: "Select a maximum viewing distance." }
  ],
  3: [],
  4: [
    { path: "schedule.dailyDuration", message: "Select a daily operating duration." },
    { path: "schedule.scheduleType", message: "Select an event schedule type." },
    { path: "schedule.setupTiming", message: "Select a setup timing." }
  ],
  5: [
    { path: "production.audio", message: "Select an audio option." }
  ],
  6: [
    { path: "logistics.distanceTier", message: "Select a distance range." }
  ],
  7: []
};

function getByPath(obj, path) {
  return path.split(".").reduce((acc, key) => (acc === undefined || acc === null ? acc : acc[key]), obj);
}

function validateStep(step) {
  const errors = [];
  const rules = STEP_REQUIRED_FIELDS[step] || [];
  rules.forEach((rule) => {
    const value = getByPath(state, rule.path);
    let valid = value !== undefined && value !== null && String(value).trim() !== "";
    if (valid && rule.numeric) valid = Number(value) > 0;
    if (valid && rule.zip) valid = /^\d{5}$/.test(String(value).trim());
    if (!valid) errors.push(rule);
  });
  if (step === 3 && totalSelectedUnits() === 0) {
    errors.push({ path: "screens.selections", message: "Select at least one screen to continue." });
  }
  return errors;
}

function showStepErrors(errors) {
  document.querySelectorAll("[data-error-for]").forEach((el) => { el.hidden = true; el.textContent = ""; });
  errors.forEach((err) => {
    const el = document.querySelector(`[data-error-for="${err.path}"]`);
    if (el) { el.textContent = err.message; el.hidden = false; }
    const input = document.querySelector(`[data-bind="${err.path}"]`);
    if (input) input.setAttribute("aria-invalid", "true");
  });
  const first = document.querySelector('[data-error-for]:not([hidden])');
  if (first) first.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "center" });
  postIframeHeight();
}

function validateLeadForm() {
  const errors = [];
  const required = [
    { path: "lead.name", message: "Enter your name." },
    { path: "lead.email", message: "Enter a valid email address.", email: true },
    { path: "lead.phone", message: "Enter a phone number." },
    { path: "lead.eventDate", message: "Enter the event date." },
    { path: "lead.zip", message: "Enter a valid 5-digit ZIP code.", zip: true }
  ];
  required.forEach((rule) => {
    const value = getByPath(state, rule.path);
    let valid = value !== undefined && value !== null && String(value).trim() !== "";
    if (valid && rule.email) valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value).trim());
    if (valid && rule.zip) valid = /^\d{5}$/.test(String(value).trim());
    if (!valid) errors.push(rule);
  });
  return errors;
}

function prefersReducedMotion() {
  return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/* ============================================================================
   NAVIGATION
   ==========================================================================*/

function goToStep(step) {
  state.currentStep = clampInt(step, 1, 7, 1);
  saveState();
  renderApp();
  const main = document.getElementById("wizardMain");
  if (main) main.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
}

function nextStep() {
  const errors = validateStep(state.currentStep);
  if (errors.length) { showStepErrors(errors); return; }
  if (state.currentStep >= 7) return;
  goToStep(state.currentStep + 1);
}

function prevStep() {
  if (state.currentStep <= 1) return;
  goToStep(state.currentStep - 1);
}

function startMode(mode) {
  state.mode = mode;
  state.currentStep = 1;
  saveState();
  renderApp();
}

/* ============================================================================
   EVENT WIRING
   Delegated listeners are re-attached after every render since render
   replaces innerHTML. Using data-action / data-bind keeps markup declarative.
   ==========================================================================*/

function setByPath(obj, path, value) {
  const keys = path.split(".");
  let target = obj;
  for (let i = 0; i < keys.length - 1; i++) target = target[keys[i]];
  target[keys[keys.length - 1]] = value;
}

function attachGlobalListeners() {
  const root = document.getElementById("app");
  if (!root) return;

  // Bound single-value inputs (text/select/radio/date/number/textarea).
  root.querySelectorAll("[data-bind]").forEach((el) => {
    const eventName = (el.tagName === "SELECT" || el.type === "radio" || el.type === "checkbox") ? "change" : "input";
    el.addEventListener(eventName, (e) => {
      const path = el.getAttribute("data-bind");
      if (el.type === "radio" && !el.checked) return;
      setByPath(state, path, el.value);
      saveState();
      if (path === "screens.selections") return;
      // Re-render only the parts that can change as a result (summary, mobile bar, and
      // for a few fields the current step itself, since conditional sections may appear).
      refreshDynamicRegions(path);
    });
  });

  // Bound checkbox-array inputs.
  root.querySelectorAll("[data-bind-array]").forEach((el) => {
    el.addEventListener("change", () => {
      const path = el.getAttribute("data-bind-array");
      const arr = getByPath(state, path);
      const idx = arr.indexOf(el.value);
      if (el.checked && idx === -1) arr.push(el.value);
      if (!el.checked && idx !== -1) arr.splice(idx, 1);
      saveState();
      refreshDynamicRegions(path);
    });
  });

  // Delegated click handling for every data-action button.
  root.addEventListener("click", handleActionClick);

  const stepForm = document.getElementById("stepForm");
  if (stepForm) {
    stepForm.addEventListener("submit", (e) => e.preventDefault());
  }

  const leadForm = document.getElementById("leadForm");
  if (leadForm) {
    leadForm.addEventListener("submit", (e) => {
      e.preventDefault();
      submitLeadForm();
    });
  }

  checkRestoreNote();
}

// Certain fields affect conditional UI (recommendation, license note, video
// feed question, modular fields) so those steps get a light re-render instead
// of a full app re-render, which would lose focus on the active input.
const FIELDS_NEEDING_STEP_REFRESH = new Set([
  "coverage.goal", "event.attendance", "event.eventType",
  "production.contentTypes", "schedule.scheduleType", "schedule.setupTiming"
]);

function refreshDynamicRegions(changedPath) {
  const summary = document.getElementById("wizardSummary");
  if (summary) summary.innerHTML = renderSummaryPanel();
  const mobileBarHost = document.querySelector(".mobile-bar");
  if (mobileBarHost) mobileBarHost.outerHTML = renderMobileBar();
  if (FIELDS_NEEDING_STEP_REFRESH.has(changedPath) || changedPath.startsWith("production.support")) {
    const form = document.getElementById("stepForm");
    if (form) {
      form.innerHTML = renderCurrentStep();
      attachGlobalListeners();
    }
  }
  postIframeHeight();
}

function handleActionClick(e) {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.getAttribute("data-action");

  switch (action) {
    case "start-mode":
      startMode(btn.getAttribute("data-mode"));
      break;
    case "resume-progress":
      goToStep(state.currentStep || 1);
      break;
    case "clear-progress":
      clearState(true);
      break;
    case "next-step":
      nextStep();
      break;
    case "prev-step":
      prevStep();
      break;
    case "jump-step": {
      const target = parseInt(btn.getAttribute("data-step"), 10);
      if (target <= state.currentStep) goToStep(target);
      break;
    }
    case "qty-increment": {
      const id = btn.getAttribute("data-screen");
      setScreenQty(id, toPositiveInt(state.screens.selections[id], 0) + 1);
      rerenderScreenStep();
      break;
    }
    case "qty-decrement": {
      const id = btn.getAttribute("data-screen");
      setScreenQty(id, toPositiveInt(state.screens.selections[id], 0) - 1);
      rerenderScreenStep();
      break;
    }
    case "apply-preset":
      applyPreset(btn.getAttribute("data-preset"));
      rerenderScreenStep();
      break;
    case "apply-recommendation":
      applyRecommendation(getOrComputeRecommendation());
      rerenderScreenStep();
      break;
    case "open-lead-modal": {
      const errors = validateStep(3).concat(state.currentStep === 7 ? [] : []);
      if (totalSelectedUnits() === 0) { goToStep(3); break; }
      openLeadModal();
      break;
    }
    case "close-lead-modal":
      closeLeadModal();
      break;
    case "email-estimate":
      emailEstimate();
      break;
    case "copy-estimate":
      copyEstimate(btn);
      break;
    case "start-over":
      clearState(false);
      break;
    case "confirm-accept":
      if (typeof pendingConfirmCallback === "function") pendingConfirmCallback();
      closeConfirmDialog();
      break;
    case "confirm-cancel":
      closeConfirmDialog();
      break;
    default:
      break;
  }
}

function rerenderScreenStep() {
  const form = document.getElementById("stepForm");
  if (form) {
    form.innerHTML = renderCurrentStep();
    attachGlobalListeners();
  }
  const summary = document.getElementById("wizardSummary");
  if (summary) summary.innerHTML = renderSummaryPanel();
  const mobileBarHost = document.querySelector(".mobile-bar");
  if (mobileBarHost) mobileBarHost.outerHTML = renderMobileBar();
  postIframeHeight();
}

function checkRestoreNote() {
  const note = document.querySelector("[data-restore-note]");
  if (!note) return;
  let hasSaved = false;
  try {
    hasSaved = !!localStorage.getItem(STORAGE_KEY) && state.currentStep > 0;
  } catch (err) { hasSaved = false; }
  note.hidden = !hasSaved;
}

/* ============================================================================
   LEAD SUBMISSION / OUTPUT
   ==========================================================================*/

function buildQuoteSummaryText(est) {
  const lines = [];
  lines.push(`Showtime LED Estimate`);
  lines.push(`Event: ${state.event.eventType || "Not specified"} on ${state.event.eventDate || "TBD"}`);
  lines.push(`Screens: ${est.selections ? est.selections.map((l) => `${l.qty}x ${l.item.name}`).join(", ") : "None selected"}`);
  lines.push(`Event days: ${state.schedule.eventDays || state.event.eventDays || 1}`);
  lines.push(`Estimated range: ${est.customQuoteRequired ? "Custom Quote Required" : `${formatCurrency(est.totalLow)}-${formatCurrency(est.totalHigh)}`}`);
  return lines.join("\n");
}

function buildQuotePayload() {
  const est = calculateEstimate(state);
  const summaryText = est.noScreens ? "No screens selected" : buildQuoteSummaryText(est);
  return {
    customer: { ...state.lead },
    event: { ...state.event },
    screens: est.selections ? est.selections.map((l) => ({ id: l.item.id, name: l.item.name, qty: l.qty })) : [],
    production: { ...state.production },
    logistics: { ...state.logistics },
    estimate: est.noScreens ? {} : {
      low: est.totalLow,
      high: est.totalHigh,
      customQuoteRequired: est.customQuoteRequired,
      customReasons: est.customReasons,
      pendingItems: est.pendingItems
    },
    summary: summaryText
  };
}

function submitLeadForm() {
  const errors = validateLeadForm();
  showStepErrors([]); // clear existing (lead form uses same error markup convention)
  document.querySelectorAll('#leadForm [data-error-for]').forEach((el) => { el.hidden = true; });
  if (errors.length) {
    errors.forEach((err) => {
      const el = document.querySelector(`#leadForm [data-error-for="${err.path}"]`);
      if (el) { el.textContent = err.message; el.hidden = false; }
    });
    postIframeHeight();
    return;
  }
  saveState();
  sendQuoteToShowtime();
}

function sendQuoteToShowtime() {
  const quoteId = generateQuoteId();
  const payload = buildQuotePayload();

  // 1) Persist a full backup of the quote in localStorage.
  try {
    localStorage.setItem("showtimeLedLastQuote", JSON.stringify({ quoteId, submittedAt: new Date().toISOString(), ...payload }));
  } catch (err) {
    console.warn("Showtime estimator: could not store quote backup.", err);
  }

  // 2) Notify a parent Wix page via postMessage (for a future Velo integration).
  try {
    window.parent.postMessage({ type: "SHOWTIME_QUOTE_ESTIMATE", payload }, "*");
  } catch (err) {
    console.warn("Showtime estimator: postMessage failed.", err);
  }

  // 3) Build the URL for the configured Wix quote page and open it in the top window.
  const url = buildQuoteUrl(quoteId, payload);
  window.open(url, "_top");
}

// Builds a URL with individual fields as query params plus one compact
// encoded summary, capped to a safe overall length.
function buildQuoteUrl(quoteId, payload) {
  const base = SHOWTIME_CONFIG.quotePageUrl;
  const params = new URLSearchParams();
  params.set("quoteId", quoteId);
  params.set("name", payload.customer.name || "");
  params.set("email", payload.customer.email || "");
  params.set("phone", payload.customer.phone || "");
  params.set("company", payload.customer.company || "");
  params.set("eventDate", payload.customer.eventDate || "");
  params.set("zip", payload.customer.zip || "");
  params.set("eventType", payload.event.eventType || "");
  params.set("low", payload.estimate.low ?? "");
  params.set("high", payload.estimate.high ?? "");
  params.set("customQuote", payload.estimate.customQuoteRequired ? "1" : "0");

  let summary = payload.summary || "";
  const MAX_URL_LENGTH = 1800; // stays well under practical browser/query limits
  let encodedSummary = encodeURIComponent(summary);
  while ((base.length + params.toString().length + encodedSummary.length + 20) > MAX_URL_LENGTH && summary.length > 0) {
    summary = summary.slice(0, summary.length - 40);
    encodedSummary = encodeURIComponent(summary + "...");
  }
  params.set("summary", summary);

  const separator = base.includes("?") ? "&" : "?";
  return `${base}${separator}${params.toString()}`;
}

/* ============================================================================
   EMAIL ESTIMATE (mailto, no backend)
   ==========================================================================*/

function emailEstimate() {
  const est = calculateEstimate(state);
  if (est.noScreens) return;
  const subject = encodeURIComponent(`Showtime LED Estimate — ${state.event.eventType || "Event"} on ${state.event.eventDate || "TBD"}`);
  const body = encodeURIComponent(buildQuoteSummaryText(est) + "\n\nThis estimate is for planning purposes only and is not a confirmed reservation or final price.");
  const mailtoUrl = `mailto:${SHOWTIME_CONFIG.company.email}?subject=${subject}&body=${body}`;
  showToast("Opening your email application…");
  window.location.href = mailtoUrl;
}

/* ============================================================================
   COPY ESTIMATE
   ==========================================================================*/

function copyEstimate(triggerBtn) {
  const est = calculateEstimate(state);
  if (est.noScreens) return;
  const text = buildQuoteSummaryText(est);

  const showConfirmed = () => showToast("Estimate copied to clipboard.");
  const showFailed = () => showToast("Could not copy automatically — please select and copy the text manually.");

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(showConfirmed).catch(() => legacyCopy(text, showConfirmed, showFailed));
  } else {
    legacyCopy(text, showConfirmed, showFailed);
  }
}

function legacyCopy(text, onSuccess, onFail) {
  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    if (ok) onSuccess(); else onFail();
  } catch (err) {
    onFail();
  }
}

let toastTimer = null;
function showToast(message) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.hidden = false;
  toast.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.classList.remove("is-visible");
    toast.hidden = true;
  }, 3200);
  postIframeHeight();
}

/* ============================================================================
   IFRAME HEIGHT MESSAGING
   Keeps the Wix embed sized to its content instead of showing an internal
   scrollbar or clipping content.
   ==========================================================================*/

function postIframeHeight() {
  try {
    const height = document.documentElement.scrollHeight;
    window.parent.postMessage({ type: "SHOWTIME_IFRAME_HEIGHT", height }, "*");
  } catch (err) {
    // Not embedded, or parent unavailable — safe to ignore.
  }
}

const debouncedPostHeight = debounce(postIframeHeight, 120);

/* ============================================================================
   INIT
   ==========================================================================*/

function initApp() {
  state = loadState();
  renderApp();
  window.addEventListener("resize", debouncedPostHeight);
  if (window.ResizeObserver) {
    const ro = new ResizeObserver(debouncedPostHeight);
    ro.observe(document.body);
  }
  postIframeHeight();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}

