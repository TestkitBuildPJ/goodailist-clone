# 34 — Style tokens (Font pairings, color psychology, VN typography)

> Port of **VIBECODE-MASTER-v5.txt** Phụ Lục B (Font Pairing) and Phụ Lục C
> (Color Psychology), plus Vietnamese-first typography & layout rules
> for the kit's primary market.  Both Vision (`/vibe-vision`) and UI design
> (`/vibe-rri-ui`) consult this file when a project type is detected; the
> lists are stable and machine-readable
> (`methodology.FONT_PAIRINGS` / `methodology.COLOR_PSYCHOLOGY`).
>
> **Copy / messaging patterns are in `references/36-copy-patterns.md`** —
> §B/C (this file) ≠ §D (that file).
>
> Do not renumber existing IDs; add new entries with the next free numeric ID.

## 1. Six canonical font pairings (FP-01..FP-06)

| ID | Mood | Heading | Body | When to pick |
|---|---|---|---|---|
| FP-01 | **Modern Tech**     | Plus Jakarta Sans     | Inter             | SaaS dashboards, dev-tools, AI products |
| FP-02 | **Professional**    | DM Sans               | Source Sans Pro   | B2B, fintech, enterprise admin |
| FP-03 | **Creative**        | Playfair Display      | Lato              | Editorial, agency, portfolio |
| FP-04 | **Friendly**        | Poppins               | Open Sans         | Consumer apps, education, e-commerce mass market |
| FP-05 | **Elegant**         | Cormorant Garamond    | Montserrat        | Luxury, hospitality, premium services |
| FP-06 | **Startup**         | Space Grotesk         | Work Sans         | Y-Combinator-style landing, indie SaaS |

All pairings ship as Google Fonts; loading via Next.js `next/font/google`
or Tailwind `font-family` extension takes 2 lines of config.

## 2. Six canonical color psychologies (CP-01..CP-06)

| ID | Meaning | Primary HEX | Secondary cue | When to pick |
|---|---|---|---|---|
| CP-01 | **Trust / Professional** | `#2563EB` (blue-600)  | low-saturation gray | finance, legal, healthcare, B2B SaaS |
| CP-02 | **Energy / Action**      | `#F97316` (orange-500) | warm yellow accents | call-to-action heavy landing, fitness, food delivery |
| CP-03 | **Growth / Health**      | `#22C55E` (green-500) | mint, sage neutrals | health-tech, ESG, plant-based, eco |
| CP-04 | **Luxury / Premium**     | `#7C3AED` (violet-600) | deep navy + gold accent | premium SaaS, jewelry, hospitality |
| CP-05 | **Warning / Urgency**    | `#EF4444` (red-500)   | dark crimson | dashboards with alerts, compliance, security |
| CP-06 | **Neutral / Modern**     | `#6B7280` (gray-500)  | white + black accents | docs sites, design systems, b2b admin |

Use **one primary** + **one accent from a different row** as the canonical
pair (e.g. CP-01 primary + CP-02 accent for a "trustworthy but energetic"
fintech).  Anti-pattern: 3+ saturated primaries on one page.

## 3. Vietnamese-first typography & layout rules (VN-01..VN-12)

The Vietnamese market is the kit's primary user base; Vietnamese is a
diacritic-rich Latin script that breaks several Western typography
conventions.  These rules are mandatory for any UI that ships in
`vi`; they are recommended (but not required) for `en`.

### 3a. Type scale & line-height

| ID    | Rule                                                                                                                                | Why |
|-------|--------------------------------------------------------------------------------------------------------------------------------------|-----|
| VN-01 | Body line-height ≥ **1.6** (vs the typical English 1.4–1.5).                                                                         | Diacritics like `ằ`, `ặ`, `ậ` extend ~25% above the cap-height; tight leading collides them with the next line's ascenders. |
| VN-02 | Heading line-height ≥ **1.2**, never < 1.15 even on huge display type.                                                               | Same diacritic-collision risk applies to `Ư`, `Ơ`, `Đ`. |
| VN-03 | Body font-size **≥ 16 px** desktop, ≥ 15 px mobile.  ≤ 14 px only for table dense data.                                              | Small Vietnamese text loses diacritic legibility before the same English text does. |
| VN-04 | `letter-spacing` **0** for body; **-0.01em..0** for headings.  Never positive on body.                                               | Positive tracking widens the gap between accented characters and their bases. |

### 3b. Font selection for Vietnamese

| ID    | Rule                                                                                                                                | Why |
|-------|--------------------------------------------------------------------------------------------------------------------------------------|-----|
| VN-05 | Pick fonts with **explicit Vietnamese subset** support (Inter, Plus Jakarta Sans, DM Sans, Be Vietnam Pro, IBM Plex Sans). Avoid italic-only display fonts. | Many Google Fonts render placeholder dotted-circle for `ặ`, `ẵ`, `ỡ`, `ự`. |
| VN-06 | When using `next/font/google`, declare `subsets: ['latin', 'vietnamese']`.                                                            | Default `'latin'` only loads Western diacritics; Vietnamese-specific compositions fall back to system. |
| VN-07 | Self-host `Be Vietnam Pro` as the canonical fallback for any pairing whose heading face has missing Vietnamese glyphs.                | Network-independent, free, designed for Vietnamese. |
| VN-08 | Block `font-variant-ligatures: discretionary-ligatures`.                                                                              | Some discretionary ligatures merge `oa`/`ie`/`uo` and break Vietnamese reading. |

### 3c. Layout rules

| ID    | Rule                                                                                                                                | Why |
|-------|--------------------------------------------------------------------------------------------------------------------------------------|-----|
| VN-09 | Body text container max-width **65–75 ch** (Vietnamese reads slightly faster than English at the same point size; ≥ 75 ch causes saccade fatigue). | Optimal Vietnamese line length is ~10 words per line. |
| VN-10 | Allow **15–20% extra vertical rhythm** (margin/padding) compared to an English equivalent.                                            | Diacritic collision + 1.6 leading make tighter rhythms feel cramped. |
| VN-11 | Buttons / chips: padding `0.6em 1.2em` minimum; height ≥ 40 px on touch.  Never use `text-transform: uppercase` on Vietnamese.      | Uppercase Vietnamese drops the diacritic distinction (`HỌC` vs `HOC`). |
| VN-12 | Forms: label above input, never inline placeholder-as-label.  Help/error text 12–13 px **with** Vietnamese subset enabled.            | Inline placeholder + Vietnamese input collide on focus/blur transitions. |

## 4. Programmatic access

```python
from vibecodekit.methodology import (
    FONT_PAIRINGS, COLOR_PSYCHOLOGY, lookup_style_token
)

# All canonical lists
print(FONT_PAIRINGS["FP-01"])     # ("Plus Jakarta Sans", "Inter", "Modern Tech")
print(COLOR_PSYCHOLOGY["CP-01"])  # ("Trust/Professional", "#2563EB")

# Lookup by ID
lookup_style_token("FP-03")  # → font-pairing dict
lookup_style_token("CP-04")  # → color-psychology dict
lookup_style_token("CF-04")  # → copy-pattern dict (passes through to ref-36)
```

## 5. Cross-reference with Vision template

When `/vibe-vision` proposes a stack the contractor **must** also pick:

- one `FP-*` font pairing (and verify it satisfies VN-05..VN-08 if the
  product ships in Vietnamese)
- one `CP-*` primary color (and optionally a `CP-*` accent from a
  different row)
- defer `CF-*` copy patterns (see `references/36-copy-patterns.md`) to
  the copy-iteration step
- apply VN-01..VN-12 layout rules to every Vietnamese-facing surface

Conformance probe `46_style_tokens_canonical` (added in v0.11.1) verifies
both the markdown list and the methodology constants stay in sync — drift
between this file and `methodology.py` blocks the release gate.
