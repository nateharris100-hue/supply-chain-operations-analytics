# Tableau Build Guide

How each dashboard in `tableau/Supply Chain Operations Analytics.twbx` was
built, sheet by sheet. Build Page 1 exactly as written here, lock the layout,
then clone it for Pages 2–4.

**Visual target:** the Supplier Performance mockup built from this exact dataset.
Match it; don't redesign while building.

---

## 1. Connect the data

1. Tableau → **Connect → To a File → Text file**
2. Choose `outputs/supply_chain_master.csv` — **this file only.** Do not add the
   other eight CSVs. Adding them recreates the multi-source problem that broke
   the filters in v1.
3. On the Data Source tab, confirm these parsed correctly:
   - `order_date`, `expected_delivery_date`, `actual_delivery_date`,
     `shipment_date`, `actual_arrival_date` → **Date**
   - `is_on_time`, `is_late`, `is_delivered`, `below_reorder_point`,
     `is_single_source` → **Number (whole)**
   - `order_month` → **Date**
4. `is_on_time` is **null** for orders not yet delivered. That is deliberate —
   an undelivered order is not a late order. Every rate below divides by
   `is_delivered`, never by the row count.
5. Switch the connection to **Extract** (radio button, top right). Live-querying
   a CSV is slow, and Tableau Public requires an extract anyway.

---

## 2. Calculated fields

Create all of these before building any sheet. `Analysis → Create Calculated Field`.

### Core measures

```
// On-Time Rate
IF SUM([Is Delivered]) = 0 THEN NULL
ELSE SUM([Is On Time]) / SUM([Is Delivered])
END
```
Format as Percentage, 1 decimal.

```
// Total Spend
SUM([Order Cost])
```

```
// Avg Cycle Time
AVG([Total Cycle Time])
```

```
// Avg Lead Time
AVG([Promised Lead Time Days])
```

```
// Freight % of Spend
SUM([Shipping Cost]) / SUM([Order Cost])
```

```
// Cost Variance %
SUM([Cost Variance]) / SUM([Planned Cost])
```

```
// Supplier Spend Share
SUM([Order Cost]) / TOTAL(SUM([Order Cost]))
```

### Table calculations (these need Compute Using set — see §6)

```
// Running Spend %   — drives the Pareto line on Page 4
RUNNING_SUM([Supplier Spend Share])
```

```
// Median OTD
WINDOW_MEDIAN([On-Time Rate])
```

```
// Median Lead Time
WINDOW_MEDIAN([Avg Lead Time])
```

```
// Danger Flag   — the red/blue split on the scatter
[On-Time Rate] < [Median OTD] AND [Avg Lead Time] >= [Median Lead Time]
```

### KPI delta labels

Tableau has no built-in "vs target" caption, so build each as a string. Put it
on the Text shelf under the big number.

```
// On-Time Delta
"▼ " + STR(ROUND((0.90 - [On-Time Rate]) * 100, 1)) + " pts vs 90% target"
```

```
// Cycle Time Delta
"▲ " + STR(ROUND([Avg Cycle Time] - 21, 1)) + " d vs 21-day target"
```

Expected values on the full dataset: on-time **84.3%**, cycle **25.0 d**,
quality **3.43**, spend **$56.5M**, freight **3.40%**, cost variance **+0.90%**.
If your numbers differ, something is filtered or double-counted — stop and find
it before building further.

---

## 3. Build ONE KPI card, then duplicate it

This is the step worth doing slowly. There are 16 KPI cards across four
dashboards; build the template once.

A card is **two worksheets** side by side in a horizontal container.

**Sheet `KPI – On Time`** (the number)
1. Drag **On-Time Rate** to **Text**.
2. Drag **On-Time Delta** to **Text** as well.
3. Click Text → Edit Label. Put the rate on its own line at **30pt semibold**,
   the delta beneath at **11pt**, colored red (`#C0392B`).
4. Marks card → Text. Rows and Columns stay empty.
5. Format → Borders → remove all. Format → Shading → None.

**Sheet `Spark – On Time`** (the sparkline)
1. **order_month** → Columns. Right-click it → **Continuous** (green pill).
2. **On-Time Rate** → Rows.
3. Marks type → **Line**, size one notch above minimum.
4. Right-click the Y axis → Edit Axis → uncheck **Include zero**. A sparkline
   forced to zero shows no variation.
5. Right-click each axis → uncheck **Show Header**.
6. Format → Lines → Grid Lines **None**, Zero Lines **None**, Axis Rulers **None**.
7. Analytics pane → **Reference Line** → Constant `0.90` → dashed, grey, no label.
8. Size the sheet to roughly 130 × 30 px in the dashboard container.

**Assemble:** horizontal container → text object for the metric name (12pt
semibold) and its italic definition (11.5pt grey) stacked above, number sheet
left, sparkline sheet right. Set container background white, add a 1px
`#DFE5EA` border.

Then **duplicate the container** for the other three KPIs and swap the measure.
Do not build each from scratch — they will not line up.

---

## 4. The four worksheets on Page 1

### Sheet 1 — `Scatter – Supplier Risk`
*"Which suppliers could break us?"*

- **Columns:** `Avg Lead Time` · **Rows:** `On-Time Rate`
- **Detail:** `supplier_name` (this sets the mark grain to one dot per supplier)
- **Size:** `SUM(order_cost)` · **Color:** `Danger Flag`
  (True → `#C0392B`, False → `#3A6A99`, both at ~45% opacity, 1.5px border)
- **Filter:** create `Orders Delivered = SUM([Is Delivered])`, drag to Filters,
  set **At least 20**. Suppliers with a handful of orders produce meaningless
  100% and 0% rates. Say this out loud in an interview — it's a judgment call,
  not a technicality.
- **Reference lines:** Analytics → Reference Line → Table → Median, for both
  axes. Label → **Value**. These produce the two dashed quadrant lines.
  (The scatter's own reference lines compute the median across marks, so you do
  not need the `Median OTD` calc here — that one is only for `Danger Flag`.)
- **Tooltip:** supplier, on-time %, lead time, spend, order count, quality.
- Annotate the two material danger cases (Shenzhen, Penang) directly on the
  chart: right-click mark → Annotate → Mark.

### Sheet 2 — `Trend – Top 5 On Time`
*"One of our largest suppliers is failing in slow motion"*

- **Columns:** `order_date` → **Quarter**, continuous
- **Rows:** `On-Time Rate` · **Color:** `supplier_name`
- **Filter:** `supplier_name` → Top 5 by `SUM(order_cost)`
- **Color is the whole point here.** Set the four healthy suppliers to the same
  grey (`#B3BEC8`) and Shenzhen Precision Mfg to red (`#C0392B`), and make the
  red line thicker. Five categorical hues would make this a spaghetti chart
  where every line competes. One red line against four grey ones states the
  finding without a legend.
- Reference line at `0.90`, dashed, labeled "Target 90%".
- Label the last point of each line (Label → Line Ends → Label end of line).

### Sheet 3 — `Bars – Supplier Ranking`
*"Reliability and spend don't line up"*

- **Rows:** `supplier_name`, sorted descending by `On-Time Rate`
- **Columns:** `On-Time Rate`
- **Color:** `[On-Time Rate] < [Median OTD]` → red when true, blue when false
- Same **at least 20 delivered orders** filter as Sheet 1
- Reference line at the median, dashed
- Label each bar with its value at the end

### Sheet 4 — `Table – Top Suppliers`
*"Where the money actually goes"*

- **Rows:** `supplier_name` (top 10 by `SUM(order_cost)`)
- **Columns (Measure Values):** orders, On-Time Rate, Avg Lead Time, quality,
  Total Spend
- On the spend column, Analytics → **Bar in Table** (or set the Marks type to Bar
  for that measure) to get in-cell data bars
- Add a flag column:

```
// Risk Flag
IF [On-Time Rate] < [Median OTD] AND SUM([Order Cost]) > 2000000
THEN "Material reliability risk"
ELSEIF [On-Time Rate] < [Median OTD] THEN "Below median on-time"
ELSEIF [Avg Lead Time] > 32 THEN "Long lead time"
ELSE "" END
```

---

## 5. Dashboard assembly

1. New Dashboard, size **Automatic** (not Fixed — fixed breaks on other screens).
2. Top strip: horizontal container with a text object for the title and the
   italic question subtitle on the left, `Data as of 30 Sep 2026 · 3,175 orders`
   on the right in 11.5pt uppercase grey.
3. KPI row: horizontal container, four KPI containers, even spacing.
4. Body: horizontal container with Scatter (≈55% width) and Trend (≈45%).
5. Full-width Bars, then full-width Table.
6. Every chart title goes in a **text object**, not the worksheet title — you
   need two lines with different styling (serif question, italic grey subtitle)
   and the worksheet title field fights you on that.

### Global filters — the step that fixes v1

1. Drag `order_date`, `supplier_name`, `category`, `shipping_mode` onto the
   dashboard as filters.
2. For **each one**: right-click → **Apply to Worksheets → All Using This Data
   Source.**
3. Test: change the supplier filter and confirm **all four** panels move. If one
   doesn't, that sheet is on a different data source — go back to §1.

---

## 6. Gotchas that will cost you an hour each

**Table calcs need a direction.** `WINDOW_MEDIAN` and `RUNNING_SUM` default to
computing across whatever Tableau guesses. Right-click the pill → **Compute
Using → Supplier Name** (or **Specific Dimensions** and tick only supplier). If
`Median OTD` returns the same value as each supplier's own rate, Compute Using is
wrong — it's partitioning per supplier instead of across them.

**Filters and table calcs fight.** A normal filter runs *before* table calcs, so
filtering suppliers changes the median and repaints the colors. If you want the
median fixed to the full supplier set, make the filter a **Context Filter**
(right-click → Add to Context) or switch to a FIXED LOD.

**Don't divide by COUNT.** `SUM([Is On Time]) / COUNT([Order Id])` counts
not-yet-delivered orders as failures and will understate on-time by ~2 points.
Always divide by `SUM([Is Delivered])`.

**Sparklines need "Include zero" off**, or every one looks flat.

**Tableau Public is public.** Anything you publish there is visible to anyone and
indexed. That's fine for this project — it's a portfolio piece — but never put
real employer data there.

**Test the filters after publishing, not before.** Published workbooks handle
filter scope differently from Desktop. This is the specific thing that broke in
v1, so verify it on the live link.

---

## 7. Phase 2 checklist

- [ ] CSV connected as the single source, switched to Extract
- [ ] All 13 calculated fields created
- [ ] Headline numbers match §2 (84.3% / 25.0d / 3.43 / $56.5M)
- [ ] One KPI card built to final spec and duplicated, not rebuilt
- [ ] Four worksheets built
- [ ] Page 1 assembled and layout locked
- [ ] All four global filters set to "All Using This Data Source" and tested
- [ ] Pages 2–4 cloned from Page 1's containers

---

# Appendix — Build log, from actually doing it in Tableau Public

Written after building Page 1. These are corrections and gotchas found in the
app, not in theory. Where this appendix disagrees with the sections above,
**this appendix is right.**

## Saving: Tableau Public can't save a normal local workbook

In Tableau **Public**, `File → Save` and `File → Save As…` are **greyed out**.
Your only options are:

- **`File → Export Packaged Workbook…`** → saves a local `.twbx`. **Use this.**
- `File → Save to Tableau Public…` (⌘S) / `Save to Tableau Public As…` (⇧⌘S) →
  **publishes to the public web.** Anyone can find it.

⚠️ **Do not reflex-press ⌘S or ⇧⌘S in Tableau Public.** In Tableau Desktop those
are local saves; here they publish. Build locally with Export Packaged Workbook,
and publish deliberately at the end when the work is ready to be seen.

Current file: `supply_chain_dashboard.twbx` in this folder.

## Adding fields: double-click beats dragging

Dragging onto the small Marks-card buttons (Color, Size, Detail) is unreliable.
What works:

- **Double-click a field in the Data pane** — Tableau adds it to the view and
  picks a sensible shelf. This is the fastest, most reliable way.
- **Drag onto the Marks card body** (not the buttons) — a measure dropped there
  lands on **Size**.
- Dragging to **Columns / Rows / Filters** works normally; they're big targets.
- To move a field to a different shelf afterwards, right-click its pill.

## Mark type order matters

With mark type **Automatic**, dropping `Danger Flag` puts it on **Shape**
(circles vs squares), not Color. Then switching the mark type to Circle
**removes the field entirely**, because Shape no longer exists.

Correct order:
1. Set mark type to **Circle** first.
2. *Then* double-click `Danger Flag` — it lands on **Color**.

If you end up with two `Danger Flag` pills (one Detail, one Color), right-click
the Detail one → **Remove**.

## Compute Using is mandatory, not optional

Straight after putting `Danger Flag` on Color, the legend showed **only False** —
every supplier looked healthy. The table calc was partitioning per-supplier, so
each supplier's rate was being compared to its own median.

Fix: right-click the `Danger Flag` pill → **Compute Using → Supplier Name**.
True/False both appear immediately.

Same applies to `Median OTD`, `Median Lead Time` and `Running Spend Pct`
wherever they're used. **If a table calc looks wrong, check Compute Using first.**

## The on-time axis must not include zero

By default the axis ran 0.0–0.95 and squashed every mark into the top third.
Right-click the axis → **Edit Axis…** → untick **Include zero**. The axis then
runs ~0.60–0.95 and the quadrants become readable.

## Reference lines

Right-click axis → **Add Reference Line** → set the aggregation dropdown from
Average to **Median**, and set **Label → Value** so the number prints on the line.
Do it on both axes.

## Verified figures (cross-checks)

Tableau computed these independently of the Python analysis, and they match:

| Figure | Value |
|---|---|
| Marks after the 20+ delivered-orders filter | **27 suppliers** |
| Median on-time reference line | **0.8466** |
| Median lead time reference line | **26.03 days** |
| Suppliers flagged in the danger quadrant | **7** |

If your numbers differ from these, something is filtered differently — find it
before building further.

## Field names as actually created

`%` was avoided in field names. The real names are:

- `Freight Pct of Spend` (not "Freight % of Spend")
- `Cost Variance Rate` (not "Cost Variance %")
- `Running Spend Pct` (not "Running Spend %")
- `Is Delivered` — a **calculated field**, not a CSV column:
  `IF NOT ISNULL([Actual Delivery Date]) THEN 1 ELSE 0 END`
  Tableau caches a text file's schema, and `Data → Refresh Data Source` does
  **not** pick up columns added to the CSV afterwards. To get genuinely new
  columns you have to recreate the connection.

`Supplier Spend Share` pops a **Default Table Calculation** dialog on save
because of `TOTAL()`. Accept **Automatic**.

## Status

- [x] Data source connected, 3,175 rows
- [x] All 16 calculated fields created and validated
- [x] Sheet **Supplier Risk Scatter** complete: quadrant medians, spend-sized
      bubbles, red/blue danger split, 20+ order filter
- [ ] KPI cards
- [ ] Trend / ranked bars / detail table sheets
- [ ] Dashboard assembly and global filters
- [ ] Pages 2–4

---

# Appendix B — KPI cards, the working recipe

Tableau has no "big number" card type; you build one as a worksheet whose only
content is text. The reliable sequence, found by doing it four times:

1. **New worksheet.**
2. **Drag the measure onto the Marks card body** (the empty area, not a button).
   It lands on **Detail**.
3. **Slow-drag that pill onto the Text button.** This is the key move:
   *pill-to-button* drags work, while *data-pane-to-button* drags do not. Press,
   move through 3–4 intermediate points, hover ~2s on the button, release.
4. Repeat 2–3 for the delta field, if the KPI has one.
5. Toolbar fit dropdown → **Entire View** (otherwise the text shows as `####`).
6. Marks → **Text** → the **…** button → Edit Label.
7. The label lists fields in the order Tableau chose, which is usually the delta
   first. **Select all and retype the tokens in the order you want** —
   `<AGG(On-Time Rate)>` newline `<AGG(On-Time Delta)>`. Typed tokens resolve
   correctly as long as the field name is exact.
8. Triple-click the value line, set the font size box to **28**, press Return
   (Return also closes the dialog).

## Number formats — set them as field defaults, not per-sheet

Right-click the field in the Data pane → **Default Properties → Number Format**.
Doing it here applies everywhere at once — the KPI card, the scatter axis, the
trend axis, the reference-line labels. Set:

- `On-Time Rate` → **Percentage**, 1 decimal → `84.3%`
- `Total Spend` → **Currency (Custom)**, 1 decimal, Display Units **Millions** → `$56.5M`

Setting these turned every axis in the workbook from `0.8433` into `84.3%` in
one action.

## Building the KPI row on the dashboard

Drop the first KPI sheet at the very **top edge** of the canvas — it becomes a
full-width row. Drop each following one on the **right-hand portion of that row**
to split it. If one lands as a full-height column down the side instead, grab its
**move handle** (the grip at the top-centre of the selected panel) and drag it
into the row.

**Don't shrink the KPI row too far.** At 28pt, squeezing the row height makes
every card render as `########`. Undo (⌘Z) restores it.

## Watch the tab bar positions

The worksheet tab strip shifts as sheet names get longer, and the three small
icons at its right are **New Worksheet / New Dashboard / New Story**. Clicking
from a remembered coordinate created a stray dashboard. Right-click the unwanted
tab → **Delete** to remove it.

## Status

- [x] Data source, 16 calculated fields
- [x] **Supplier Risk Scatter** — quadrant medians, spend-sized bubbles, red danger split
- [x] **Supplier On-Time Trend** — Shenzhen red vs other top-5 grey, 90% target line
- [x] **Supplier Ranking** — 27 suppliers sorted, red below the median
- [x] **KPI On-Time / Cycle Time / Total Spend / Quality**
- [x] **Supplier Performance** dashboard — KPI row, two charts, ranking, global Category filter
- [x] Global filter verified: clearing it empties all panels; one category repopulates
      them and *recomputes* the median reference lines
- [ ] Polish: `Avg Quality Score` and `Avg Cycle Time` could use 1-decimal defaults
      (`24.98` → `25.0`); the scatter panel is cramped and wants more height
- [ ] Pages 2–4 (Shipping & Logistics, Inventory Health, Cost & Risk)
- [ ] Story assembly and publish

---

## Appendix C — Page 2 build log (Shipping & Logistics)

**Status: COMPLETE.** Saved in `supply_chain_dashboard.twbx` (471 KB, 12 worksheets,
2 dashboards).

### Sheets built

| Sheet | Shelves | Result |
|---|---|---|
| `KPI Transit Days` | `Avg Transit Days` on Text, 28pt | **10.8 d** |
| `KPI Freight Pct` | `Freight Pct of Spend` on Text, 28pt | **3.4%** |
| `KPI Freight Total` | `Total Freight` on Text, 28pt | **$1.9M** |
| `Shipping Cost vs Speed` | Cols `Avg Transit Days`, Rows `Freight Pct of Spend`, mark Circle, Color `Shipping Mode`, Size `Total Freight` | 4 marks tracing the speed/cost curve |
| `Mode Reliability` | Rows `Shipping Mode`, Cols `On-Time Rate`, sorted desc, labels on, fit **Entire View** | overnight 90.4 · express 88.3 · standard 84.8 · economy 75.8 |

New calculated fields: `Avg Transit Days = AVG([Days In Transit])`,
`Total Freight = SUM([Shipping Cost])`.

Field-default number formats set: `Total Freight` → Currency (Custom), 1 dp,
Display Units **Millions** (`$1.9M`); `Avg Transit Days` → Number (Custom), 1 dp
(`10.83` → `10.8`).

### What the page shows

Reliability ranks **exactly** with speed and with freight cost — overnight is both
the fastest and the most reliable, economy is slowest, cheapest and least reliable
(75.8%, a 14.6-point gap to overnight). Express is the biggest bubble ($852K of
freight), so the largest single lever is express → standard on shipments where the
8–16 day window is acceptable: standard still lands 84.8% on time at 2.4% of spend
vs express's 3.9%.

### Dashboard layout — the ordering rule (important)

Tableau only offers drop zones *inside the pane under the cursor*. There is no
outer "add a full-width band" zone once the dashboard holds more than one pane.
So **build the rows first, then split each row into columns**:

1. Drop the first sheet on the empty dashboard (it fills everything).
2. Drop the second sheet on the **bottom half** of it → full-width row 2.
3. Only now drop the remaining sheets on the **right half** of whichever row
   they belong to.

Doing it the other way (KPI row first, charts after) is what failed: the charts
could only land inside one KPI column, and dragging the divider afterwards
resized a single column instead of the whole row.

Two independent dividers end up controlling the row heights (one per column
group); drag **both** to the same y to make the grid line up.

### Cross-filter verification (the whole point of the rebuild)

`Category` was re-added on `Supplier Ranking` and scoped **Apply to Worksheets →
All Using This Data Source**, then surfaced on both dashboards.

Filtering to **Electronics only** moved every pane on Page 2 at once:

| | All categories | Electronics only |
|---|---|---|
| Avg transit | 10.8 d | 9.1 d |
| Freight % of spend | 3.4% | 3.3% |
| Total freight | $1.9M | $0.3M |
| Best-on-time mode | overnight 90.4% | **standard 91.0%** |

The mode ranking *re-orders* under the filter — standard overtakes express and
overnight inside Electronics. That is the behaviour the 8-CSV version could not
produce, and it is the single best thing to demo in an interview.

### Gotchas hit on Page 2

- Dropping a field onto the Filters shelf **on top of an existing pill replaces
  it**. This silently removed the global `Category` filter from every sheet that
  carried it. Always drop into empty space below the last pill.
- `Shipping Mode` carried a `Null` member into the scatter's colour legend and a
  "1 null" badge. Fixed with a `Shipping Mode` filter excluding Null.
- A bar chart dropped on a dashboard keeps its worksheet fit (`Standard`), so the
  bars hugged the top third of the pane. Select the pane → toolbar fit dropdown →
  **Entire View**.
- Clicking into the Claude app mid-build drops Tableau out of frontmost and the
  next click lands on the wrong menu item; re-focus Tableau first.

### Still open

- [ ] Boolean field aliases on Page 1 still read `Danger Flag: False/True`
- [ ] 1-decimal defaults for `Avg Cycle Time` (24.98 → 25.0) and `Avg Quality Score`
- [ ] Page 1 scatter wants more height
- [ ] Pages 3–4 (Inventory Health, Cost & Risk)
- [ ] Story assembly and publish

---

## Appendix D — Page 3 build log (Inventory Health)

**Status: COMPLETE.** `supply_chain_dashboard.twbx` is now 781 KB — 20 worksheets,
3 dashboards, 1 data source.

### The de-duplication layer (the important part)

Inventory columns are *product-grain* attributes repeated on every order row. A
naive `SUM([Inventory Value At Hand])` returns **$290.5M instead of $5.36M —
overstated 54×** (one row per order, ~59 orders per SKU).

Everything on this page routes through an anchor-row flag:

```
Is SKU Row = [Order Id] = { FIXED [Product Id] : MIN([Order Id]) }

Inventory Value     = SUM(IF [Is SKU Row] THEN [Inventory Value At Hand] END)
SKU Count           = SUM(IF [Is SKU Row] THEN 1 ELSE 0 END)
Available Units     = SUM(IF [Is SKU Row] THEN [Available Qty] END)
SKUs Below Reorder  = SUM(IF [Is SKU Row] AND [Below Reorder Point] = 1 THEN 1 ELSE 0 END)
Capital in Overstock= SUM(IF [Is SKU Row] AND [Coverage Ratio] >= 3 THEN [Inventory Value At Hand] END)
```

Date-range-safe turnover (no hardcoded "24 months"):

```
Months In View     = DATEDIFF('month', MIN([Order Date]), MAX([Order Date])) + 1
Annualized COGS    = SUM([Order Cost]) * 12 / [Months In View]
Inventory Turnover = [Annualized COGS] / [Inventory Value]
Days of Supply     = 365 / [Inventory Turnover]
```

Health band, and the Pareto cumulative (Compute Using → Product Name):

```
Stock Status = IF [Available Qty] <= 0 THEN "1 Stockout"
  ELSEIF [Coverage Ratio] < 0.5 THEN "2 Critical"
  ELSEIF [Coverage Ratio] < 1   THEN "3 Below reorder"
  ELSEIF [Coverage Ratio] < 3   THEN "4 Adequate"
  ELSE "5 Overstocked" END

Running Inv Value Pct = RUNNING_SUM([Inventory Value]) / TOTAL([Inventory Value])
```

### Verified figures (all cross-checked against the CSV in Python first)

| | Value |
|---|---|
| Inventory value | **$5.4M** (exact: 5,361,229) |
| Inventory turnover | **5.27x** |
| Days of supply | **69 d** |
| SKUs below reorder | **12** |
| SKU count | 54 |
| 80% of capital reached at | the **13th SKU of 54** (24%) |
| Top 20% of SKUs carry | 77.9% of value |

### The finding

**76% of inventory capital ($4.06M) sits in 15 overstocked SKUs; the 12 SKUs
actually below reorder hold 3.3% ($177K).** The sharpest pair: Barcode Scanner is
#3 by demand at **0.15× coverage** (2 days of supply) while HDD 8TB is #7 by
demand at **10.2× coverage** and $342K sitting still. Electronics alone is $3.03M
— 57% of all inventory capital — with 5 of its 8 SKUs overstocked.

### Colour scheme

Red → orange → blue → yellow for Critical → Below reorder → Adequate → Overstocked.
This is a **diverging** scale (too little / about right / too much), not a severity
ramp, and it reads better than a monotonic ramp because overstock is also a problem.

### Cross-filter verification

Filtering to **Electronics only** moves all six panes together:

| | All | Electronics |
|---|---|---|
| Inventory value | $5.4M | **$3.0M** |
| Turnover | 5.27x | **1.59x** |
| Days of supply | 69 d | **230 d** |
| SKUs below reorder | 12 | **2** |
| Action list | 12 rows | Power Supply Unit 0.36x, Audio Module 0.49x |

Turnover collapsing to 1.59x and days-of-supply blowing out to 230 d inside
Electronics *is* the overstock story, quantified.

### Gotchas hit on Page 3

- **A dimension on Label sets mark granularity.** Swapping `Product Name` for a
  callout field on Label collapsed 54 marks to 9. Fix: `Product Name` on **Detail**,
  callout field on **Label**.
- **Label collisions silently drop pinned labels.** `Mark Label → Always Show` does
  nothing if "Allow labels to overlap other marks" is off and a neighbour's label is
  in the way. The real fix was not more labels but fewer — a `Callout Label` calc
  that returns a name for only four SKUs, then overlap on. A scatter with 54 labels
  is noise; four deliberate callouts are an argument.
- **Changing a field's Default Properties → Aggregation does not change pills
  already on a shelf.** Remove the pill and re-add it.
- **A mis-aimed drag onto the view created a phantom `Dropped_<timestamp>` data
  source.** Right-click it → Close (safe while no sheet uses it as primary).
- Right-clicking a mark gives a tooltip, not a menu, unless the mark is already
  selected — left-click first, confirm via the status bar ("1 of 54 marks"), then
  right-click.
- Removing a leftover **Measure Names** legend: select the owning sheet on the
  dashboard → caret ▾ → Legends → uncheck. There is no X on the legend itself.

### Still open

- [ ] `Below Median OTD` on Page 1 still shows False/True in the legend
- [ ] Page 4 (Cost & Risk)
- [ ] Story assembly and publish
- [ ] Portfolio README, resume bullet, 90-second walkthrough

---

## Appendix E — Page 4 (Cost & Risk) and the Story

**Status: COMPLETE.** `supply_chain_dashboard.twbx` is 1.09 MB — 27 worksheets,
4 dashboards, 1 story, 1 data source.

### New calculated fields

```
Late Rate          = 1 - [On-Time Rate]
Late Spend         = SUM(IF [Is Late] = 1 THEN [Order Cost] END)
Overspend Dollars  = SUM([Cost Variance])
Meridian Highlight = IF [Supplier Name] = "Meridian Components"
                     THEN "Meridian Components" ELSE "All other suppliers" END
Risk Tier          = IF [Late Rate] >= 0.18 AND [Total Spend] >= 2800000
                       THEN "1 High - large and unreliable"
                     ELSEIF [Late Rate] >= 0.18 THEN "2 Unreliable but small"
                     ELSEIF [Total Spend] >= 2800000 THEN "3 Concentration risk"
                     ELSE "4 Low" END
Supplier Callout   = IF [Supplier Name] = "Shenzhen Precision Mfg" OR … THEN [Supplier Name] END
```

`Cost Variance Rate`, `Total Spend`, `Supplier Spend Share`, `Running Spend Pct`
and `On-Time Rate` were all reused from Page 1 — no duplicates created.

Risk Tier deliberately thresholds on **dollars ($2.8M ≈ 5% of spend)** rather than
`Supplier Spend Share`. Share is a `TOTAL()` table calc; mixing it into an IF would
have made Risk Tier a table calc too and forced a Compute Using on every view it
touches. Dollars keep it a plain aggregate.

### Verified figures

| | Value |
|---|---|
| Total spend | **$56.5M** |
| Cost variance | **+0.90%** |
| Late delivery rate | **15.7%** (479 of 3,056 delivered) |
| Late-delivered spend | **$7.8M** |
| Top-5 concentration | 58.4% · 80% of spend sits with 10 of 30 suppliers |

### The finding

**Meridian Components is $409,762 of the $501,353 total cost variance — 82% of it
from one supplier.** The other 29 combined net only +$91,591. And it is
accelerating, not flat:

| 2024 Q4 | 2025 Q2 | 2025 Q4 | 2026 Q2 | 2026 Q3 |
|---|---|---|---|---|
| −0.28% | +3.07% | +6.88% | +9.14% | **+12.73%** |

The most recent quarter alone cost **+$204,844**. The `Meridian Price Drift` line
chart — red line climbing, grey "all other suppliers" line flat at zero — is the
single best visual in the project.

Second finding, from the risk matrix: the worst late rates (Lakeside 43.8%,
Budget Source 40.0%) belong to suppliers carrying ~0.6% of spend each. The one
that actually matters is **Shenzhen Precision Mfg — 23.5% late on $7.8M**, the
largest real exposure in the book. Late rate alone misleads; it has to be read
against spend.

### Story

`Supply Chain Review` — 4 points, one per dashboard:

1. 84.3% on-time — our #2 supplier is the worst
2. Reliability ranks exactly with speed and cost
3. 76% of capital idle while 12 SKUs run dry
4. One supplier is 82% of all cost variance

### Gotchas hit on Page 4

- **The sheet-tab context menu moves its items.** Some sheets show *Hide* where
  others show *Delete*, which shifts *Duplicate* by one row. A blind click at the
  remembered offset deleted `KPI Cost Variance` (restored by rebuilding it) and
  nearly deleted `KPI Late Rate`. **Screenshot the menu before every click.**
- **Data-pane search results sit at two different heights**: dimensions at full
  y≈221, measures at y≈236. Dragging from the wrong one silently does nothing —
  cost four failed attempts on `Supplier Callout`.
- **The global `Category` filter was still scoped to Electronics** from the Page 3
  cross-filter demo, and had been saved that way. Any new sheet inherited it.
  Reset it to All before building, and check the filter state before every export.
- Tableau offers a drop zone's **top half only in the upper-middle** of a pane —
  hovering at the very top edge targets the whole pane instead.
- `cmd+Z` on a dashboard undoes the last *drop*, not the last *resize*.

### Still open

- [ ] `Below Median OTD` on Page 1 still reads False/True
- [ ] Page 4: Measure Names legend not removed; no Category filter card
- [ ] Publish to Tableau Public
- [ ] Portfolio README, resume bullets, interview talking points, walkthrough script
