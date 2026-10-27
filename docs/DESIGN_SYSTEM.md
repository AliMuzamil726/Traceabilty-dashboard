# SAWIE design system

Calm, spacious, precise. One theme, two brand colours, one error red. Everything here
lives in `frontend/src/design-system/` and `frontend/tailwind.config.ts`.

## 1. Colour

Tailwind's default palette is **replaced**, not extended, so off-brand classes do not
exist. `npm run check:colors` scans the source, the public folder and the built CSS
and fails on any other colour.

| Token | Hex | Tailwind | Use |
| --- | --- | --- | --- |
| Forest 950 | `#0B2418` | `forest-950` | tooltips, overlay scrim (40%) |
| Forest 900 | `#10331F` | `forest-900` | sidebar |
| Forest 800 | `#164A2C` | `forest-800` | pressed, success text |
| Forest 700 | `#1D6039` | `forest-700` | **primary**: buttons, active states |
| Forest 600 | `#25774A` | `forest-600` | progress, completed steps |
| Forest 500 | `#2F915A` | `forest-500` | focus ring |
| Forest 100 | `#E3F1E8` | `forest-100` | info tint |
| Forest 50 | `#F1F8F3` | `forest-50` | hover, success tint |
| Wheat 600 | `#A67C1F` | `wheat-600` | warning icons, required marker |
| Wheat 500 | `#C79A2E` | `wheat-500` | **accent**: active nav indicator, brand leaf |
| Wheat 300 | `#E3C479` | `wheat-300` | accent text on dark |
| Wheat 100 | `#F7EBCB` | `wheat-100` | accent pill, avatar |
| Wheat 50 | `#FBF5E4` | `wheat-50` | warning tint |
| Canvas | `#F5F6F2` | `canvas` | page background |
| Surface | `#FFFFFF` | `surface` | cards, inputs |
| Line | `#E3E6DE` | `line` | borders (structure comes from 1px borders) |
| Muted | `#5B675F` | `muted` | secondary text |
| Ink | `#15221B` | `ink` | text |
| Error | `#B42318` / `#FDECEA` | `danger`, `danger-tint` | validation errors, destructive actions, map overlap warnings only |

Semantic mapping (no new hues): success = forest, warning = wheat, info = forest tint,
neutral = warm grey tint, danger = the error red. Charts use forest, wheat and their tints.

Never put text on Wheat 500 or Wheat 600 backgrounds; wheat is for marks, indicators
and tints. `gray.200` and `gray.400` exist only as aliases of Line and Muted so
Tailwind's base styles stay on brand.

### Contrast (WCAG 2.1 AA, normal text needs 4.5:1)

| Pair | Ratio |
| --- | --- |
| Ink on canvas | 15.16:1 |
| Ink on surface | 16.45:1 |
| Muted on canvas | 5.45:1 |
| Muted on surface | 5.92:1 |
| Muted on Forest 50 | 5.48:1 |
| Forest 700 text on surface | 7.54:1 |
| Success pill (Forest 800 on Forest 50) | 9.49:1 |
| Info pill (Forest 900 on Forest 100) | 11.89:1 |
| Warning pill (Ink on Wheat 50) | 15.11:1 |
| Accent pill (Forest 950 on Wheat 100) | 13.83:1 |
| Error text on surface | 6.57:1 |
| Error pill (red on red tint) | 5.75:1 |
| White on Forest 700 (primary button) | 7.54:1 |
| White on error red (danger button) | 6.57:1 |
| White on Forest 900 (sidebar) | 13.86:1 |
| Sidebar items (Forest 100 at 80% on Forest 900) | 8.16:1 |
| Sidebar captions (Forest 100 at 70% on Forest 900) | 6.62:1 |
| "In build" pill on dark (Wheat 300 on Wheat 500 15% over Forest 900) | 6.53:1 |
| Avatar initials (Forest 900 on Wheat 100) | 11.68:1 |
| Tooltip (white on Forest 950) | 16.41:1 |

Disabled items (Settings) are exempt from contrast rules and also carry `aria-disabled`.

## 2. Typography

* UI: **Inter Variable** (`@fontsource-variable/inter`, self-hosted).
* IDs, coordinates, codes: **JetBrains Mono** (`@fontsource/jetbrains-mono`, 400 and 500), class `mono-id`.
* Tables and KPIs: `tabular` utility (`font-variant-numeric: tabular-nums`).

| Token | Size / line height | Use |
| --- | --- | --- |
| `text-xs` | 12 / 16 | captions, pills |
| `text-sm` | 13 / 18 | labels, hints, table headers |
| `text-base` | 14 / 20 | body, controls |
| `text-md` | 16 / 24 | section titles |
| `text-lg` | 20 / 28 | dialog titles |
| `text-xl` | 24 / 32 | page titles |
| `text-2xl` | 32 / 40 | KPI values |

Sentence case everywhere; no all-caps labels.

## 3. Shape, depth, spacing

* Radius: 8px controls and buttons (`rounded-control`), 10px cards (`rounded-card`), 4px small marks (`rounded-sm`), 999px pills (`rounded-pill` for status only).
* Shadows: `shadow-1` (resting cards) and `shadow-2` (overlays, raised). Borders do most of the work.
* Spacing: Tailwind's 4px grid.
* Focus: 2px Forest 500 outline with 2px offset on every interactive element (`:focus-visible`).

Card padding is 12, 16 and 20px (`sm`, `md`, `lg`). A row of tiles aligns from the top, so
values share a baseline whether or not a tile has a hint line.

### Dashboard composition

* The **pipeline** is one bordered strip divided by hairlines, not seven cards, and has no
  gradient. A stage shows "of the stage before" only when that share is 100 percent or
  less; a larger figure compares unlike things and reads as an error.
* The **key figures** row shows quantities the pipeline does not: fieldbook submission rate,
  fields ready for pickup, delivered weight and mapped area. Farmers, fields, bales and
  scans are counted once, in the pipeline.
* Pages for Modules 3 to 7 are framed by the router with `PageContainer`; Modules 1 and 2
  frame their own pages. The top bar shows the breadcrumb; the page title is the page's own
  heading (the top bar repeats it only on a phone).

## 4. Motion

| Token | Value |
| --- | --- |
| Durations | 120 ms (`fast`), 200 ms (`base`), 320 ms (`slow`) |
| Easing | `cubic-bezier(.2,.8,.2,1)` |
| Page transition | fade + 8px rise (`pageVariants`, used by `PageContainer`) |
| Lists | 30 ms stagger, capped at 8 items (`listItemVariants`, `staggerDelay`) |
| Buttons | press scale 0.98 (`motion-safe:active:scale-[.98]`) |
| Sidebar | width animates between 264px and the 76px rail |
| Loading | skeleton shimmer (off under reduced motion) |
| Success | short check-draw (`CheckDraw`) |

No looping decorative animation. The app is wrapped in `MotionConfig reducedMotion="user"`.

## 5. Components

Import from `@/design-system/components`. All are typed, keyboard accessible and
pick up `id`, `aria-describedby`, `aria-invalid` and `required` from a surrounding `FormField`.

| Component | Key props | Notes |
| --- | --- | --- |
| `Button` | `variant` primary, secondary, ghost, danger; `size` sm, md, lg; `loading`; `leftIcon`, `rightIcon`; `fullWidth` | `buttonClasses()` styles links as buttons |
| `IconButton` | `label` (required, also tooltip), `icon`, `size`, `variant` ghost, secondary, onDark | |
| `Input` | `invalid`, `leadingIcon`, `suffix`, `mono` | |
| `NumberInput` | `value`, `onValueChange(number or null)`, `unit`, `decimals` | right-aligned tabular numbers |
| `Textarea` | `invalid`, `rows` | |
| `Select` | `options` (from master lists), `placeholder` | native select for best accessibility |
| `Combobox` | `value`, `onChange`, `options` or async `loadOptions(query, signal)`, `selectedLabel` | ARIA combobox with `aria-activedescendant`, debounced |
| `DatePicker` | `value` (ISO date or null), `onValueChange`, `min`, `max` | native date input, localised calendar |
| `SegmentedControl` | `value`, `onChange`, `options`, `aria-label` | radiogroup, arrow keys |
| `ChoiceCards` | `value`, `onChange`, `options` (title, description, icon), `columns` | radio cards (e.g. tenure) |
| `FormField` | `label`, `hint`, `error`, `required`, `hideLabel` | error replaces hint and is announced |
| `Card`, `SectionHeader` | `padding`, `elevated`; `title`, `description`, `actions` | |
| `PageHeader`, `Breadcrumb` | `title`, `subtitle`, `actions`, `breadcrumb` | |
| `StatCard` | `label`, `value`, `hint`, `icon`, `loading` | skeleton state built in |
| `Badge`, `StatusPill`, `StatusPillOnDark` | `tone` success, warning, info, neutral, danger, accent | |
| `DataTable` | `columns` (sortable, numeric, mono), `rows`, `rowKey`, `caption`, `loading`, `empty`, `sort`, `pagination`, `selectable` | sticky header, `aria-sort`, page contract built in |
| `Dialog`, `Drawer` | `open`, `onClose`, `title`, `footer`; drawer `side` | focus trap, Escape, focus restore, portal |
| `ConfirmDialog` | `confirmLabel` names the action, `destructive`, `loading` | `alertdialog` |
| `Stepper` | `steps`, `current`, `orientation`, `onStepClick` | |
| `Tabs` | `value`, `onChange`, `items` (count), render-prop panel | WAI-ARIA tabs |
| `Tooltip` | `content`, `side` | hover and focus, `aria-describedby` |
| `Toaster`, `toast` | `toast.success(title, description)` etc. | one global area in the shell |
| `EmptyState` | `icon`, `title`, `description`, `action` | say what is missing and how to add it |
| `Skeleton`, `SkeletonText` | `shape` line, block, circle | |
| `KeyValueList` | `items` (`mono` per value), `columns` | |
| `ProgressBar` | `value`, `max`, `label`, `showValue`, `tone` forest or wheat | |
| `FileDropzone` | `onFiles`, `accept`, `multiple`, `maxSize`, `onReject` | keyboard operable button inside |
| `Switch` | `checked`, `onChange`, `label`, `hideLabel`, `description`, `disabled` | a real checkbox with `role="switch"` underneath, so it is announced and keyboard operable; for a genuine two-state setting, not a filter |
| `DiffView` | `diff` (`{ field: { from, to } }`), `compact` | the before and after of one change; a created record shows one column rather than an empty "was" |

## 6. Writing

English, sentence case, plain verbs. Buttons say what happens ("Register farmer", not
"Submit"); the toast repeats the verb ("Farmer registered"). Errors say what went wrong
and how to fix it. No emoji, stickers or illustrations; icons come only from `lucide-react`.
