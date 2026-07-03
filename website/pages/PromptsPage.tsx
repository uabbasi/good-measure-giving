// Good Measure Giving — "Modern" motif AI transparency index (/prompts).
// Motif-only (no legacy variant): renders its own GmgNav + footer via the content kit.

import React, { useState, useEffect, useMemo } from 'react';
import { promptPath } from '../src/lib/paths';
import {
  GmgContentFrame,
  Breadcrumb,
  ContentHero,
  Section,
  P,
  CardGrid,
  LinkCard,
  type ContentCtx,
} from '../src/components/gmg/content';
import { FONT_MONO } from '../src/components/gmg/tokens';
import type { GmgPalette } from '../src/components/gmg/tokens';
import { usePromptsIndex } from '../src/hooks/usePrompts';
import type { Prompt } from '../src/hooks/usePrompts';

// Small motif stat chip — mono label + bold count.
const StatChip: React.FC<{ p: GmgPalette; count: number; label: string }> = ({ p, count, label }) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'baseline',
      gap: 8,
      padding: '8px 14px',
      borderRadius: 10,
      border: `1px solid ${p.rule}`,
      background: p.bg2,
    }}
  >
    <span style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 600, color: p.fg }}>{count}</span>
    <span
      style={{ fontFamily: FONT_MONO, fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase', color: p.sub2 }}
    >
      {label}
    </span>
  </div>
);

// Motif filter pill — selected fills with the sage accent.
const Pill: React.FC<{ p: GmgPalette; active: boolean; onClick: () => void; children: React.ReactNode }> = ({
  p,
  active,
  onClick,
  children,
}) => (
  <button
    type="button"
    onClick={onClick}
    style={{
      padding: '7px 14px',
      borderRadius: 99,
      border: `1px solid ${active ? p.accent : p.rule2}`,
      background: active ? p.accent : 'transparent',
      color: active ? p.bg : p.sub,
      fontSize: 13,
      fontWeight: 500,
      cursor: 'pointer',
      fontFamily: FONT_MONO,
      letterSpacing: '0.02em',
    }}
  >
    {children}
  </button>
);

export const PromptsPage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  const { data, loading } = usePromptsIndex();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  useEffect(() => {
    document.title = 'AI Transparency | Good Measure Giving';
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  const filteredPrompts = useMemo(() => {
    if (!data) return [];
    return data.prompts.filter((prompt) => {
      const matchesSearch =
        !searchTerm ||
        prompt.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        prompt.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesCategory = !selectedCategory || prompt.category === selectedCategory;
      return matchesSearch && matchesCategory;
    });
  }, [data, searchTerm, selectedCategory]);

  const groupedPrompts = useMemo(() => {
    const groups: Record<string, Prompt[]> = {};
    for (const prompt of filteredPrompts) {
      if (!groups[prompt.category]) groups[prompt.category] = [];
      groups[prompt.category].push(prompt);
    }
    return groups;
  }, [filteredPrompts]);

  return (
    <GmgContentFrame isDark={isDark} maxWidth={960}>
      {(ctx: ContentCtx) => {
        const { p } = ctx;

        if (loading) return <P p={p} muted>Loading prompts…</P>;
        if (!data) return <P p={p} muted>Failed to load prompts.</P>;

        return (
          <>
            <Breadcrumb p={p} trail={[{ label: 'Home', to: '/' }, { label: 'AI Transparency' }]} />

            <ContentHero
              ctx={ctx}
              kicker="AI Transparency"
              title="Our AI Prompts"
              lead="We believe in radical transparency. We publish our core prompts and prompt annotations here, and continue expanding coverage. You can see exactly what instructions we give to AI models, how we prevent hallucinations, and what safeguards ensure accuracy."
            />

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 28 }}>
              <StatChip p={p} count={data.total_count} label="Total" />
              <StatChip p={p} count={data.active_count} label="Active" />
              <StatChip p={p} count={data.planned_count} label="Planned" />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginBottom: 8 }}>
              <input
                type="text"
                placeholder="Search prompts…"
                aria-label="Search prompts"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  padding: '11px 16px',
                  borderRadius: 10,
                  border: `1px solid ${p.rule2}`,
                  background: p.card,
                  color: p.fg,
                  fontSize: 15,
                  fontFamily: 'inherit',
                  outline: 'none',
                }}
              />
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                <Pill p={p} active={selectedCategory === null} onClick={() => setSelectedCategory(null)}>
                  All
                </Pill>
                {data.categories.map((cat) => (
                  <Pill
                    key={cat.id}
                    p={p}
                    active={selectedCategory === cat.id}
                    onClick={() => setSelectedCategory(cat.id)}
                  >
                    {cat.name}
                  </Pill>
                ))}
              </div>
            </div>

            {Object.entries(groupedPrompts).map(([categoryId, prompts], idx) => {
              const category = data.categories.find((c) => c.id === categoryId);
              return (
                <Section key={categoryId} ctx={ctx} title={category?.name || categoryId} first={idx === 0}>
                  {category?.description && <P p={p} muted>{category.description}</P>}
                  <CardGrid min={260}>
                    {prompts.map((prompt) => (
                      <LinkCard
                        key={prompt.id}
                        p={p}
                        to={promptPath(prompt.id)}
                        title={prompt.name}
                        desc={prompt.description}
                        meta={prompt.status === 'active' ? 'Active' : 'Planned'}
                      />
                    ))}
                  </CardGrid>
                </Section>
              );
            })}

            {filteredPrompts.length === 0 && (
              <P p={p} muted>No prompts match your search.</P>
            )}
          </>
        );
      }}
    </GmgContentFrame>
  );
};
