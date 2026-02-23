import type { DriveStep } from 'driver.js';

export const browseTourSteps: DriveStep[] = [
  {
    popover: {
      title: 'Welcome to Good Measure',
      description:
        'We evaluate Muslim charities on impact, alignment, and transparency so you can give with confidence.',
    },
  },
  {
    element: '[data-tour="browse-search"]',
    popover: {
      title: 'Search',
      description:
        'Find any charity by name, mission keywords, or EIN.',
    },
  },
  {
    element: '[data-tour="browse-guided"]',
    popover: {
      title: 'Start With Your Intent',
      description:
        'These paths match your giving goal \u2014 zakat compliance, cause area, maximum leverage, or browse everything.',
    },
  },
  {
    element: '[data-tour="browse-first-card"]',
    popover: {
      title: 'Charity Cards',
      description:
        'Each card shows the <strong>recommendation badge</strong> (our overall assessment), <strong>evidence stage</strong>, and <strong>wallet tag</strong> (zakat/sadaqah). Click any card for the full evaluation.',
    },
  },
];
