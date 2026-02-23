import type { DriveStep } from 'driver.js';

export const detailsTourSteps: DriveStep[] = [
  {
    element: '[data-tour="recommendation-cue"]',
    popover: {
      title: 'Our Assessment',
      description:
        'This badge is our bottom line on the charity — from <strong>Maximum Alignment</strong> (strongest match) down to <strong>Needs Verification</strong> (gaps remain). It weighs impact evidence, financial health, and donor fit together.',
    },
  },
  {
    element: '[data-tour="wallet-tag"]',
    popover: {
      title: 'Zakat Eligibility',
      description:
        'Tells you whether this charity qualifies for your zakat or sadaqah funds, based on beneficiary categories and fund segregation policies.',
    },
  },
  {
    element: '[data-tour="score-breakdown"]',
    popover: {
      title: 'Evaluation Breakdown',
      description:
        'Harvey balls show how the charity scores across <strong>Impact</strong> and <strong>Alignment</strong>. Scroll this section for strengths, areas to watch, and sourced evidence.',
    },
  },
  {
    element: '[data-tour="action-save"]',
    popover: {
      title: 'Save to Your Plan',
      description:
        'Bookmark this charity to add it to your giving plan. From there you can set a target amount and track donations.',
    },
  },
  {
    element: '[data-tour="action-log-donation"]',
    popover: {
      title: 'Track Your Giving',
      description:
        'Already donated? Log it here with the amount, date, and zakat/sadaqah classification. Everything shows up in your giving dashboard.',
    },
  },
  {
    element: '[data-tour="action-donate"]',
    popover: {
      title: 'Give Directly',
      description:
        'Opens the charity\u2019s own donation page. Come back and log it to keep your records complete.',
    },
  },
];
