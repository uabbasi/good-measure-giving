import type { DriveStep } from 'driver.js';

export const givingPlanTourSteps: DriveStep[] = [
  {
    popover: {
      title: 'Your Giving Plan',
      description:
        'This is your personal zakat and sadaqah dashboard. Set a target, organize charities into categories, and track every donation \u2014 all in one place.',
    },
  },
  {
    element: '[data-tour="giving-target"]',
    popover: {
      title: 'Set Your Zakat Target',
      description:
        'Enter your annual zakat obligation. The progress bar tracks how much you\u2019ve given against this goal.',
    },
  },
  {
    element: '[data-tour="giving-add-charity"]',
    popover: {
      title: 'Add Charities',
      description:
        'Search any evaluated charity and add it to your plan. Charities are auto-assigned to matching categories based on their cause tags.',
    },
  },
  {
    element: '[data-tour="giving-add-category"]',
    popover: {
      title: 'Create Categories',
      description:
        'Organize your giving by geography (Palestine, Pakistan), cause (education, medical), or population (refugees, orphans). Set a percentage for each.',
    },
  },
  {
    element: '[data-tour="giving-log-donation"]',
    popover: {
      title: 'Log Donations',
      description:
        'Record each donation with amount, date, and zakat/sadaqah classification. Your history is exportable as CSV for tax records.',
    },
  },
  {
    element: '[data-tour="giving-history-tab"]',
    popover: {
      title: 'Giving History',
      description:
        'Switch to the History tab to see all your logged donations, edit entries, and export by year.',
    },
  },
];
