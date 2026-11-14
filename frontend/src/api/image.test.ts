import { describe, expect, it } from 'vitest';
import { ImagePrepError, prepareImage, scaledSize } from './image';

describe('scaledSize', () => {
  it('fits the long edge into 1024 px and keeps the aspect ratio', () => {
    expect(scaledSize(4032, 3024)).toEqual({ width: 1024, height: 768 });
    expect(scaledSize(3024, 4032)).toEqual({ width: 768, height: 1024 });
  });

  it('never upscales small photos', () => {
    expect(scaledSize(640, 480)).toEqual({ width: 640, height: 480 });
  });
});

describe('prepareImage', () => {
  it('rejects files that are not images', async () => {
    const pdf = new File(['%PDF'], 'notes.pdf', { type: 'application/pdf' });
    await expect(prepareImage(pdf)).rejects.toBeInstanceOf(ImagePrepError);
  });
});
