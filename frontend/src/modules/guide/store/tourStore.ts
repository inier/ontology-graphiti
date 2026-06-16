import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface TourState {
  /** Guide page: completed step indices */
  guideCompletedSteps: number[];
  /** Guide page: current active step index */
  guideCurrentStep: number;
  /** Guide page: whether the full tour has been finished */
  guideTourFinished: boolean;

  /** Per-page first-visit tracking: pageId -> completed */
  pageToursCompleted: Record<string, boolean>;

  /** Currently active tour ID (prevents multiple tours at once) */
  activeTourId: string | null;

  // Actions
  markGuideStepComplete: (step: number) => void;
  setGuideCurrentStep: (step: number) => void;
  finishGuideTour: () => void;
  markPageTourCompleted: (page: string) => void;
  setActiveTour: (tourId: string | null) => void;
  resetAllTours: () => void;
  resetGuideTour: () => void;
  isPageTourNeeded: (page: string) => boolean;
}

export const useTourStore = create<TourState>()(
  persist(
    (set, get) => ({
      guideCompletedSteps: [],
      guideCurrentStep: 0,
      guideTourFinished: false,
      pageToursCompleted: {},
      activeTourId: null,

      markGuideStepComplete: (step) =>
        set((s) => ({
          guideCompletedSteps: s.guideCompletedSteps.includes(step)
            ? s.guideCompletedSteps
            : [...s.guideCompletedSteps, step],
        })),

      setGuideCurrentStep: (step) => set({ guideCurrentStep: step }),

      finishGuideTour: () => set({ guideTourFinished: true }),

      markPageTourCompleted: (page) =>
        set((s) => ({
          pageToursCompleted: { ...s.pageToursCompleted, [page]: true },
        })),

      setActiveTour: (tourId) => set({ activeTourId: tourId }),

      resetAllTours: () =>
        set({
          guideCompletedSteps: [],
          guideCurrentStep: 0,
          guideTourFinished: false,
          pageToursCompleted: {},
          activeTourId: null,
        }),

      resetGuideTour: () =>
        set({
          guideCompletedSteps: [],
          guideCurrentStep: 0,
          guideTourFinished: false,
        }),

      isPageTourNeeded: (page) => !get().pageToursCompleted[page],
    }),
    { name: 'odap-tour-progress' },
  ),
);
