import { useQuery } from '@tanstack/react-query';
import type { GuidesIndex, Guide, GuideSummary } from '../../scripts/lib/guide-seo';

export function useGuides(): { guides: GuideSummary[]; loading: boolean } {
  const { data, isLoading } = useQuery({
    queryKey: ['guides'],
    queryFn: async (): Promise<GuidesIndex> => {
      const r = await fetch('/data/guides/guides.json');
      return r.json();
    },
  });
  return { guides: data?.guides ?? [], loading: isLoading };
}

export function useGuide(slug: string): { guide: Guide | null; loading: boolean; notFound: boolean } {
  const { data, isLoading, error } = useQuery({
    queryKey: ['guide', slug],
    queryFn: async (): Promise<Guide> => {
      const r = await fetch(`/data/guides/${slug}.json`);
      if (!r.ok) throw new Error('not-found');
      return r.json();
    },
    enabled: !!slug,
    retry: false,
  });
  return { guide: data ?? null, loading: isLoading, notFound: !!error };
}
