import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ApiResponse } from '../types/api';
import { ResponseCard } from './ResponseCard';

const base: ApiResponse = {
  request_id: 'r1',
  action: 'answer',
  reason_code: 'OK',
  answer_text: 'Beverage plastic bottles go in Plastics.',
  bin_category: 'Plastics',
  caveats: [],
  citations: [
    {
      source_id: 'recycling_101_poster',
      title: 'Recycling 101 poster',
      section: 'Plastic > DOs',
      lines: '20-20',
      excerpt: 'Beverage plastic bottles',
      url: 'https://example.org',
      retrieved_at: '2026-10-18',
    },
  ],
  redirect: null,
  image: null,
  served_from_cache: false,
};

describe('ResponseCard', () => {
  it('shows the bin category as text, not colour alone', () => {
    render(<ResponseCard response={base} />);
    expect(screen.getByText('Answer')).toBeInTheDocument();
    expect(screen.getByText('Bin category')).toBeInTheDocument();
    expect(screen.getByText('Plastics')).toBeInTheDocument();
    expect(screen.getByText('Beverage plastic bottles')).toBeInTheDocument();
  });

  it('shows no bin category and a redirect for a refusal', () => {
    render(
      <ResponseCard
        response={{
          ...base,
          action: 'refuse',
          reason_code: 'NO_UNIFIED_STANDARD',
          bin_category: null,
          citations: [],
          answer_text: 'There is no campus-wide rule for this item.',
          redirect: { label: 'Ask your hall tutor or CEDARS', url: 'https://www.cedars.hku.hk/' },
        }}
      />,
    );
    expect(screen.getByText("Can't help with this")).toBeInTheDocument();
    expect(screen.queryByText('Bin category')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ask your hall tutor or CEDARS' })).toBeInTheDocument();
  });

  it('says what the photo was identified as, but not for an unclear photo', () => {
    render(<ResponseCard response={{ ...base, image: { item_label: 'PET bottle', confidence: 0.95, needs_clearer_input: false } }} />);
    expect(screen.getByText(/Photo identified as/)).toHaveTextContent('Photo identified as: PET bottle');
  });

  it('shows no identified item when it asks for a clearer photo', () => {
    render(
      <ResponseCard
        response={{
          ...base,
          action: 'defer',
          reason_code: 'MULTIPLE_ITEMS',
          bin_category: null,
          citations: [],
          answer_text: 'I can see more than one item.',
          image: { item_label: '', confidence: 0, needs_clearer_input: true },
        }}
      />,
    );
    expect(screen.queryByText(/Photo identified as/)).not.toBeInTheDocument();
  });

  it('always shows the on-site priority notice', () => {
    render(<ResponseCard response={{ ...base, served_from_cache: true }} />);
    expect(screen.getByText(/On-site signs and staff always take priority/)).toBeInTheDocument();
    expect(screen.getByText('Demo answer')).toBeInTheDocument();
  });
});
