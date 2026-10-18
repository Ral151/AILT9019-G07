import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ApiResponse } from '../types/api';
import { ExchangeItem } from './ExchangeItem';

const caveatAnswer: ApiResponse = {
  request_id: 'r2',
  action: 'answer_with_caveat',
  reason_code: 'OK',
  answer_text: 'Plastic bottles go in the Plastic bottle compartment.',
  bin_category: 'Plastic bottle',
  caveats: ['Smart Recycling Bins don’t all accept the same items.'],
  citations: [],
  redirect: null,
  image: null,
  served_from_cache: false,
};

describe('ExchangeItem', () => {
  it('shows a loading state while waiting', () => {
    render(<ExchangeItem exchange={{ id: 1, question: 'Q?', response: null, error: null }} busy onRetry={() => {}} />);
    expect(screen.getByRole('status')).toHaveTextContent(/Checking HKU/);
  });

  it('shows the caveat note with the answer', () => {
    render(
      <ExchangeItem exchange={{ id: 1, question: 'Q?', response: caveatAnswer, error: null }} busy={false} onRetry={() => {}} />,
    );
    expect(screen.getByText('Answer with note')).toBeInTheDocument();
    expect(screen.getByText('Please note')).toBeInTheDocument();
    expect(screen.getByText('Plastic bottle')).toBeInTheDocument();
  });

  it('offers a retry after an error', () => {
    const onRetry = vi.fn();
    render(
      <ExchangeItem exchange={{ id: 7, question: 'Q?', response: null, error: 'Server down' }} busy={false} onRetry={onRetry} />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Server down');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(onRetry).toHaveBeenCalledWith(7);
  });
});
