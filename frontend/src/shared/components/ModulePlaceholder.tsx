import { Construction } from 'lucide-react';
import { PageContainer } from '@/app/layout/PageContainer';
import { PIPELINE, statusLabel } from '@/app/moduleRegistry';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { StatusPill } from '@/design-system/components/Badge';
import { PageHeader } from '@/design-system/components/PageHeader';
import type { ModuleMeta } from '@/shared/types';
import { PipelineTracker } from './PipelineTracker';

/** Shown for modules that are not built yet: purpose, pipeline position and status. */
export function ModulePlaceholder({ meta }: { meta: ModuleMeta }) {
  const label = statusLabel(meta);
  const index = PIPELINE.findIndex((m) => m.number === meta.number);
  const previous = index > 0 ? PIPELINE[index - 1] : undefined;
  const next = index >= 0 && index < PIPELINE.length - 1 ? PIPELINE[index + 1] : undefined;

  const position =
    meta.pipelineStage === null
      ? 'Reads from every stage of the pipeline.'
      : [
          `Stage ${meta.pipelineStage} of ${PIPELINE.length}.`,
          previous ? `Receives work from ${previous.name}.` : 'This is where every trace starts.',
          next ? `Hands over to ${next.name}.` : 'This is the end of the chain.',
        ].join(' ');

  return (
    <PageContainer>
      <PageHeader
        title={meta.name}
        subtitle={meta.purpose}
        breadcrumb={[{ label: 'Home', to: '/' }, { label: meta.name }]}
        actions={label ? <StatusPill tone={label === 'In build' ? 'accent' : 'neutral'}>{label}</StatusPill> : undefined}
      />
      <Card className="mt-6" padding="lg">
        <div className="flex items-start gap-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-card bg-wheat-50 text-wheat-600" aria-hidden>
            <Construction className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-md font-semibold text-ink">
              {label === 'In build' ? 'This module is being built now' : 'This module is planned'}
            </h2>
            <p className="mt-1 max-w-[70ch] text-base text-muted">{position}</p>
          </div>
        </div>
      </Card>
      <section className="mt-8" aria-labelledby="pipeline-heading">
        <SectionHeader id="pipeline-heading" title="Where it sits in the pipeline" className="mb-4" />
        <PipelineTracker highlight={meta.number} compact />
      </section>
    </PageContainer>
  );
}
