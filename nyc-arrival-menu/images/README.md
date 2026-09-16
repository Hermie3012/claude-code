# Image slots

Twelve slots. Drop a file into this folder with the exact filename below and it
appears on the next page load — no markup change, no build step. Until the file
exists, the page draws the slot's specification card instead of a broken image.

Slots are filled by `assets/app.js`, which probes `data-src` on each
`.plate__frame` in `index.html` and only inserts an `<img>` once the file
actually loads. The `alt` text lives on `data-alt` in the markup and is applied
to the image when it is inserted, so editing the alt text means editing
`index.html`, not this file — the copies below are here so a photographer or
picture editor can read the brief in one place.

## Specification

| Slot | Filename | Ratio | Minimum size |
|-----:|----------|-------|--------------|
| 01 | `01-oysters.jpg`            | 4:3 | 1600 × 1200 |
| 02 | `02-coney-hot-dog.jpg`      | 4:3 | 1600 × 1200 |
| 03 | `03-pastrami-on-rye.jpg`    | 4:3 | 1600 × 1200 |
| 04 | `04-the-slice.jpg`          | 4:3 | 1600 × 1200 |
| 05 | `05-bagel-lox.jpg`          | 4:3 | 1600 × 1200 |
| 06 | `06-egg-cream.jpg`          | 3:4 | 1200 × 1600 |
| 07 | `07-cheesecake.jpg`         | 4:3 | 1600 × 1200 |
| 08 | `08-chicken-waffles.jpg`    | 4:3 | 1600 × 1200 |
| 09 | `09-general-tso.jpg`        | 4:3 | 1600 × 1200 |
| 10 | `10-chicken-over-rice.jpg`  | 4:3 | 1600 × 1200 |
| 11 | `11-bacon-egg-cheese.jpg`   | 3:2 | 1800 × 1200 |
| 12 | `12-chopped-cheese.jpg`     | 4:3 | 1600 × 1200 |

Images are drawn with `object-fit: cover`, so anything off-ratio is cropped from
the centre rather than distorted. Keep the subject away from the outer 8%.
JPEG at quality 80 or WebP; aim for under 300 KB each so the page stays quick.

## Briefs

**01 — Oysters**
*Alt:* A dozen raw oysters on crushed ice on a metal tray, with lemon wedges and a small dish of mignonette.
*Direction:* Shot from above under cold daylight. Wet shell, visible liquor. No garnish beyond lemon.

**02 — Coney Island hot dog**
*Alt:* A grilled hot dog in a split roll held in one hand, with a line of yellow mustard down the length of it.
*Direction:* Hand-held, outdoors, daylight. Paper tray, mustard stripe, boardwalk or street behind it at shallow depth of field.

**03 — Pastrami on rye**
*Alt:* A hand-carved pastrami sandwich on seeded rye, cut in half and stacked, with a smear of yellow mustard and a pickle spear.
*Direction:* Cut in half, stacked so the hand-carved edge and the pepper bark both read. Paper plate, deli counter light, mustard visible.

**04 — The slice**
*Alt:* A wide triangular cheese slice of New York pizza on a paper plate, folded along its spine, with grease at the crease.
*Direction:* A plain slice mid-fold on a thin paper plate. Counter fluorescents, not studio light. Char on the underside of the crust should be visible.

**05 — Bagel and lox**
*Alt:* An open bagel with a thick layer of cream cheese, folded ribbons of orange lox, red onion rings and capers.
*Direction:* Open-faced, three-quarter angle so the blistered crust and the cross-section both read. Onion and capers present but not styled into a wreath.

**06 — Egg cream** *(portrait)*
*Alt:* A tall straight-sided glass of chocolate egg cream on a counter, with a thick white foam collar at the top.
*Direction:* Tall glass, straight on, eye level with the foam line. Shoot within thirty seconds of it being made — the collar collapses.

**07 — New York cheesecake**
*Alt:* A tall wedge of plain New York cheesecake on a white plate, cut clean, with a thin sponge layer at the base.
*Direction:* One plain wedge, side-on at plate level, so the density of the crumb and the base layer both read. No fruit, no mint, no dusting.

**08 — Chicken and waffles**
*Alt:* Fried chicken pieces resting on a waffle, with a small jug of syrup and a bottle of hot sauce beside the plate.
*Direction:* Warm tungsten light, late-night diner feel. Chicken on top of the waffle, syrup and hot sauce both in frame — the two condiments are the story.

**09 — General Tso's chicken**
*Alt:* Glazed fried chicken pieces with dried chillies in a white oval dish, beside a folded white takeout carton.
*Direction:* The oval restaurant dish, not a styled bowl. Include the white takeout carton and the lazy-susan glass if you can get one — the room is the subject.

**10 — Chicken over rice**
*Alt:* A foil platter of yellow rice and chopped chicken with shredded lettuce, criss-crossed with white sauce and a line of red sauce.
*Direction:* Shot at night under cart lighting, foil platter on the counter edge. The white sauce should be over-applied. Keep the street in the background.

**11 — Bacon, egg and cheese** *(landscape)*
*Alt:* A bacon, egg and cheese sandwich on a kaiser roll, half unwrapped from foil and deli paper on a bodega counter.
*Direction:* Half-unwrapped from foil and paper, on the counter, not a plate. The wrapper is as important as the sandwich. Morning light through a shopfront.

**12 — Chopped cheese**
*Alt:* A chopped cheese sandwich cut in half on deli paper, showing chopped beef and melted American cheese in a hero roll with lettuce and tomato.
*Direction:* Cut in half on deli paper so the chop and the melt read in cross-section. Bodega grill light. Ideally the flat-top and two spatulas in the background.
