import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ImagePrepError } from '../api/image';
import { ChatInput, PHOTO_PRIVACY_NOTE } from './ChatInput';

const prepareImage = vi.fn();
vi.mock('../api/image', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/image')>()),
  prepareImage: (file: File) => prepareImage(file),
}));

const prepared = new Blob(['jpeg'], { type: 'image/jpeg' });

beforeEach(() => {
  prepareImage.mockReset();
  URL.createObjectURL = vi.fn(() => 'blob:preview');
  URL.revokeObjectURL = vi.fn();
});

function choose(testId: string, file = new File(['raw'], 'bottle.jpg', { type: 'image/jpeg' })) {
  fireEvent.change(screen.getByTestId(testId), { target: { files: [file] } });
}

describe('ChatInput photos', () => {
  it('offers both "Take photo" (camera) and "Upload photo" (files)', () => {
    render(<ChatInput disabled={false} photosEnabled onSubmit={() => {}} />);
    expect(screen.getByRole('button', { name: 'Take photo' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Upload photo' })).toBeInTheDocument();
    expect(screen.getByTestId('camera-input')).toHaveAttribute('capture', 'environment');
    expect(screen.getByTestId('upload-input')).not.toHaveAttribute('capture');
    expect(screen.getByText(PHOTO_PRIVACY_NOTE)).toBeInTheDocument();
  });

  it('sends an uploaded photo on its own, already prepared', async () => {
    prepareImage.mockResolvedValue(prepared);
    const onSubmit = vi.fn();
    render(<ChatInput disabled={false} photosEnabled onSubmit={onSubmit} />);
    expect(screen.getByRole('button', { name: /Ask/ })).toBeDisabled();

    choose('upload-input');
    expect(await screen.findByAltText('Photo to send')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Ask/ }));

    expect(onSubmit).toHaveBeenCalledWith('', prepared);
    expect(screen.queryByAltText('Photo to send')).not.toBeInTheDocument();
  });

  it('sends a camera photo together with a question', async () => {
    prepareImage.mockResolvedValue(prepared);
    const onSubmit = vi.fn();
    render(<ChatInput disabled={false} photosEnabled onSubmit={onSubmit} />);
    choose('camera-input');
    await screen.findByAltText('Photo to send');
    fireEvent.change(screen.getByLabelText('What do you want to throw away?'), { target: { value: 'Smart bin OK?' } });
    fireEvent.click(screen.getByRole('button', { name: /Ask/ }));
    expect(onSubmit).toHaveBeenCalledWith('Smart bin OK?', prepared);
  });

  it('can remove the photo before sending', async () => {
    prepareImage.mockResolvedValue(prepared);
    render(<ChatInput disabled={false} photosEnabled onSubmit={() => {}} />);
    choose('upload-input');
    await screen.findByAltText('Photo to send');
    fireEvent.click(screen.getByRole('button', { name: 'Remove photo' }));
    expect(screen.queryByAltText('Photo to send')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ask/ })).toBeDisabled();
  });

  it('shows a readable error for a photo it cannot open', async () => {
    prepareImage.mockRejectedValue(new ImagePrepError('Please choose a photo (JPEG, PNG or WebP).'));
    render(<ChatInput disabled={false} photosEnabled onSubmit={() => {}} />);
    choose('upload-input', new File(['x'], 'notes.pdf', { type: 'application/pdf' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('JPEG, PNG or WebP'));
  });

  it('disables photos when recognition is off', () => {
    render(<ChatInput disabled={false} photosEnabled={false} onSubmit={() => {}} />);
    expect(screen.getByRole('button', { name: 'Upload photo' })).toBeDisabled();
    expect(screen.getByText(/describe the item in words/)).toBeInTheDocument();
  });
});
