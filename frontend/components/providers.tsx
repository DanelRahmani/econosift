'use client';

import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/queryClient';
import { LearningProvider } from '@/lib/learningContext';

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <LearningProvider>
        {children}
      </LearningProvider>
    </QueryClientProvider>
  );
}
