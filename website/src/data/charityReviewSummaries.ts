import { ratingFromGmgScore } from '../components/gmg/rating';

interface CharityReviewSummary {
  reviewName?: string;
  description: string;
  source: { label: string; url: string };
}

const summaries: Record<string, CharityReviewSummary> = {
  '13-3433452': {
    reviewName: 'Doctors Without Borders USA',
    description: 'Its 2024 filing shows 83.5% of spending went to programs, including emergency medical aid.',
    source: {
      label: 'MSF USA financial statements and filings',
      url: 'https://www.doctorswithoutborders.org/who-we-are/finances-reporting-accountability',
    },
  },
  '94-2614101': {
    reviewName: 'Second Harvest of Silicon Valley',
    description: 'Its 2024–25 annual report details food distribution in Santa Clara and San Mateo counties.',
    source: {
      label: 'Second Harvest’s 2024–25 annual report',
      url: 'https://www.shfb.org/about-us/governance-and-financial/annual-report-2024-2025/',
    },
  },
  '75-2882187': {
    reviewName: 'Amoud Foundation',
    description: 'Review the charity’s financial disclosures and its published zakat claim before donating.',
    source: {
      label: 'Amoud Foundation’s financial disclosures',
      url: 'https://www.amoudfoundation.org/financial-information/',
    },
  },
  '13-5660870': {
    description: 'The International Rescue Committee says its dedicated Zakat Fund accepts zakat during Ramadan only. Check the fund’s terms before giving.',
    source: {
      label: 'IRC’s Zakat Fund policy',
      url: 'https://www.rescue.org/zakat-fund',
    },
  },
};

export function charityReviewSummary(ein: string, score: number | null | undefined) {
  if (!Object.hasOwn(summaries, ein)) return undefined;
  const { reviewName, description, source } = summaries[ein];
  const rating = reviewName && score != null ? ratingFromGmgScore(score) : null;
  return {
    title: rating ? `${reviewName} Review: ${rating} Rating | GMG` : undefined,
    description: rating ? `Good Measure Giving rating: ${rating}. ${description}` : description,
    source,
  };
}
