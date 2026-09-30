export default function Panel({ title, subtitle, right, children, className = "" }) {
  return (
    <section
      className={`bg-soc-panel border border-soc-border rounded-xl p-4 ${className}`}
    >
      {(title || right) && (
        <div className="flex items-start justify-between mb-3">
          <div>
            {title && (
              <h2 className="text-sm font-semibold tracking-wide text-soc-text uppercase">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="text-xs text-soc-muted mt-0.5">{subtitle}</p>
            )}
          </div>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}
