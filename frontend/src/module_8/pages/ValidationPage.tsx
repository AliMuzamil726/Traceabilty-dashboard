import { GroupPage } from './GroupPage';

/** The rules that decide whether a form can be saved. */
export default function ValidationPage() {
  return (
    <GroupPage
      group="validation"
      title="Validation rules"
      description="What counts as an acceptable identity number, phone number or field size."
      notice={
        <p className="rounded-control bg-wheat-50 px-3 py-2 text-sm text-ink">
          These affect new entries only. A farmer or field already saved keeps its values even if
          they would no longer pass, so tightening a rule never invalidates work that is done.
        </p>
      }
    />
  );
}
