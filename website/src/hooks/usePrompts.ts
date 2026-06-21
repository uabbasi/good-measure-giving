import { useQuery } from '@tanstack/react-query';

export interface Prompt {
  id: string;
  name: string;
  category: string;
  description: string;
  status: 'active' | 'planned';
}

export interface PromptCategory {
  id: string;
  name: string;
  description: string;
}

export interface PromptsIndex {
  prompts: Prompt[];
  categories: PromptCategory[];
  total_count: number;
  active_count: number;
  planned_count: number;
}

export interface Annotation {
  section: string;
  lines: string;
  explanation: string;
}

export interface PromptDetail extends Prompt {
  source_file: string;
  content: string;
  annotations: Annotation[];
}

export function usePromptsIndex(): { data: PromptsIndex | null; loading: boolean } {
  const { data, isLoading } = useQuery({
    queryKey: ['prompts'],
    queryFn: async (): Promise<PromptsIndex> => {
      const r = await fetch('/data/prompts/index.json');
      return r.json();
    },
  });
  return { data: data ?? null, loading: isLoading };
}

export function usePromptDetail(id: string): { prompt: PromptDetail | null; loading: boolean; error: string | null } {
  const { data, isLoading, error } = useQuery({
    queryKey: ['prompt', id],
    queryFn: async (): Promise<PromptDetail> => {
      const r = await fetch(`/data/prompts/${id}.json`);
      if (!r.ok) throw new Error('Prompt not found');
      return r.json();
    },
    enabled: !!id,
    retry: false,
  });
  return { prompt: data ?? null, loading: isLoading, error: error ? (error as Error).message : null };
}
