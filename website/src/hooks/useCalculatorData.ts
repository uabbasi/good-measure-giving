import { useQuery } from '@tanstack/react-query';
import type { ZakatAssets } from '../../types';

export interface AssetSection {
  heading: string;
  paragraphs: string[];
}

export interface AssetFaq {
  q: string;
  a: string;
}

export interface AssetEntry {
  slug: string;
  displayName: string;
  metaTitle: string;
  metaDescription: string;
  heroAnswer: string;
  zakatAssetKey: keyof ZakatAssets;
  inputLabel: string;
  inputHelp: string;
  sections: AssetSection[];
  faq: AssetFaq[];
}

export interface CalculatorData {
  hub: { metaTitle: string; metaDescription: string; heroText: string };
  assets: AssetEntry[];
}

export function useCalculatorData(): { data: CalculatorData | null; loading: boolean } {
  const { data, isLoading } = useQuery({
    queryKey: ['calculator-data'],
    queryFn: async (): Promise<CalculatorData> => {
      const r = await fetch('/data/zakat-calculator/assets.json');
      return r.json();
    },
  });
  return { data: data ?? null, loading: isLoading };
}
