import React from 'react';
import { render } from '@testing-library/react';
import { AudioVisualizer } from './AudioVisualizer';

describe('AudioVisualizer Component', () => {
  it('renders correctly when idle', () => {
    const { container } = render(<AudioVisualizer isActive={false} mode="idle" />);
    
    // Check if the canvas is in the document
    const canvas = container.querySelector('canvas');
    expect(canvas).toBeInTheDocument();
  });

  it('renders correctly when active and listening', () => {
    const { container } = render(<AudioVisualizer isActive={true} mode="listening" />);
    
    // Check if the canvas element is still rendering properly in active state
    const canvas = container.querySelector('canvas');
    expect(canvas).toBeInTheDocument();
  });
  
  it('renders correctly when active and transcribing', () => {
    const { container } = render(<AudioVisualizer isActive={true} mode="transcribing" />);
    
    const canvas = container.querySelector('canvas');
    expect(canvas).toBeInTheDocument();
  });
});
