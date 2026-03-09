/**
 * Static pricing catalog for in-kind donation fair market values
 * Sources: Salvation Army Donation Value Guide, Goodwill published ranges
 * Per IRS Publication 561, values represent typical thrift store prices
 */

export type ItemCondition = 'excellent' | 'good' | 'fair' | 'poor';

export interface ValueGuideItem {
  id: string;
  category: string;
  name: string;
  /** Price range per condition: [low, high] */
  values: Record<ItemCondition, [number, number]>;
}

export interface ValueGuideCategory {
  id: string;
  name: string;
  icon: string; // emoji for display
  items: ValueGuideItem[];
}

/** IRS Publication 561 condition definitions */
export const CONDITION_DEFINITIONS: Record<ItemCondition, string> = {
  excellent: 'Like new, barely used, no defects or wear',
  good: 'Minor wear, fully functional, no significant flaws',
  fair: 'Shows wear, may have minor defects but still usable',
  poor: 'Significant wear, may need repair, still has some value',
};

export const VALUE_GUIDE_LAST_UPDATED = '2025-01-15';
export const VALUE_GUIDE_SOURCES = [
  { name: 'Salvation Army Donation Value Guide', url: 'https://satruck.org/donation-value-guide' },
  { name: 'Goodwill Industries Published Ranges', url: 'https://www.goodwill.org/donate/tax-deductions/' },
];

function item(id: string, category: string, name: string, excellent: [number, number], good: [number, number], fair: [number, number], poor: [number, number]): ValueGuideItem {
  return { id, category, name, values: { excellent, good, fair, poor } };
}

// ──────────────────────────────────────────────────────────────
// Clothing (Adult Men & Women)
// Merged: SA guide values widen low end on blazer, jeans, blouse, jacket, skirt
// Removed: generic children's/infant items → replaced by dedicated categories
// Added: overcoat, pajamas, nightgown from SA guide
// ──────────────────────────────────────────────────────────────
const clothing: ValueGuideCategory = {
  id: 'clothing',
  name: 'Clothing',
  icon: '\u{1F455}',
  items: [
    // ── Men's Suits & Formalwear ──
    item('cl-mens-suit', 'Clothing', "Men's Suit (2pc)", [40, 100], [15, 60], [8, 30], [4, 15]),
    item('cl-mens-suit-3pc', 'Clothing', "Men's Suit (3pc)", [50, 120], [20, 70], [10, 35], [5, 18]),
    item('cl-mens-blazer', 'Clothing', "Men's Blazer/Sport Coat", [15, 60], [7, 25], [4, 15], [2, 8]),
    item('cl-mens-vest-dress', 'Clothing', "Men's Suit Vest/Waistcoat", [8, 25], [4, 15], [2, 8], [1, 4]),
    item('cl-mens-tuxedo', 'Clothing', "Men's Tuxedo", [40, 120], [20, 70], [10, 35], [5, 18]),

    // ── Men's Tops ──
    item('cl-mens-shirt', 'Clothing', "Men's Dress Shirt", [6, 18], [3, 12], [2, 8], [1, 4]),
    item('cl-mens-casual-shirt', 'Clothing', "Men's Casual/Button-Down Shirt", [5, 15], [3, 10], [2, 6], [1, 3]),
    item('cl-mens-polo', 'Clothing', "Men's Polo Shirt", [5, 15], [3, 10], [2, 6], [1, 3]),
    item('cl-mens-tshirt', 'Clothing', "Men's T-Shirt", [4, 12], [1, 6], [1, 4], [0.5, 2]),
    item('cl-mens-tank', 'Clothing', "Men's Tank Top/Undershirt", [2, 6], [1, 4], [0.5, 2], [0.25, 1]),
    item('cl-mens-henley', 'Clothing', "Men's Henley/Long-Sleeve Tee", [5, 12], [2, 8], [1, 5], [0.5, 3]),
    item('cl-mens-hawaiian', 'Clothing', "Men's Hawaiian/Camp Shirt", [5, 15], [3, 10], [2, 6], [1, 3]),

    // ── Men's Sweaters & Layers ──
    item('cl-mens-sweater', 'Clothing', "Men's Sweater/Pullover", [8, 20], [3, 12], [2, 8], [1, 4]),
    item('cl-mens-cardigan', 'Clothing', "Men's Cardigan", [8, 22], [4, 14], [2, 8], [1, 4]),
    item('cl-mens-hoodie', 'Clothing', "Men's Hoodie/Sweatshirt", [6, 18], [3, 12], [2, 7], [1, 4]),
    item('cl-mens-fleece', 'Clothing', "Men's Fleece Pullover/Jacket", [8, 22], [4, 14], [2, 8], [1, 4]),
    item('cl-mens-vest-casual', 'Clothing', "Men's Casual Vest/Down Vest", [8, 25], [5, 15], [3, 8], [2, 4]),

    // ── Men's Bottoms ──
    item('cl-mens-pants', 'Clothing', "Men's Dress Pants/Slacks", [8, 25], [5, 12], [3, 10], [2, 5]),
    item('cl-mens-chinos', 'Clothing', "Men's Chinos/Khakis", [6, 18], [4, 12], [2, 8], [1, 4]),
    item('cl-mens-jeans', 'Clothing', "Men's Jeans", [8, 25], [4, 20], [3, 10], [2, 5]),
    item('cl-mens-cargo', 'Clothing', "Men's Cargo Pants", [6, 18], [4, 12], [2, 8], [1, 4]),
    item('cl-mens-shorts', 'Clothing', "Men's Shorts", [5, 12], [3, 8], [2, 5], [1, 3]),
    item('cl-mens-athletic-shorts', 'Clothing', "Men's Athletic Shorts", [4, 12], [2, 8], [1, 5], [0.5, 3]),
    item('cl-mens-sweatpants', 'Clothing', "Men's Sweatpants/Joggers", [5, 15], [3, 10], [2, 6], [1, 3]),

    // ── Men's Outerwear ──
    item('cl-mens-jacket', 'Clothing', "Men's Jacket/Coat (Winter)", [20, 60], [15, 60], [8, 20], [4, 10]),
    item('cl-mens-overcoat', 'Clothing', "Men's Overcoat/Topcoat", [20, 75], [15, 60], [8, 30], [4, 12]),
    item('cl-mens-parka', 'Clothing', "Men's Parka/Down Jacket", [25, 80], [15, 50], [8, 25], [4, 12]),
    item('cl-mens-rain-jacket', 'Clothing', "Men's Rain Jacket/Windbreaker", [8, 25], [5, 15], [3, 10], [2, 5]),
    item('cl-mens-leather-jacket', 'Clothing', "Men's Leather Jacket", [30, 100], [20, 60], [10, 30], [5, 15]),
    item('cl-mens-denim-jacket', 'Clothing', "Men's Denim Jacket", [10, 30], [6, 18], [3, 10], [2, 5]),
    item('cl-mens-ski-jacket', 'Clothing', "Men's Ski/Snowboard Jacket", [20, 70], [12, 40], [6, 20], [3, 10]),

    // ── Men's Activewear & Sleepwear ──
    item('cl-mens-athletic-top', 'Clothing', "Men's Athletic/Gym Shirt", [4, 12], [2, 8], [1, 5], [0.5, 3]),
    item('cl-mens-athletic-pants', 'Clothing', "Men's Athletic/Track Pants", [5, 15], [3, 10], [2, 6], [1, 3]),
    item('cl-mens-tracksuit', 'Clothing', "Men's Track Suit", [10, 30], [6, 18], [3, 10], [2, 5]),
    item('cl-mens-pajamas', 'Clothing', "Men's Pajamas", [5, 15], [2, 10], [1, 6], [0.5, 3]),
    item('cl-mens-thermals', 'Clothing', "Men's Thermal Underwear (set)", [5, 15], [3, 10], [2, 6], [1, 3]),

    // ── Men's Workwear ──
    item('cl-mens-scrubs', 'Clothing', "Men's Scrubs (set)", [8, 20], [4, 12], [2, 8], [1, 4]),
    item('cl-mens-coveralls', 'Clothing', "Men's Coveralls/Overalls", [10, 30], [6, 18], [3, 10], [2, 5]),
    item('cl-mens-work-jacket', 'Clothing', "Men's Work Jacket (Carhartt-style)", [15, 45], [8, 25], [4, 15], [2, 8]),
    item('cl-mens-work-pants', 'Clothing', "Men's Work Pants", [6, 18], [4, 12], [2, 8], [1, 4]),

    // ── Women's Dresses & Formalwear ──
    item('cl-womens-dress', 'Clothing', "Women's Dress (Casual)", [10, 40], [4, 20], [3, 12], [2, 6]),
    item('cl-womens-dress-cocktail', 'Clothing', "Women's Cocktail/Party Dress", [15, 60], [8, 30], [4, 18], [2, 8]),
    item('cl-formal-gown', 'Clothing', "Women's Evening Gown", [25, 100], [10, 60], [6, 25], [3, 12]),
    item('cl-womens-sundress', 'Clothing', "Women's Sundress", [6, 20], [3, 12], [2, 8], [1, 4]),
    item('cl-womens-maxi-dress', 'Clothing', "Women's Maxi Dress", [8, 25], [4, 15], [3, 10], [2, 5]),
    item('cl-womens-suit', 'Clothing', "Women's Suit", [25, 80], [7, 30], [4, 18], [2, 8]),
    item('cl-womens-blazer', 'Clothing', "Women's Blazer", [10, 35], [5, 20], [3, 12], [2, 6]),
    item('cl-womens-romper', 'Clothing', "Women's Romper/Jumpsuit", [8, 25], [4, 15], [3, 10], [2, 5]),

    // ── Women's Tops ──
    item('cl-womens-blouse', 'Clothing', "Women's Blouse", [5, 18], [3, 12], [2, 7], [1, 4]),
    item('cl-womens-tank', 'Clothing', "Women's Tank Top/Camisole", [2, 8], [1, 5], [0.5, 3], [0.25, 1.50]),
    item('cl-womens-tshirt', 'Clothing', "Women's T-Shirt", [4, 12], [1, 6], [1, 4], [0.5, 2]),
    item('cl-womens-tunic', 'Clothing', "Women's Tunic", [6, 18], [3, 12], [2, 7], [1, 4]),
    item('cl-womens-crop-top', 'Clothing', "Women's Crop Top", [3, 10], [2, 6], [1, 4], [0.5, 2]),
    item('cl-womens-polo', 'Clothing', "Women's Polo Shirt", [4, 12], [2, 8], [1, 5], [0.5, 3]),

    // ── Women's Sweaters & Layers ──
    item('cl-womens-sweater', 'Clothing', "Women's Sweater/Pullover", [8, 20], [4, 12], [2, 8], [1, 4]),
    item('cl-womens-cardigan', 'Clothing', "Women's Cardigan", [8, 22], [4, 14], [2, 8], [1, 4]),
    item('cl-womens-hoodie', 'Clothing', "Women's Hoodie/Sweatshirt", [6, 18], [3, 12], [2, 7], [1, 4]),
    item('cl-womens-fleece', 'Clothing', "Women's Fleece Jacket", [8, 22], [4, 14], [2, 8], [1, 4]),
    item('cl-womens-vest', 'Clothing', "Women's Vest/Down Vest", [8, 25], [5, 15], [3, 8], [2, 4]),
    item('cl-womens-poncho', 'Clothing', "Women's Poncho/Cape", [8, 25], [5, 15], [3, 8], [2, 4]),
    item('cl-womens-shawl', 'Clothing', "Women's Shawl/Wrap", [5, 18], [3, 12], [2, 7], [1, 3]),

    // ── Women's Bottoms ──
    item('cl-womens-skirt', 'Clothing', "Women's Skirt", [5, 15], [3, 12], [2, 7], [1, 4]),
    item('cl-womens-maxi-skirt', 'Clothing', "Women's Maxi Skirt", [6, 18], [3, 12], [2, 8], [1, 4]),
    item('cl-womens-pants', 'Clothing', "Women's Pants/Slacks", [6, 18], [4, 12], [3, 8], [1, 4]),
    item('cl-womens-jeans', 'Clothing', "Women's Jeans", [8, 25], [4, 20], [3, 10], [2, 5]),
    item('cl-womens-leggings', 'Clothing', "Women's Leggings", [4, 12], [2, 8], [1, 5], [0.5, 3]),
    item('cl-womens-capris', 'Clothing', "Women's Capris/Cropped Pants", [5, 15], [3, 10], [2, 6], [1, 3]),
    item('cl-womens-shorts', 'Clothing', "Women's Shorts", [4, 12], [2, 8], [1, 5], [0.5, 3]),
    item('cl-womens-athletic-shorts', 'Clothing', "Women's Athletic Shorts", [4, 10], [2, 7], [1, 4], [0.5, 2]),
    item('cl-womens-sweatpants', 'Clothing', "Women's Sweatpants/Joggers", [5, 15], [3, 10], [2, 6], [1, 3]),

    // ── Women's Outerwear ──
    item('cl-womens-jacket', 'Clothing', "Women's Jacket/Coat (Winter)", [15, 50], [10, 40], [6, 20], [3, 10]),
    item('cl-womens-parka', 'Clothing', "Women's Parka/Down Jacket", [20, 65], [12, 40], [6, 20], [3, 10]),
    item('cl-womens-rain-jacket', 'Clothing', "Women's Rain Jacket/Windbreaker", [8, 22], [4, 14], [2, 8], [1, 4]),
    item('cl-womens-leather-jacket', 'Clothing', "Women's Leather Jacket", [25, 80], [15, 50], [8, 25], [4, 12]),
    item('cl-womens-denim-jacket', 'Clothing', "Women's Denim Jacket", [8, 25], [5, 15], [3, 10], [2, 5]),
    item('cl-womens-trench', 'Clothing', "Women's Trench Coat", [15, 50], [8, 30], [4, 18], [2, 8]),
    item('cl-womens-fur-faux', 'Clothing', "Women's Faux Fur Coat/Jacket", [15, 50], [8, 30], [4, 15], [2, 8]),

    // ── Women's Activewear & Sleepwear ──
    item('cl-womens-athletic-top', 'Clothing', "Women's Athletic/Sports Top", [4, 12], [2, 8], [1, 5], [0.5, 3]),
    item('cl-womens-athletic-pants', 'Clothing', "Women's Athletic/Yoga Pants", [5, 15], [3, 10], [2, 6], [1, 3]),
    item('cl-womens-sports-bra', 'Clothing', "Women's Sports Bra", [3, 10], [2, 6], [1, 4], [0.5, 2]),
    item('cl-womens-nightgown', 'Clothing', "Women's Nightgown/Sleepwear", [6, 18], [4, 12], [2, 8], [1, 4]),
    item('cl-womens-robe', 'Clothing', "Women's Robe", [6, 18], [4, 12], [2, 7], [1, 3]),

    // ── Women's Workwear ──
    item('cl-womens-scrubs', 'Clothing', "Women's Scrubs (set)", [8, 20], [4, 12], [2, 8], [1, 4]),
    item('cl-womens-uniform', 'Clothing', "Women's Uniform (shirt or pants)", [4, 12], [2, 8], [1, 5], [0.5, 3]),

    // ── Unisex / Shared ──
    item('cl-bathrobe', 'Clothing', 'Bathrobe', [6, 15], [4, 10], [2, 6], [1, 3]),
    item('cl-swimsuit', 'Clothing', 'Swimsuit', [5, 15], [3, 10], [2, 6], [1, 3]),
    item('cl-tie', 'Clothing', 'Necktie', [3, 10], [2, 6], [1, 4], [0.5, 2]),
    item('cl-bowtie', 'Clothing', 'Bow Tie', [2, 8], [1, 5], [0.5, 3], [0.25, 1.50]),
    item('cl-belt', 'Clothing', 'Belt', [3, 10], [2, 8], [1, 4], [0.5, 2]),
    item('cl-suspenders', 'Clothing', 'Suspenders', [3, 10], [2, 6], [1, 4], [0.5, 2]),
    item('cl-rain-poncho', 'Clothing', 'Rain Poncho', [3, 10], [2, 6], [1, 4], [0.5, 2]),
    item('cl-ski-pants', 'Clothing', 'Ski/Snow Pants', [10, 30], [6, 18], [3, 10], [2, 5]),
    item('cl-wetsuit', 'Clothing', 'Wetsuit', [15, 50], [8, 30], [4, 15], [2, 8]),
    item('cl-costume', 'Clothing', 'Costume/Halloween', [5, 20], [3, 12], [2, 8], [1, 4]),
    item('cl-uniform-generic', 'Clothing', 'Uniform (generic)', [5, 15], [3, 10], [2, 6], [1, 3]),
    item('cl-maternity-top', 'Clothing', 'Maternity Top', [4, 12], [2, 8], [1, 5], [0.5, 3]),
    item('cl-maternity-pants', 'Clothing', 'Maternity Pants', [5, 15], [3, 10], [2, 6], [1, 3]),
    item('cl-maternity-dress', 'Clothing', 'Maternity Dress', [8, 25], [4, 15], [3, 10], [2, 5]),
    item('cl-womens-handbag', 'Clothing', "Women's Handbag", [8, 30], [3, 20], [2, 10], [1, 5]),
  ],
};

// ──────────────────────────────────────────────────────────────
// Boys' Clothing — NEW from Salvation Army guide
// ──────────────────────────────────────────────────────────────
const boysClothing: ValueGuideCategory = {
  id: 'boys-clothing',
  name: "Boys' Clothing",
  icon: '\u{1F466}',
  items: [
    item('cb-blazer', "Boys' Clothing", 'Boys Blazer', [10, 15], [5, 12], [3, 8], [2, 4]),
    item('cb-boots', "Boys' Clothing", 'Boys Boots', [12, 20], [6, 15], [3, 10], [2, 5]),
    item('cb-coat', "Boys' Clothing", 'Boys Coat (Winter)', [12, 20], [7, 15], [5, 10], [3, 6]),
    item('cb-jacket', "Boys' Clothing", 'Boys Jacket (Light)', [10, 15], [5, 12], [3, 8], [2, 4]),
    item('cb-jeans', "Boys' Clothing", 'Boys Jeans/Pants', [6, 10], [3, 8], [2, 5], [1, 3]),
    item('cb-pajamas', "Boys' Clothing", 'Boys Pajamas', [4, 6], [2, 5], [1, 3], [0.5, 2]),
    item('cb-shirt', "Boys' Clothing", 'Boys Shirt', [5, 8], [3, 6], [2, 4], [1, 2]),
    item('cb-shorts', "Boys' Clothing", 'Boys Shorts', [4, 6], [2, 5], [1, 3], [0.5, 2]),
    item('cb-slacks', "Boys' Clothing", 'Boys Slacks', [6, 10], [3, 8], [2, 5], [1, 3]),
    item('cb-snowsuit', "Boys' Clothing", 'Boys Snowsuit', [10, 15], [6, 12], [4, 8], [2, 4]),
    item('cb-suit', "Boys' Clothing", 'Boys Suit', [10, 15], [6, 12], [5, 8], [3, 5]),
    item('cb-sweater', "Boys' Clothing", 'Boys Sweater', [6, 10], [3, 8], [2, 5], [1, 3]),
    item('cb-swimsuit', "Boys' Clothing", 'Boys Swimsuit', [4, 6], [2, 5], [1, 3], [0.5, 2]),
    item('cb-tshirt', "Boys' Clothing", 'Boys T-shirt', [2, 3], [1, 2.50], [0.50, 1.50], [0.25, 1]),
  ],
};

// ──────────────────────────────────────────────────────────────
// Girls' Clothing — NEW from Salvation Army guide
// ──────────────────────────────────────────────────────────────
const girlsClothing: ValueGuideCategory = {
  id: 'girls-clothing',
  name: "Girls' Clothing",
  icon: '\u{1F467}',
  items: [
    item('cg-blouse', "Girls' Clothing", 'Girls Blouse', [5, 8], [3, 6], [2, 4], [1, 2]),
    item('cg-boots', "Girls' Clothing", 'Girls Boots', [12, 20], [6, 15], [3, 10], [2, 5]),
    item('cg-coat', "Girls' Clothing", 'Girls Coat (Winter)', [12, 20], [7, 15], [5, 10], [3, 6]),
    item('cg-dress', "Girls' Clothing", 'Girls Dress', [8, 12], [4, 10], [3, 6], [1, 3]),
    item('cg-jacket', "Girls' Clothing", 'Girls Jacket (Light)', [10, 15], [5, 12], [3, 8], [2, 4]),
    item('cg-jeans', "Girls' Clothing", 'Girls Jeans/Pants', [6, 10], [3, 8], [2, 5], [1, 3]),
    item('cg-pajamas', "Girls' Clothing", 'Girls Pajamas', [4, 6], [2, 5], [1, 3], [0.5, 2]),
    item('cg-shorts', "Girls' Clothing", 'Girls Shorts', [4, 6], [2, 5], [1, 3], [0.5, 2]),
    item('cg-skirt', "Girls' Clothing", 'Girls Skirt', [4, 6], [3, 5], [2, 3], [1, 2]),
    item('cg-snowsuit', "Girls' Clothing", 'Girls Snowsuit', [10, 15], [6, 12], [4, 8], [2, 4]),
    item('cg-sweater', "Girls' Clothing", 'Girls Sweater', [6, 10], [3, 8], [2, 5], [1, 3]),
    item('cg-swimsuit', "Girls' Clothing", 'Girls Swimsuit', [4, 6], [2, 5], [1, 3], [0.5, 2]),
    item('cg-tshirt', "Girls' Clothing", 'Girls T-shirt', [2, 3], [1, 2.50], [0.50, 1.50], [0.25, 1]),
  ],
};

// ──────────────────────────────────────────────────────────────
// Baby & Toddler — NEW category
// Merged from: Toys & Books (stroller, car seat, high chair, crib)
//            + Clothing (infant) + Salvation Army guide new items
// Values widened where SA guide suggests broader range
// ──────────────────────────────────────────────────────────────
const baby: ValueGuideCategory = {
  id: 'baby',
  name: 'Baby & Toddler',
  icon: '\u{1F476}',
  items: [
    item('ba-blanket', 'Baby & Toddler', 'Baby Blanket', [6, 10], [3, 8], [2, 5], [1, 3]),
    item('ba-clothes', 'Baby & Toddler', 'Baby Clothes (Single Item)', [4, 6], [2, 5], [1, 3], [0.5, 2]),
    item('ba-shoes', 'Baby & Toddler', 'Baby Shoes', [3, 5], [2, 4], [1, 3], [0.5, 1.50]),
    item('ba-bunting', 'Baby & Toddler', 'Bunting/Snowsuit', [10, 15], [6, 12], [4, 8], [2, 4]),
    item('ba-car-seat', 'Baby & Toddler', 'Car Seat (check expiration)', [20, 50], [10, 40], [5, 20], [3, 10]),
    item('ba-crib', 'Baby & Toddler', 'Crib (no mattress)', [40, 100], [25, 75], [12, 40], [5, 15]),
    item('ba-high-chair', 'Baby & Toddler', 'High Chair', [20, 50], [10, 35], [5, 18], [2, 8]),
    item('ba-playpen', 'Baby & Toddler', 'Playpen', [18, 30], [10, 22], [4, 14], [2, 6]),
    item('ba-stroller', 'Baby & Toddler', 'Stroller (Standard)', [25, 75], [10, 50], [5, 25], [3, 12]),
    item('ba-toddler-bed', 'Baby & Toddler', 'Toddler Bed', [35, 50], [25, 40], [15, 28], [8, 18]),
  ],
};

// ──────────────────────────────────────────────────────────────
// Shoes & Accessories
// Merged: Men's boots widened low end per SA guide [6,20]
// Handbag moved to Clothing (Women's Handbag) to match SA guide category
// ──────────────────────────────────────────────────────────────
const shoes: ValueGuideCategory = {
  id: 'shoes',
  name: 'Shoes & Accessories',
  icon: '\u{1F45F}',
  items: [
    item('sh-mens-dress', 'Shoes & Accessories', "Men's Dress Shoes", [15, 50], [10, 30], [5, 15], [3, 8]),
    item('sh-mens-casual', 'Shoes & Accessories', "Men's Casual Shoes", [10, 30], [6, 18], [4, 10], [2, 5]),
    item('sh-mens-athletic', 'Shoes & Accessories', "Men's Athletic Shoes", [10, 35], [6, 20], [4, 12], [2, 6]),
    item('sh-mens-boots', 'Shoes & Accessories', "Men's Boots", [12, 50], [6, 20], [4, 12], [2, 6]),
    item('sh-womens-dress', 'Shoes & Accessories', "Women's Dress Shoes", [10, 35], [6, 20], [4, 12], [2, 6]),
    item('sh-womens-casual', 'Shoes & Accessories', "Women's Casual Shoes", [8, 25], [5, 15], [3, 10], [2, 5]),
    item('sh-womens-boots', 'Shoes & Accessories', "Women's Boots", [12, 40], [6, 20], [4, 12], [2, 6]),
    item('sh-womens-athletic', 'Shoes & Accessories', "Women's Athletic Shoes", [8, 30], [5, 18], [3, 10], [2, 6]),
    item('sh-child-shoes', 'Shoes & Accessories', "Children's Shoes", [5, 15], [3, 10], [2, 6], [1, 3]),
    item('sh-sandals', 'Shoes & Accessories', 'Sandals/Flip-Flops', [3, 12], [2, 8], [1, 5], [0.5, 3]),
    item('sh-wallet', 'Shoes & Accessories', 'Wallet', [4, 15], [3, 10], [2, 6], [1, 3]),
    item('sh-hat', 'Shoes & Accessories', 'Hat/Cap', [3, 10], [2, 6], [1, 4], [0.5, 2]),
    item('sh-scarf', 'Shoes & Accessories', 'Scarf', [3, 12], [2, 8], [1, 5], [0.5, 2]),
    item('sh-gloves', 'Shoes & Accessories', 'Gloves', [3, 10], [2, 6], [1, 4], [0.5, 2]),
    item('sh-sunglasses', 'Shoes & Accessories', 'Sunglasses', [5, 15], [3, 10], [2, 6], [1, 3]),
    item('sh-watch', 'Shoes & Accessories', 'Watch', [10, 40], [6, 25], [4, 15], [2, 8]),
    item('sh-jewelry', 'Shoes & Accessories', 'Costume Jewelry', [3, 15], [2, 10], [1, 6], [0.5, 3]),
  ],
};

// ──────────────────────────────────────────────────────────────
// Electronics
// Merged: Laptop [50,250], Printer [5,150], Stereo [15,75], Tablet [25,150],
//         TV [20,170] widened per SA guide
// Added: eReader, Radio/Clock Radio, Cell Phone (Basic)
// Cell Phone split into Smartphone vs Basic per SA guide distinction
// ──────────────────────────────────────────────────────────────
const electronics: ValueGuideCategory = {
  id: 'electronics',
  name: 'Electronics',
  icon: '\u{1F4BB}',
  items: [
    item('el-laptop', 'Electronics', 'Laptop Computer', [75, 250], [50, 150], [20, 70], [5, 30]),
    item('el-desktop', 'Electronics', 'Desktop Computer (System)', [30, 150], [25, 80], [10, 40], [5, 20]),
    item('el-tablet', 'Electronics', 'Tablet/iPad', [40, 150], [25, 80], [10, 45], [4, 20]),
    item('el-monitor', 'Electronics', 'Computer Monitor (LCD)', [15, 60], [5, 50], [3, 20], [2, 10]),
    item('el-printer', 'Electronics', 'Computer Printer', [25, 150], [12, 75], [5, 35], [3, 15]),
    item('el-tv-flat', 'Electronics', 'Television (LED/Flat)', [40, 170], [20, 90], [10, 45], [5, 20]),
    item('el-stereo', 'Electronics', 'Stereo System', [20, 75], [15, 45], [5, 25], [3, 12]),
    item('el-speakers', 'Electronics', 'Speakers (pair)', [10, 40], [6, 25], [3, 15], [2, 8]),
    item('el-dvd-player', 'Electronics', 'DVD/Blu-ray Player', [8, 20], [5, 15], [3, 8], [1, 4]),
    item('el-game-console', 'Electronics', 'Video Game Console', [25, 100], [15, 60], [8, 30], [4, 15]),
    item('el-camera', 'Electronics', 'Digital Camera', [15, 60], [10, 35], [5, 20], [3, 10]),
    item('el-phone', 'Electronics', 'Cell Phone (Smartphone)', [30, 100], [25, 60], [10, 30], [5, 15]),
    item('el-phone-basic', 'Electronics', 'Cell Phone (Basic/Old)', [8, 20], [5, 15], [3, 8], [2, 5]),
    item('el-ereader', 'Electronics', 'eReader (Kindle)', [15, 50], [10, 35], [5, 20], [3, 10]),
    item('el-radio', 'Electronics', 'Radio/Clock Radio', [5, 15], [3, 10], [2, 6], [1, 3]),
    item('el-router', 'Electronics', 'WiFi Router', [5, 20], [3, 12], [2, 8], [1, 4]),
    item('el-headphones', 'Electronics', 'Headphones', [5, 25], [3, 15], [2, 8], [1, 4]),
    item('el-keyboard', 'Electronics', 'Keyboard', [3, 15], [2, 10], [1, 5], [0.5, 3]),
    item('el-mouse', 'Electronics', 'Mouse', [2, 10], [1, 6], [1, 4], [0.5, 2]),
  ],
};

const furniture: ValueGuideCategory = {
  id: 'furniture',
  name: 'Furniture',
  icon: '\u{1FA91}',
  items: [
    item('fu-sofa', 'Furniture', 'Sofa/Couch', [50, 200], [30, 120], [15, 60], [5, 25]),
    item('fu-loveseat', 'Furniture', 'Loveseat', [35, 150], [20, 80], [10, 40], [5, 20]),
    item('fu-recliner', 'Furniture', 'Recliner', [25, 100], [15, 60], [8, 30], [4, 15]),
    item('fu-dining-table', 'Furniture', 'Dining Table', [30, 150], [20, 80], [10, 40], [5, 20]),
    item('fu-dining-chair', 'Furniture', 'Dining Chair (each)', [8, 30], [5, 18], [3, 10], [2, 5]),
    item('fu-coffee-table', 'Furniture', 'Coffee Table', [15, 60], [10, 35], [5, 20], [3, 10]),
    item('fu-end-table', 'Furniture', 'End Table', [10, 40], [6, 25], [3, 15], [2, 8]),
    item('fu-desk', 'Furniture', 'Desk', [20, 80], [12, 50], [6, 25], [3, 12]),
    item('fu-office-chair', 'Furniture', 'Office Chair', [15, 60], [10, 35], [5, 20], [3, 10]),
    item('fu-bookcase', 'Furniture', 'Bookcase', [15, 60], [10, 35], [5, 20], [3, 10]),
    item('fu-dresser', 'Furniture', 'Dresser/Chest of Drawers', [25, 100], [15, 60], [8, 30], [4, 15]),
    item('fu-nightstand', 'Furniture', 'Nightstand', [10, 35], [6, 20], [3, 12], [2, 6]),
    item('fu-bed-frame', 'Furniture', 'Bed Frame', [25, 100], [15, 60], [8, 30], [4, 15]),
    item('fu-mattress', 'Furniture', 'Mattress', [40, 150], [25, 80], [10, 40], [5, 20]),
    item('fu-tv-stand', 'Furniture', 'TV Stand/Entertainment Center', [15, 60], [10, 35], [5, 20], [3, 10]),
    item('fu-shelf', 'Furniture', 'Shelving Unit', [10, 40], [6, 25], [3, 15], [2, 8]),
    item('fu-filing-cabinet', 'Furniture', 'Filing Cabinet', [10, 35], [6, 20], [3, 12], [2, 6]),
    item('fu-ottoman', 'Furniture', 'Ottoman/Footstool', [8, 30], [5, 18], [3, 10], [2, 5]),
  ],
};

// ──────────────────────────────────────────────────────────────
// Kitchen & Dining
// Merged: Microwave widened to [10,50] per SA guide
// Added: Cooking Utensils, Pot/Pan (single) from SA guide
// ──────────────────────────────────────────────────────────────
const kitchen: ValueGuideCategory = {
  id: 'kitchen',
  name: 'Kitchen & Dining',
  icon: '\u{1F373}',
  items: [
    item('ki-microwave', 'Kitchen & Dining', 'Microwave', [15, 50], [10, 30], [4, 15], [2, 8]),
    item('ki-toaster', 'Kitchen & Dining', 'Toaster/Toaster Oven', [6, 18], [4, 15], [2, 8], [1, 4]),
    item('ki-coffee-maker', 'Kitchen & Dining', 'Coffee Maker', [6, 25], [4, 15], [2, 8], [1, 4]),
    item('ki-blender', 'Kitchen & Dining', 'Blender/Mixer', [6, 20], [4, 14], [2, 8], [1, 4]),
    item('ki-mixer', 'Kitchen & Dining', 'Stand Mixer', [20, 80], [12, 50], [6, 25], [3, 12]),
    item('ki-food-processor', 'Kitchen & Dining', 'Food Processor', [8, 30], [5, 18], [3, 10], [2, 5]),
    item('ki-slow-cooker', 'Kitchen & Dining', 'Slow Cooker', [5, 18], [3, 12], [2, 8], [1, 4]),
    item('ki-instant-pot', 'Kitchen & Dining', 'Instant Pot/Pressure Cooker', [10, 40], [6, 25], [3, 15], [2, 8]),
    item('ki-pots-pans', 'Kitchen & Dining', 'Pots & Pans Set', [10, 40], [6, 25], [3, 15], [2, 8]),
    item('ki-pot-pan', 'Kitchen & Dining', 'Pot/Pan (single)', [3, 8], [2, 5], [1, 3], [0.50, 2]),
    item('ki-dish-set', 'Kitchen & Dining', 'Dish Set (6+ pc)', [8, 30], [6, 25], [3, 10], [2, 5]),
    item('ki-silverware', 'Kitchen & Dining', 'Silverware Set', [5, 18], [3, 12], [2, 8], [1, 4]),
    item('ki-glassware', 'Kitchen & Dining', 'Glassware Set', [5, 15], [3, 10], [2, 6], [1, 3]),
    item('ki-knife-set', 'Kitchen & Dining', 'Knife Set', [8, 30], [5, 18], [3, 10], [2, 5]),
    item('ki-bakeware', 'Kitchen & Dining', 'Bakeware Set', [5, 18], [3, 12], [2, 8], [1, 4]),
    item('ki-bakeware-single', 'Kitchen & Dining', 'Bakeware (single piece)', [2, 5], [1, 3], [0.50, 2], [0.25, 1]),
    item('ki-cutting-board', 'Kitchen & Dining', 'Cutting Board', [2, 8], [1, 5], [1, 3], [0.5, 2]),
    item('ki-utensils', 'Kitchen & Dining', 'Cooking Utensils', [1.50, 4], [0.50, 2], [0.25, 1.50], [0.25, 1]),
  ],
};

// ──────────────────────────────────────────────────────────────
// Home Appliances
// Merged: Vacuum widened to [15,65] per SA guide
// Iron adjusted to [3,10] per SA guide
// ──────────────────────────────────────────────────────────────
const appliances: ValueGuideCategory = {
  id: 'appliances',
  name: 'Home Appliances',
  icon: '\u{1F9F9}',
  items: [
    item('ap-vacuum', 'Home Appliances', 'Vacuum Cleaner', [25, 65], [15, 40], [6, 20], [3, 10]),
    item('ap-iron', 'Home Appliances', 'Iron', [5, 12], [3, 10], [2, 6], [1, 3]),
    item('ap-fan', 'Home Appliances', 'Fan (table/floor)', [5, 18], [3, 12], [2, 8], [1, 4]),
    item('ap-space-heater', 'Home Appliances', 'Space Heater', [8, 25], [5, 15], [3, 10], [2, 5]),
    item('ap-air-purifier', 'Home Appliances', 'Air Purifier', [10, 40], [6, 25], [3, 15], [2, 8]),
    item('ap-humidifier', 'Home Appliances', 'Humidifier', [5, 20], [3, 12], [2, 8], [1, 4]),
    item('ap-sewing-machine', 'Home Appliances', 'Sewing Machine', [15, 60], [10, 35], [5, 20], [3, 10]),
    item('ap-washer', 'Home Appliances', 'Washing Machine', [50, 200], [30, 120], [15, 60], [5, 25]),
    item('ap-dryer', 'Home Appliances', 'Dryer', [50, 175], [30, 100], [15, 50], [5, 25]),
    item('ap-dehumidifier', 'Home Appliances', 'Dehumidifier', [10, 40], [6, 25], [3, 15], [2, 8]),
  ],
};

// ──────────────────────────────────────────────────────────────
// Home Decor & Linens
// Merged: Floor Lamp widened to [6,50] per SA guide
// Added: Drapes from SA guide
// ──────────────────────────────────────────────────────────────
const homeDecor: ValueGuideCategory = {
  id: 'home-decor',
  name: 'Home Decor & Linens',
  icon: '\u{1F6CB}\u{FE0F}',
  items: [
    item('hd-lamp', 'Home Decor & Linens', 'Table Lamp', [5, 20], [3, 12], [2, 8], [1, 4]),
    item('hd-floor-lamp', 'Home Decor & Linens', 'Floor Lamp', [15, 50], [6, 30], [3, 15], [2, 8]),
    item('hd-picture-frame', 'Home Decor & Linens', 'Picture Frame', [3, 12], [2, 8], [1, 5], [0.5, 3]),
    item('hd-wall-art', 'Home Decor & Linens', 'Wall Art/Print', [5, 25], [3, 15], [2, 8], [1, 4]),
    item('hd-mirror', 'Home Decor & Linens', 'Mirror', [5, 25], [3, 15], [2, 8], [1, 4]),
    item('hd-vase', 'Home Decor & Linens', 'Vase', [3, 12], [2, 8], [1, 5], [0.5, 3]),
    item('hd-curtains', 'Home Decor & Linens', 'Curtains (pair)', [5, 18], [3, 12], [2, 8], [1, 4]),
    item('hd-drapes', 'Home Decor & Linens', 'Drapes', [12, 40], [6, 25], [3, 15], [2, 6]),
    item('hd-rug', 'Home Decor & Linens', 'Area Rug', [10, 50], [6, 30], [3, 15], [2, 8]),
    item('hd-comforter', 'Home Decor & Linens', 'Comforter/Duvet', [8, 30], [5, 18], [3, 10], [2, 5]),
    item('hd-sheet-set', 'Home Decor & Linens', 'Sheet Set', [5, 15], [3, 10], [2, 6], [1, 3]),
    item('hd-blanket', 'Home Decor & Linens', 'Blanket/Throw', [4, 15], [3, 10], [2, 6], [1, 3]),
    item('hd-pillow', 'Home Decor & Linens', 'Pillow', [4, 8], [2, 6], [1, 4], [0.5, 2]),
    item('hd-towel-set', 'Home Decor & Linens', 'Towel Set', [4, 12], [3, 8], [2, 5], [1, 3]),
    item('hd-tablecloth', 'Home Decor & Linens', 'Tablecloth', [3, 10], [2, 6], [1, 4], [0.5, 2]),
    item('hd-candle-holder', 'Home Decor & Linens', 'Candle Holder', [2, 10], [1, 6], [1, 4], [0.5, 2]),
    item('hd-clock', 'Home Decor & Linens', 'Clock', [3, 15], [2, 10], [1, 6], [0.5, 3]),
  ],
};

const sports: ValueGuideCategory = {
  id: 'sports',
  name: 'Sports & Outdoor',
  icon: '\u{26BD}',
  items: [
    item('sp-bicycle', 'Sports & Outdoor', 'Bicycle', [30, 120], [20, 70], [10, 35], [5, 15]),
    item('sp-exercise-bike', 'Sports & Outdoor', 'Exercise Bike', [25, 100], [15, 60], [8, 30], [4, 15]),
    item('sp-treadmill', 'Sports & Outdoor', 'Treadmill', [50, 200], [30, 120], [15, 60], [5, 25]),
    item('sp-weights', 'Sports & Outdoor', 'Weight Set', [15, 60], [10, 35], [5, 20], [3, 10]),
    item('sp-golf-clubs', 'Sports & Outdoor', 'Golf Club Set', [25, 100], [15, 60], [8, 30], [4, 15]),
    item('sp-tennis-racket', 'Sports & Outdoor', 'Tennis Racket', [5, 20], [3, 12], [2, 8], [1, 4]),
    item('sp-skis', 'Sports & Outdoor', 'Skis (pair)', [20, 80], [12, 50], [6, 25], [3, 12]),
    item('sp-snowboard', 'Sports & Outdoor', 'Snowboard', [20, 80], [12, 50], [6, 25], [3, 12]),
    item('sp-sleeping-bag', 'Sports & Outdoor', 'Sleeping Bag', [8, 30], [5, 18], [3, 10], [2, 5]),
    item('sp-tent', 'Sports & Outdoor', 'Tent', [15, 60], [10, 35], [5, 20], [3, 10]),
    item('sp-backpack', 'Sports & Outdoor', 'Backpack', [8, 25], [5, 15], [3, 10], [2, 5]),
    item('sp-camping-chair', 'Sports & Outdoor', 'Camping Chair', [4, 15], [3, 10], [2, 6], [1, 3]),
    item('sp-yoga-mat', 'Sports & Outdoor', 'Yoga Mat', [3, 12], [2, 8], [1, 5], [0.5, 3]),
    item('sp-helmet', 'Sports & Outdoor', 'Helmet (bike/ski)', [5, 20], [3, 12], [2, 8], [1, 4]),
  ],
};

// ──────────────────────────────────────────────────────────────
// Toys & Books
// Removed: Stroller, Car Seat, High Chair, Crib → moved to Baby & Toddler
// ──────────────────────────────────────────────────────────────
const toys: ValueGuideCategory = {
  id: 'toys',
  name: 'Toys & Books',
  icon: '\u{1F9F8}',
  items: [
    item('to-board-game', 'Toys & Books', 'Board Game', [3, 12], [2, 8], [1, 5], [0.5, 3]),
    item('to-puzzle', 'Toys & Books', 'Puzzle', [2, 8], [1, 5], [1, 3], [0.5, 2]),
    item('to-action-figure', 'Toys & Books', 'Action Figure/Doll', [3, 12], [2, 8], [1, 5], [0.5, 3]),
    item('to-stuffed-animal', 'Toys & Books', 'Stuffed Animal', [2, 8], [1, 5], [1, 3], [0.5, 2]),
    item('to-lego-set', 'Toys & Books', 'LEGO/Building Set', [5, 25], [3, 15], [2, 8], [1, 4]),
    item('to-toy-vehicle', 'Toys & Books', 'Toy Vehicle', [3, 12], [2, 8], [1, 5], [0.5, 3]),
    item('to-play-kitchen', 'Toys & Books', 'Play Kitchen/Workbench', [10, 40], [6, 25], [3, 15], [2, 8]),
    item('to-ride-on', 'Toys & Books', 'Ride-On Toy', [8, 30], [5, 18], [3, 10], [2, 5]),
    item('to-book-hardcover', 'Toys & Books', 'Book (Hardcover)', [2, 8], [1, 5], [1, 3], [0.5, 2]),
    item('to-book-paperback', 'Toys & Books', 'Book (Paperback)', [1, 5], [0.5, 3], [0.5, 2], [0.25, 1]),
    item('to-textbook', 'Toys & Books', 'Textbook', [5, 25], [3, 15], [2, 8], [1, 4]),
    item('to-dvd', 'Toys & Books', 'DVD/Blu-ray', [2, 6], [1, 4], [0.5, 3], [0.25, 1]),
    item('to-video-game', 'Toys & Books', 'Video Game', [5, 20], [3, 12], [2, 8], [1, 4]),
    item('to-musical-instrument', 'Toys & Books', 'Musical Instrument', [15, 60], [10, 35], [5, 20], [3, 10]),
  ],
};

const tools: ValueGuideCategory = {
  id: 'tools',
  name: 'Tools & Garden',
  icon: '\u{1F527}',
  items: [
    item('tl-power-drill', 'Tools & Garden', 'Power Drill', [10, 40], [6, 25], [3, 15], [2, 8]),
    item('tl-circular-saw', 'Tools & Garden', 'Circular Saw', [10, 40], [6, 25], [3, 15], [2, 8]),
    item('tl-hand-tools', 'Tools & Garden', 'Hand Tool Set', [8, 30], [5, 18], [3, 10], [2, 5]),
    item('tl-toolbox', 'Tools & Garden', 'Toolbox', [5, 20], [3, 12], [2, 8], [1, 4]),
    item('tl-lawn-mower', 'Tools & Garden', 'Lawn Mower (push)', [30, 120], [20, 70], [10, 35], [5, 15]),
    item('tl-weed-trimmer', 'Tools & Garden', 'Weed Trimmer', [8, 30], [5, 18], [3, 10], [2, 5]),
    item('tl-leaf-blower', 'Tools & Garden', 'Leaf Blower', [8, 30], [5, 18], [3, 10], [2, 5]),
    item('tl-garden-tools', 'Tools & Garden', 'Garden Tool Set', [5, 18], [3, 12], [2, 8], [1, 4]),
    item('tl-wheelbarrow', 'Tools & Garden', 'Wheelbarrow', [10, 35], [6, 20], [3, 12], [2, 6]),
    item('tl-ladder', 'Tools & Garden', 'Ladder', [10, 40], [6, 25], [3, 15], [2, 8]),
    item('tl-hose', 'Tools & Garden', 'Garden Hose', [3, 10], [2, 6], [1, 4], [0.5, 2]),
    item('tl-pot-planter', 'Tools & Garden', 'Flower Pot/Planter', [3, 12], [2, 8], [1, 5], [0.5, 3]),
    item('tl-grill', 'Tools & Garden', 'Grill/BBQ', [20, 80], [12, 50], [6, 25], [3, 12]),
    item('tl-patio-chair', 'Tools & Garden', 'Patio Chair', [8, 25], [5, 15], [3, 10], [2, 5]),
    item('tl-patio-table', 'Tools & Garden', 'Patio Table', [15, 50], [10, 30], [5, 18], [3, 10]),
  ],
};

export const VALUE_GUIDE_CATEGORIES: ValueGuideCategory[] = [
  clothing,
  boysClothing,
  girlsClothing,
  baby,
  shoes,
  electronics,
  furniture,
  kitchen,
  appliances,
  homeDecor,
  sports,
  toys,
  tools,
];

/** Flat list of all items for search */
export const ALL_VALUE_GUIDE_ITEMS: ValueGuideItem[] = VALUE_GUIDE_CATEGORIES.flatMap(c => c.items);

/** Get the midpoint value for a condition */
export function getMidpointValue(item: ValueGuideItem, condition: ItemCondition): number {
  const [low, high] = item.values[condition];
  return Math.round((low + high) / 2);
}
