type FeaturePlaceholderProps = {
  title: string;
  description: string;
};

export function FeaturePlaceholder({
  title,
  description,
}: FeaturePlaceholderProps) {
  return (
    <section className="flex min-h-[50vh] items-center justify-center">
      <div className="max-w-2xl rounded-[2rem] border border-dashed border-border bg-canvas/70 p-10 text-center shadow-inner">
        <p className="mb-3 font-display text-3xl">{title}</p>
        <p className="text-base leading-7 text-stone-700">{description}</p>
      </div>
    </section>
  );
}
