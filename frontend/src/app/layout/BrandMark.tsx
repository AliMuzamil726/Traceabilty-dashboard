/** SAWiE mark (the S, leaf and trace motif) on a white tile so it reads on any background. */
export function BrandMark({ size = 32 }: { size?: number }) {
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center overflow-hidden rounded-[9px] bg-white"
      style={{ width: size, height: size }}
      aria-hidden
    >
      <img src="/sawie-mark.png" alt="" width={size} height={size} className="h-full w-full object-contain" />
    </span>
  );
}

/** The full SAWiE Fibre Traceability logo. */
export function BrandLogo({ className }: { className?: string }) {
  return <img src="/sawie-logo.png" alt="SAWiE Fibre Traceability" className={className} />;
}
