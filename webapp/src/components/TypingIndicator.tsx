export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="size-1.5 rounded-full bg-[var(--vz-muted)]"
          style={{ animation: "vz-blink 1.2s infinite", animationDelay: `${i * 0.2}s` }}
        />
      ))}
    </div>
  );
}
