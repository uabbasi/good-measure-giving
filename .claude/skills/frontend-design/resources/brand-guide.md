# Brand & Design System Guide

Extended documentation for the zakaat charity evaluation website design system.

## Brand Positioning

### Core Promise
Help discerning Muslim donors make informed giving decisions through transparent data and rigorous methodology.

### Voice Characteristics

| Trait | Expression | Not |
|-------|------------|-----|
| **Informed** | We've analyzed the data | We know everything |
| **Honest** | Scholars differ on this | All zakat goes to X |
| **Respectful** | Consider this perspective | You should do this |
| **Efficient** | Here's what matters | Let us explain everything |
| **Trustworthy** | Source: Form 990, 2023 | Studies show... |

### Tone Examples

**Good:**
> "Based on Form 990 filings, this organization allocates 78% of revenue to program expenses. The Hanbali school considers educational programs zakat-eligible under fi sabilillah."

**Bad:**
> "This amazing charity is making a real difference! Your zakat will transform lives and create lasting impact in communities around the world."

---

## Typography System

### Font Stack

```css
/* Serif - Headlines, brand moments */
.font-merriweather {
  font-family: 'Merriweather', Georgia, serif;
}

/* Sans - Body, UI */
.font-sans {
  font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* Arabic - Quranic text only */
.font-arabic {
  font-family: 'Scheherazade New', 'Traditional Arabic', serif;
}

/* Monospace - Data, technical */
.font-mono {
  font-family: ui-monospace, 'Cascadia Code', 'Source Code Pro', monospace;
}
```

### Type Scale

| Level | Class | Use Case |
|-------|-------|----------|
| Display | `text-5xl lg:text-7xl font-bold` | Page hero headlines |
| H1 | `text-3xl lg:text-4xl font-bold` | Section headers |
| H2 | `text-xl lg:text-2xl font-semibold` | Subsection headers |
| H3 | `text-lg font-medium` | Card titles |
| Body | `text-base leading-relaxed` | Paragraph text |
| Small | `text-sm text-slate-600` | Captions, metadata |
| Micro | `text-xs uppercase tracking-wider` | Labels, badges |

---

## Color Tokens

### Semantic Colors

```tsx
// Primary actions
const primary = {
  default: 'emerald-700',
  hover: 'emerald-600',
  light: 'emerald-50',
};

// Wallet tag colors (self-assertion model)
// - ZAKAT-ELIGIBLE: Charity explicitly claims zakat eligibility on website
// - SADAQAH-STRATEGIC: High-impact systemic work, no zakat claim
// - SADAQAH-GENERAL: Standard charitable giving
// - INSUFFICIENT-DATA: Not enough info to classify
const walletTags = {
  'ZAKAT-ELIGIBLE': {
    bg: 'bg-emerald-100 dark:bg-emerald-900/30',
    text: 'text-emerald-800 dark:text-emerald-300',
    border: 'border-emerald-200 dark:border-emerald-700',
  },
  'SADAQAH-STRATEGIC': {
    bg: 'bg-indigo-100 dark:bg-indigo-900/30',
    text: 'text-indigo-800 dark:text-indigo-300',
    border: 'border-indigo-200 dark:border-indigo-700',
  },
  'SADAQAH-GENERAL': {
    bg: 'bg-gray-100 dark:bg-gray-800',
    text: 'text-gray-700 dark:text-gray-300',
    border: 'border-gray-200 dark:border-gray-700',
  },
  'INSUFFICIENT-DATA': {
    bg: 'bg-slate-100 dark:bg-slate-800',
    text: 'text-slate-600 dark:text-slate-400',
    border: 'border-slate-200 dark:border-slate-700',
  },
};

// Status colors
const status = {
  success: 'emerald-600',
  warning: 'amber-600',
  error: 'red-600',
  info: 'blue-600',
};
```

### Theme-Aware Patterns

```tsx
// Component pattern for theme-aware styling
function ThemedCard({ children }: { children: React.ReactNode }) {
  const { isDark } = useLandingTheme();

  return (
    <div className={cn(
      'rounded-xl p-6 transition-colors duration-300',
      isDark
        ? 'bg-slate-900 border border-slate-800 text-white'
        : 'bg-white border border-slate-200 text-slate-900'
    )}>
      {children}
    </div>
  );
}
```

---

## Spacing System

### Tailwind Scale Reference

| Token | Size | Use Case |
|-------|------|----------|
| 1 | 4px | Icon gaps |
| 2 | 8px | Inline element spacing |
| 3 | 12px | Small component padding |
| 4 | 16px | Standard padding |
| 6 | 24px | Card padding |
| 8 | 32px | Section gaps |
| 12 | 48px | Major section spacing |
| 16 | 64px | Page section margins |
| 24 | 96px | Hero/footer spacing |

### Consistent Patterns

```tsx
// Section spacing
<section className="py-16 lg:py-24">

// Card grid
<div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">

// Card internals
<div className="p-6 space-y-4">

// Inline elements
<div className="flex items-center gap-2">
```

---

## Component Patterns

### Cards

```tsx
// Standard card
<div className={cn(
  'rounded-xl p-6',
  'transition-all duration-300',
  'hover:shadow-lg hover:-translate-y-1',
  isDark
    ? 'bg-slate-900 border border-slate-800'
    : 'bg-white border border-slate-200 shadow-sm'
)}>
```

### Buttons

```tsx
// Primary button
<button className={cn(
  'px-6 py-3 rounded-full font-medium',
  'transition-all duration-300',
  'bg-emerald-700 text-white',
  'hover:bg-emerald-600 hover:shadow-lg',
  'active:scale-95',
  'disabled:opacity-50 disabled:cursor-not-allowed'
)}>

// Secondary button
<button className={cn(
  'px-6 py-3 rounded-full font-medium',
  'transition-all duration-300',
  isDark
    ? 'bg-slate-800 text-white hover:bg-slate-700'
    : 'bg-slate-100 text-slate-900 hover:bg-slate-200'
)}>
```

### Badges / Pills

```tsx
// Tag badge
<span className={cn(
  'inline-flex items-center gap-1.5',
  'px-3 py-1 rounded-full',
  'text-xs font-medium uppercase tracking-wider',
  'border',
  // Apply wallet tag colors based on type
)}>
  <Icon className="w-3.5 h-3.5" />
  {label}
</span>
```

---

## Iconography

### Lucide React Usage

```tsx
import { Heart, Shield, TrendingUp, AlertCircle } from 'lucide-react';

// Standard sizing
<Icon className="w-5 h-5" />          // Default
<Icon className="w-4 h-4" />          // Small (in buttons)
<Icon className="w-6 h-6" />          // Large (standalone)
<Icon className="w-8 h-8" />          // Feature icons

// With semantic color
<Shield className="w-5 h-5 text-emerald-700" />
<AlertCircle className="w-5 h-5 text-amber-600" />
```

### Icon Principles
- Always pair with text labels (no icon-only buttons)
- Use semantic colors to reinforce meaning
- Maintain consistent sizing within contexts
- Avoid decorative icons that add no information

---

## Responsive Breakpoints

### Tailwind Defaults

| Breakpoint | Min Width | Target |
|------------|-----------|--------|
| `sm` | 640px | Large phones |
| `md` | 768px | Tablets |
| `lg` | 1024px | Laptops |
| `xl` | 1280px | Desktops |
| `2xl` | 1536px | Large monitors |

### Mobile-First Patterns

```tsx
// Typography scaling
<h1 className="text-3xl md:text-4xl lg:text-5xl">

// Grid columns
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3">

// Padding scaling
<section className="px-4 md:px-8 lg:px-16">

// Stack to row
<div className="flex flex-col md:flex-row gap-4">
```

---

## Accessibility Requirements

### Color Contrast
- Normal text: 4.5:1 minimum
- Large text (18px+): 3:1 minimum
- Interactive elements: Clearly distinguishable states

### Interactive Elements
- Minimum touch target: 44x44px
- Focus states: Visible outline or ring
- Keyboard navigable: Tab order, Enter/Space activation

### Semantic HTML
```tsx
// Use proper heading hierarchy
<main>
  <h1>Page Title</h1>
  <section>
    <h2>Section</h2>
    <h3>Subsection</h3>
  </section>
</main>

// Accessible buttons
<button type="button" aria-label="Clear description">
  <Icon aria-hidden="true" />
</button>

// Form labels
<label htmlFor="email">Email</label>
<input id="email" type="email" />
```

---

## Anti-Pattern Quick Reference

### If You See This... Replace With...

| Anti-Pattern | Better Alternative |
|--------------|-------------------|
| `#00FF00` green | `emerald-700` |
| `font-inter` | `font-sans` or `font-merriweather` |
| `bg-gradient-to-r from-purple-500 to-blue-500` | Solid `bg-emerald-700` or subtle `bg-slate-50` |
| Hardcoded `#ffffff` | `bg-white` or theme-aware pattern |
| Stock prayer photo | Geometric pattern or data visualization |
| "Empowering communities" | Specific, factual description |
| Spinning counter animation | Static number with source citation |
| Modal on page load | Content visible by default |
| Icon-only button | Icon + text label |

---

## File Reference

Key files for understanding existing patterns:

| File | Contains |
|------|----------|
| `website/src/themes.tsx` | 5 experimental theme presets |
| `website/types/theme.ts` | TypeScript theme interfaces |
| `website/contexts/LandingThemeContext.tsx` | Dark mode toggle implementation |
| `website/src/components/CharityCard.tsx` | Card styling patterns |
| `website/src/components/BaselineCharityDetail.tsx` | Wallet tag styling |
| `website/README.md` | Mobile testing checklist |
