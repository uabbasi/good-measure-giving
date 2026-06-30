// Good Measure Giving — "Modern" motif AI prompt detail (/prompts/:promptId).
// Motif-only (no legacy variant): renders its own GmgNav + footer via the content kit.

import React, { useState } from 'react';
import { useParams, Navigate } from 'react-router-dom';
import {
  GmgContentFrame,
  Breadcrumb,
  ContentHero,
  Section,
  P,
  type ContentCtx,
} from '../src/components/gmg/content';
import { FONT_MONO } from '../src/components/gmg/tokens';
import type { GmgPalette } from '../src/components/gmg/tokens';
import { usePromptDetail } from '../src/hooks/usePrompts';

const categoryLabels: Record<string, string> = {
  quality_validation: 'Quality Validation',
  data_extraction: 'Data Extraction',
  narrative_generation: 'Narrative Generation',
  category_calibration: 'Category Calibration',
};

// Mono badge used for category + status metadata.
const Badge: React.FC<{ p: GmgPalette; children: React.ReactNode }> = ({ p, children }) => (
  <span
    style={{
      fontFamily: FONT_MONO,
      fontSize: 11,
      letterSpacing: '0.04em',
      padding: '4px 10px',
      borderRadius: 99,
      border: `1px solid ${p.rule2}`,
      background: p.bg2,
      color: p.sub,
    }}
  >
    {children}
  </span>
);

export const PromptDetailPage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  const { promptId } = useParams<{ promptId: string }>();
  const { prompt, loading, error } = usePromptDetail(promptId || '');
  const [copied, setCopied] = useState(false);
  const [expandedAnnotations, setExpandedAnnotations] = useState<Set<number>>(new Set([0]));

  const copyToClipboard = async () => {
    if (!prompt) return;
    try {
      await navigator.clipboard.writeText(prompt.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const toggleAnnotation = (index: number) => {
    setExpandedAnnotations((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  if (error) return <Navigate to="/prompts" replace />;

  return (
    <GmgContentFrame isDark={isDark} maxWidth={860}>
      {(ctx: ContentCtx) => {
        const { p } = ctx;

        if (loading || !prompt) return <P p={p} muted>Loading prompt…</P>;

        return (
          <>
            <Breadcrumb
              p={p}
              trail={[
                { label: 'Home', to: '/' },
                { label: 'AI Transparency', to: '/prompts' },
                { label: prompt.name },
              ]}
            />

            <ContentHero ctx={ctx} kicker="AI Prompt" title={prompt.name} lead={prompt.description} />

            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <Badge p={p}>{categoryLabels[prompt.category] || prompt.category}</Badge>
              <Badge p={p}>{prompt.status === 'active' ? 'Active' : 'Planned'}</Badge>
              <button
                type="button"
                onClick={copyToClipboard}
                style={{
                  marginLeft: 'auto',
                  padding: '8px 16px',
                  borderRadius: 99,
                  border: `1px solid ${copied ? p.accent : p.rule2}`,
                  background: copied ? p.accent : 'transparent',
                  color: copied ? p.bg : p.sub,
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: 'pointer',
                  fontFamily: FONT_MONO,
                }}
              >
                {copied ? 'Copied' : 'Copy prompt'}
              </button>
            </div>

            <Section ctx={ctx} title="Prompt content" first>
              <div
                style={{
                  borderRadius: 12,
                  border: `1px solid ${p.rule}`,
                  background: p.bg2,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '10px 16px',
                    borderBottom: `1px solid ${p.rule}`,
                    fontFamily: FONT_MONO,
                    fontSize: 11,
                    color: p.sub2,
                  }}
                >
                  <span style={{ letterSpacing: '0.08em', textTransform: 'uppercase' }}>Prompt</span>
                  <span>{prompt.source_file}</span>
                </div>
                <pre
                  style={{
                    margin: 0,
                    padding: 16,
                    maxHeight: 600,
                    overflow: 'auto',
                    fontFamily: FONT_MONO,
                    fontSize: 13,
                    lineHeight: 1.6,
                    color: p.fg,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  <code>{prompt.content}</code>
                </pre>
              </div>
            </Section>

            <Section ctx={ctx} title="Annotations">
              {prompt.annotations.length === 0 ? (
                <P p={p} muted>No annotations available for this prompt.</P>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {prompt.annotations.map((annotation, index) => {
                    const open = expandedAnnotations.has(index);
                    return (
                      <div
                        key={index}
                        style={{ border: `1px solid ${p.rule}`, borderRadius: 12, background: p.card, overflow: 'hidden' }}
                      >
                        <button
                          type="button"
                          onClick={() => toggleAnnotation(index)}
                          style={{
                            width: '100%',
                            display: 'flex',
                            alignItems: 'baseline',
                            gap: 10,
                            padding: '14px 16px',
                            background: 'transparent',
                            border: 'none',
                            cursor: 'pointer',
                            textAlign: 'left',
                            color: p.fg,
                          }}
                        >
                          <span style={{ fontFamily: FONT_MONO, fontSize: 12, color: p.accent2 }}>
                            {open ? '−' : '+'}
                          </span>
                          <span style={{ flexGrow: 1, fontSize: 15, fontWeight: 600 }}>{annotation.section}</span>
                          {annotation.lines && (
                            <span style={{ fontFamily: FONT_MONO, fontSize: 11, color: p.sub2 }}>
                              Lines {annotation.lines}
                            </span>
                          )}
                        </button>
                        {open && (
                          <div
                            style={{
                              padding: '0 16px 16px 38px',
                              fontSize: 14,
                              lineHeight: 1.65,
                              color: p.sub,
                            }}
                          >
                            {annotation.explanation}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </Section>
          </>
        );
      }}
    </GmgContentFrame>
  );
};
