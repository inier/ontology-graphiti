import { useState, useEffect, useCallback } from 'react';
import { Tour } from 'antd';
import type { TourProps } from 'antd';
import { useTourStore } from '../store/tourStore';

interface PageTourWrapperProps {
  /** Unique page identifier, e.g. 'workspace', 'ontology-designer' */
  pageId: string;
  /** Tour step definitions for this page */
  steps: TourProps['steps'];
  /** Delay in ms before auto-opening the tour (default 800) */
  delay?: number;
  /** Page content */
  children?: React.ReactNode;
}

/**
 * Reusable wrapper that auto-triggers an Ant Design Tour on first visit
 * to any page. Tracks completion in the Zustand tour store via localStorage.
 */
export function PageTourWrapper({ pageId, steps, delay = 800, children }: PageTourWrapperProps) {
  const [tourOpen, setTourOpen] = useState(false);
  const { isPageTourNeeded, markPageTourCompleted, activeTourId, setActiveTour } = useTourStore();

  useEffect(() => {
    const timer = setTimeout(() => {
      // Only open if: this page needs a tour AND no other tour is active
      if (isPageTourNeeded(pageId) && !activeTourId) {
        setActiveTour(pageId);
        setTourOpen(true);
      }
    }, delay);
    return () => clearTimeout(timer);
  }, [pageId, delay, isPageTourNeeded, activeTourId, setActiveTour]);

  const handleClose = useCallback(() => {
    setTourOpen(false);
    markPageTourCompleted(pageId);
    setActiveTour(null);
  }, [pageId, markPageTourCompleted, setActiveTour]);

  const handleFinish = useCallback(() => {
    setTourOpen(false);
    markPageTourCompleted(pageId);
    setActiveTour(null);
  }, [pageId, markPageTourCompleted, setActiveTour]);

  return (
    <>
      {children}
      <Tour open={tourOpen} onClose={handleClose} onFinish={handleFinish} steps={steps} />
    </>
  );
}
