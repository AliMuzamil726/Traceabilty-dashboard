import { GroupPage } from './GroupPage';

/** Dashboard alert thresholds and the Harvest Radar benchmark yields. */
export default function AlertsPage() {
  return (
    <>
      <GroupPage
        group="alerts"
        title="Alerts and thresholds"
        description="How long something may sit before the dashboard calls it a problem."
        notice={
          <p className="rounded-control bg-forest-50 px-3 py-2 text-sm text-ink">
            Alerts are recalculated on every read, so a change here shows on the dashboard
            immediately. Nothing already recorded changes.
          </p>
        }
      />
      <div className="mt-6">
        <GroupPage
          group="radar"
          title="Harvest Radar benchmarks"
          description="The expected yields the radar compares a field against."
        />
      </div>
    </>
  );
}
