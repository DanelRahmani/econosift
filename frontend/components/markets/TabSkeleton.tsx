export function TabSkeleton() {
  return (
    <div className="space-y-4 py-4">
      <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded animate-pulse w-1/3" />
      <div className="h-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
      <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
    </div>
  );
}
