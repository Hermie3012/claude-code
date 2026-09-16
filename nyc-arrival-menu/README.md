# New York's Arrival Menu

A single-page editorial site about New York City's iconic dishes, told as a
chronological timeline. The argument the page makes is that the city's menu and
its immigration record are the same document: every era is anchored to who was
arriving and which law let them, and the dishes sit on that spine as stations.

Twelve dishes are covered in full, twenty more in the margins, across six eras
from the Lenape oyster beds to birria on Roosevelt Avenue.

## Running it

No build step, no dependencies. Open `index.html` in a browser, or serve the
folder:

```bash
python3 -m http.server 8000 --directory .
# then http://localhost:8000
```

To publish on GitHub Pages, point Pages at this directory on the branch.

## Files

```
index.html          the page
assets/style.css    tokens, layout, both themes, print styles
assets/app.js       theme toggle, reading progress, era tracking, image slots
images/README.md    the twelve image slots: filenames, ratios, alt text, briefs
```

## Images

The page ships with no photographs. Each of the twelve image slots renders a
specification card — slot number, expected filename, pixel size, and a shot
brief — until the file exists. Drop a correctly named file into `images/` and it
appears on the next load; nothing else needs to change.

`assets/app.js` probes `data-src` on each `.plate__frame` and only inserts an
`<img>` once the file loads, so a missing photo never produces a broken-image
icon and the page degrades to the specification card instead. See
[`images/README.md`](images/README.md) for the full brief.

Alt text lives on `data-alt` in `index.html` and is applied to the image when it
is inserted; `images/README.md` carries a readable copy of each one.

## Design notes

- **Palette** comes from the Anthora coffee cup (Leslie Buck, 1963): Greek-key
  blue `#16307E` on a cool paper white, with a mustard `#A66C0C` for heat.
  Neutrals are biased slightly toward the blue rather than left pure grey.
- **Type** is Libre Caslon Display for headlines, Newsreader for body, and
  Archivo Narrow for years, labels and specification cards. Every face has a
  real fallback stack.
- **Structure carries information.** Year ticks, the arrivals strip and the
  policy callouts are not decoration — an era is defined by who was arriving and
  which act of Congress let them, so 1882, 1924 and 1965 are marked as
  explicitly as the dishes are.
- **Themes.** The complete light palette is defined on bare `:root`; dark
  redefines only the tokens, once under `prefers-color-scheme` (guarded against
  an explicit light choice) and once under `[data-theme="dark"]` so the toggle
  wins both ways. The toggle persists to `localStorage` inside try/catch and the
  page renders correctly when storage throws.
- **Accessibility.** Skip link, landmark elements, visible focus rings,
  `aria-current` on the active era, `prefers-reduced-motion` honoured, and no
  content that depends on an entrance animation to become visible.

## On the accuracy of the content

Almost every origin story in New York food is contested. Where a claim is
genuinely disputed — Feltman's first hot dog, Lombardi's first licence, Volk's
first pastrami sandwich, the etymology of the egg cream — the page says so in
the copy rather than picking a winner. Laws, union charters and business
openings are the firm dates; "invented by" is not. The closing *On the record*
section states this to the reader directly.

Restaurants named on the page were open at the time of writing. Closed ones
(Glaser's, Gem Spa, the Automat) are deliberately in the past tense.
