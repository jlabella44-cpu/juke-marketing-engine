# Showtime LED — Build Your Screen Package Estimator

A self-contained quote estimator for Showtime LED's mobile LED screen packages. Plain HTML, CSS, and vanilla JavaScript — no frameworks, no build step, no external services. Everything needed to run it locally or embed it in Wix is in this folder.

## Files

| File | Purpose |
|---|---|
| `index.html` | The app, for local development and testing. Links to `styles.css` and `app.js`. |
| `styles.css` | All styling. |
| `app.js` | All application logic, including `SHOWTIME_CONFIG` (every price and rule). |
| `wix-embed.html` | **The file you paste into Wix.** Same app as above with CSS and JS inlined into one file. |
| `README.md` | This file. |

Open `index.html` directly in a browser to run the tool locally — no server, no `npm install`, nothing to build.

---

## 1. Which file goes into Wix

Use **`wix-embed.html`** — and only that file. It contains the full app (HTML + CSS + JS) in one document with no external file references, which is what Wix's HTML embed element requires.

`index.html` / `styles.css` / `app.js` are the source files for local editing and testing. Whenever you change any of them, regenerate `wix-embed.html` (see "Keeping wix-embed.html in sync" below) before publishing.

### Pasting into Wix

1. In the Wix Editor, add an **Embed → Custom Embeds → HTML iframe** element to the page.
2. Open its code panel and choose **"Enter Code"** (not "Enter URL").
3. Open `wix-embed.html` in a text editor, select all, copy, and paste the entire contents into the Wix code panel.
4. Set the embed element's width to 100% of its container. Do not set a fixed height — the tool tells the page how tall it is automatically (see "Iframe height" below). Give it a reasonable starting height (e.g. 900px) so it doesn't look collapsed before the first height message arrives.
5. Publish the page and test on both desktop and mobile.

---

## 2. How to change the quote-page URL

Open `app.js` (and re-sync into `wix-embed.html`), find `SHOWTIME_CONFIG` near the top, and edit:

```js
quotePageUrl: "https://www.showtimeled.com/get-a-quote",
```

Set this to the live Wix page that should receive the completed quote. When a customer clicks **Request Exact Quote**, the tool opens this URL with `target="_top"` (so it replaces the whole browser tab, not just the iframe) and appends the quote details as URL query parameters.

---

## 3. How to change the Showtime email address

Same `SHOWTIME_CONFIG` object, `company` section:

```js
company: {
  name: "Showtime LED",
  email: "quotes@showtimeled.com",   // used by "Email Me This Estimate"
  phone: "(816) 555-0100",
  website: "https://www.showtimeled.com"
},
```

The `email` value is used to build the `mailto:` link behind **Email Me This Estimate**. There is no backend involved — clicking the button opens the customer's own email application with the subject and body pre-filled, addressed to this address.

---

## 4. How to replace sample prices

**Every dollar amount in the entire tool lives inside `SHOWTIME_CONFIG` at the top of `app.js`.** Nothing outside that object should ever contain a price — if you search the rest of the file for `low:` or `high:` outside `SHOWTIME_CONFIG`, you won't find pricing.

The current values are clearly marked as samples:

```js
/*
 * REPLACE SAMPLE VALUES WITH APPROVED SHOWTIME LED PRICING BEFORE PUBLISHING.
 */
```

Sections to review before going live, in the order they appear in `SHOWTIME_CONFIG`:

- **`inventory[].dailyRate`** — equipment rate per unit, per operating day (low/high).
- **`durationTiers`** — extra cost per unit per day for longer operating windows.
- **`multiDayDiscount`** — discount percentages applied to days after the first.
- **`multiScreenDiscount`** — discount percentages applied to shared setup costs when 2+ screens are booked.
- **`travel.tiers`** — flat fee + per-vehicle rate for each distance tier.
- **`setup`** — base setup/teardown charge, per-additional-unit charge, day-before and multi-day setup add-ons.
- **`holdDay`** — per-day charge for equipment left on site (overnight, festival holds, etc).
- **`crew`** — additional operator and IMAG/live-camera integration rates.
- **`productionAddons`**, **`audioOptions`**, **`powerOptions`**, **`connectivityOptions`**, **`venueAccessOptions`** — flat add-on costs for each checkbox/option in Steps 5 and 6.

Every rate is a `{ low, high }` pair. The estimator always computes a low total and a high total separately and never a single number, so keep both fields set on every entry you edit.

After editing prices in `app.js`, **regenerate `wix-embed.html`** (see below) so the embed file matches.

---

## 5. How to adjust screen inventory

Still inside `SHOWTIME_CONFIG`, edit the `inventory` array. To change how many of a screen Showtime owns, change `totalInventory`:

```js
{
  id: "trailer-16x9",
  name: "16×9 Mobile LED Trailer",
  ...
  totalInventory: 2,   // <-- change this
  ...
}
```

The quantity stepper on each screen card automatically enforces this number — customers cannot select more units than `totalInventory`, and a warning appears once the limit is reached. Preset packages (see below) are also clamped to available inventory automatically.

## Adding a new screen

Add a new object to the `inventory` array, following the shape of the existing entries:

```js
{
  id: "unique-id-no-spaces",
  name: "Display Name",
  dims: "Dimensions shown on the card",
  shortDescription: "One or two sentence description.",
  bestFor: ["Use case 1", "Use case 2"],
  totalInventory: 1,
  unitLabel: "trailer",       // or "display", "system", etc — used in "X trailers available"
  dailyRate: { low: 0, high: 0 },   // REPLACE with real pricing
  transportWeight: 1,          // how much of a delivery vehicle one unit uses (used to estimate vehicle count for travel pricing)
  large: false,                 // true counts this screen toward the "more than two large screens" custom-quote rule
  doubleSided: false,
  configurable: false           // set true + add configOptions if it needs size/mount pickers like the Modular LED Screen
}
```

The screen will automatically appear as a card in Step 3 with a quantity stepper, inventory warning, and "Why this screen?" panel — no other code changes are required. If you want it included in a preset package, add a line to that preset's `lines` array in `SHOWTIME_CONFIG.presets`.

---

## 6. How to modify recommendation rules

The recommendation engine is the `computeRecommendation(state)` function in `app.js`, in the "RECOMMENDATION ENGINE" section. It's a plain `switch` statement keyed on the customer's Step 2 coverage goal (`s.coverage.goal`), with attendance and viewing distance used as secondary signals. Each branch:

1. Adds one or more screens/quantities to a `lines` array via `addLine(lines, screenId, qty)`.
2. Sets a plain-English `reason` string shown to the customer under "Recommended because…".
3. Optionally sets `customFlag = true` for coverage goals that always require review (currently only stage-integrated / modular).

To change a rule, edit the relevant `case` block. For example, to change the attendance threshold that recommends a 16×9 instead of a 12×7 for a single viewing area, look at the `default` branch and change the `attendance >= 300` check. Attendance range IDs are mapped to approximate numeric midpoints in the `ATTENDANCE_APPROX` object just above the function — adjust those numbers if you want different thresholds to trigger different screens.

Recommended lines are automatically clamped to available inventory (`clampLinesToInventory`), so a rule can never recommend more units than the fleet has.

The recommendation is always advisory. Every screen card can be freely adjusted afterward, and the "Choose My Screens" path skips the recommendation banner entirely (though the same inventory and pricing rules still apply).

---

## 7. How to change screen descriptions, best-use cases, and other copy

- **Screen descriptions, dimensions, and "best for" lists** — `SHOWTIME_CONFIG.inventory[].shortDescription` / `.dims` / `.bestFor`.
- **Preset package names/descriptions** — `SHOWTIME_CONFIG.presets`.
- **Step questions and choice labels** (event types, attendance ranges, coverage goals, schedule options, production/audio/power/connectivity choices, venue access items, distance tiers) — the constant arrays just below `SHOWTIME_CONFIG` in `app.js` (`EVENT_TYPES`, `ATTENDANCE_OPTIONS`, `COVERAGE_GOALS`, `VIEWING_DISTANCES`, `DAILY_DURATIONS`, `SCHEDULE_TYPES`, `SETUP_TIMINGS`, `CONTENT_TYPES`, `MULTI_SCREEN_CONTENT_OPTIONS`, `PRODUCTION_SUPPORT_OPTIONS`, `AUDIO_CHOICES`, `DISTANCE_TIERS`, `VENUE_ACCESS_CHOICES`, `POWER_CHOICES`, `CONNECTIVITY_CHOICES`). Each is a simple array of `{ id, label }` objects (or plain strings for `EVENT_TYPES`) — reorder, rename, add, or remove entries as needed. If you add or remove an option that pricing depends on, also add or remove the matching entry in `SHOWTIME_CONFIG`.
- **Custom-quote thresholds** (e.g. "more than 7 event days") — `SHOWTIME_CONFIG.customQuoteThresholds`.

---

## How the postMessage integration works

The tool talks to its parent window (the Wix page) using `window.parent.postMessage`, so it works from inside an iframe without any shared backend. Two message types are sent:

### 1. Iframe height — sent continuously

```js
{ type: "SHOWTIME_IFRAME_HEIGHT", height: document.documentElement.scrollHeight }
```

Sent on initial load, on every step change, when a "Why this screen?" panel or any conditional section expands, when validation errors appear, on window resize, and whenever the page's rendered height otherwise changes (via a `ResizeObserver` on `document.body`). This lets the parent page resize the iframe to fit the content exactly, so there's no double scrollbar and nothing gets clipped.

### 2. Quote submission — sent once, when "Request Exact Quote" is submitted

```js
{
  type: "SHOWTIME_QUOTE_ESTIMATE",
  payload: {
    customer: { name, email, phone, company, eventDate, zip, notes },
    event: { eventType, eventDate, eventDays, zip, attendance, venueSetting, orgName },
    screens: [ { id, name, qty }, ... ],
    production: { contentTypes, multiScreenContent, support, audio, videoFeeds },
    logistics: { zip, distanceTier, venueAccess, power, connectivity },
    estimate: { low, high, customQuoteRequired, customReasons, pendingItems },
    summary: "Plain-text summary of the quote"
  }
}
```

At the same time, the tool:

- Opens `SHOWTIME_CONFIG.quotePageUrl` with `target="_top"`, appending the customer's name, email, phone, company, event date, ZIP, event type, price range, and a compact encoded summary as URL query parameters (kept under ~1,800 characters total, trimming the summary text if needed).
- Saves a full backup copy of the quote to `localStorage` under the key `showtimeLedLastQuote`, in case the Wix page wants to read it back later or for support/debugging purposes.

## How to listen for quote messages in Wix Velo

In the Velo code for the page containing the HTML embed element (e.g. `#html1`):

```js
$w.onReady(function () {
  $w("#html1").onMessage((event) => {
    const msg = event.data;
    if (msg && msg.type === "SHOWTIME_QUOTE_ESTIMATE") {
      const quote = msg.payload;
      // quote.customer, quote.event, quote.screens, quote.estimate, quote.summary, etc.
      // e.g. write it to a CMS collection, trigger an email via a backend web module, etc.
    }
  });
});
```

## How to listen for iframe-height messages in Wix Velo

```js
$w.onReady(function () {
  $w("#html1").onMessage((event) => {
    const msg = event.data;
    if (msg && msg.type === "SHOWTIME_IFRAME_HEIGHT" && typeof msg.height === "number") {
      $w("#html1").height = msg.height;
    }
  });
});
```

Both handlers can live in the same `onMessage` callback — just branch on `msg.type`.

---

## Keeping wix-embed.html in sync

`wix-embed.html` is a generated copy of `index.html` with `styles.css` and `app.js` inlined. Whenever you edit any of the three source files, regenerate it so Wix stays in sync. There's no build tool required — any of these work:

**Manually:** Open `index.html`, replace `<link rel="stylesheet" href="styles.css" />` with `<style>...</style>` containing the full contents of `styles.css`, and replace `<script src="app.js"></script>` with `<script>...</script>` containing the full contents of `app.js`. Save as `wix-embed.html`.

**With a one-line script** (Python, run from this folder):

```bash
python3 -c "
html = open('index.html').read()
css = open('styles.css').read()
js = open('app.js').read()
html = html.replace('<link rel=\"stylesheet\" href=\"styles.css\" />', f'<style>\n{css}\n</style>')
html = html.replace('<script src=\"app.js\"></script>', f'<script>\n{js}\n</script>')
open('wix-embed.html', 'w').write(html)
"
```

Either way, always test `wix-embed.html` by opening it directly in a browser afterward — it should look and behave identically to `index.html`.

---

## Which items require real Showtime pricing before publication

Search `app.js` for `REPLACE SAMPLE VALUES` — it appears directly above `SHOWTIME_CONFIG`, flagging that the entire object below it needs review. Concretely, before publishing:

- [ ] All `dailyRate` values in `inventory`
- [ ] `durationTiers` add-ons
- [ ] `multiDayDiscount` and `multiScreenDiscount` percentages
- [ ] `travel.tiers` flat fees and per-vehicle rates
- [ ] `setup`, `holdDay`, and `crew` values
- [ ] `productionAddons`, `audioOptions`, `powerOptions`, `connectivityOptions`, `venueAccessOptions` values
- [ ] `company.email` and `company.phone`
- [ ] `quotePageUrl` (must point to the real, published Wix quote page)
- [ ] `startingLocation` (if Showtime's home base is not Kansas City)

Nothing else in the tool needs to change to go live — the layout, validation, recommendation logic, and Wix integration all work with the sample data as-is.

---

## What this tool intentionally does not do

- It does not calculate real driving mileage from a ZIP code. ZIP code is collected as a lead field only; pricing by distance uses the manual mile-range selector, because an accurate mileage figure would require a live mapping API, which is out of scope for a dependency-free, client-side tool.
- It does not send email itself. "Email Me This Estimate" opens the customer's own email client via a `mailto:` link — there is no backend or email service involved.
- It is never presented as a confirmed reservation or a guaranteed final price. Every estimate screen and the lead-capture modal both state this explicitly, and pricing is always shown as a range.
