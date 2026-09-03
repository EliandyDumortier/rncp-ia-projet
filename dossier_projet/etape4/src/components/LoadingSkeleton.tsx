export function LoadingSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Loading recommendations"
      className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4"
    >
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-white rounded-3xl overflow-hidden shadow-soft border border-slate-100">
          <div className="aspect-[2/3] bg-slate-200 animate-pulse-soft" />
          <div className="p-3">
            <div className="h-4 bg-slate-200 rounded animate-pulse-soft mb-2" />
            <div className="h-3 bg-slate-100 rounded animate-pulse-soft w-2/3" />
          </div>
        </div>
      ))}
    </div>
  );
}
