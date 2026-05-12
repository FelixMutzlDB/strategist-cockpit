/**
 * T-212: shared chip-multi-select for qualitative outcome tags.
 *
 * Used across all five activity categories (T-212 wires only the customer
 * Engagements page; future T-219 / T-221 / T-222 work reuses this same
 * component). Tags are a closed 10-value enum mirrored from the Pydantic
 * `IMPACT_TAGS` literal in src/backend/schemas.py.
 *
 * Colour hints group tags by family:
 *  - access plays (intros/escalations) ............ blue
 *  - account-progress plays (POC/competitor/UCO).. emerald
 *  - product / roadmap plays ..................... violet
 *  - reach / enablement plays .................... amber
 */
import { Badge } from "@/components/ui/badge";

export const IMPACT_TAGS = [
  "blocker_cleared",
  "exec_intro",
  "cxo_engaged",
  "poc_unlocked",
  "competitor_displaced",
  "uco_advanced",
  "product_introduced",
  "roadmap_influenced",
  "evangelism_landed",
  "team_enabled",
] as const;

export type ImpactTag = (typeof IMPACT_TAGS)[number];

const TAG_LABEL: Record<ImpactTag, string> = {
  blocker_cleared: "Blocker cleared",
  exec_intro: "Exec intro",
  cxo_engaged: "CXO engaged",
  poc_unlocked: "POC unlocked",
  competitor_displaced: "Competitor displaced",
  uco_advanced: "UCO advanced",
  product_introduced: "Product introduced",
  roadmap_influenced: "Roadmap influenced",
  evangelism_landed: "Evangelism landed",
  team_enabled: "Team enabled",
};

// Tailwind colour hints per tag family. Picker uses selected/unselected
// states; readers (chip render in row/dialog) use the selected style.
const TAG_FAMILY_COLOR: Record<ImpactTag, { on: string; off: string }> = {
  blocker_cleared: { on: "bg-blue-100 text-blue-700", off: "bg-blue-50 text-blue-500" },
  exec_intro: { on: "bg-blue-100 text-blue-700", off: "bg-blue-50 text-blue-500" },
  cxo_engaged: { on: "bg-blue-100 text-blue-700", off: "bg-blue-50 text-blue-500" },
  poc_unlocked: { on: "bg-emerald-100 text-emerald-700", off: "bg-emerald-50 text-emerald-500" },
  competitor_displaced: { on: "bg-emerald-100 text-emerald-700", off: "bg-emerald-50 text-emerald-500" },
  uco_advanced: { on: "bg-emerald-100 text-emerald-700", off: "bg-emerald-50 text-emerald-500" },
  product_introduced: { on: "bg-violet-100 text-violet-700", off: "bg-violet-50 text-violet-500" },
  roadmap_influenced: { on: "bg-violet-100 text-violet-700", off: "bg-violet-50 text-violet-500" },
  evangelism_landed: { on: "bg-amber-100 text-amber-700", off: "bg-amber-50 text-amber-500" },
  team_enabled: { on: "bg-amber-100 text-amber-700", off: "bg-amber-50 text-amber-500" },
};

export function impactTagLabel(tag: string): string {
  return TAG_LABEL[tag as ImpactTag] ?? tag;
}

export function impactTagColorClass(tag: string): string {
  return TAG_FAMILY_COLOR[tag as ImpactTag]?.on ?? "bg-gray-100 text-gray-700";
}

interface ImpactTagPickerProps {
  value: ImpactTag[];
  onChange: (next: ImpactTag[]) => void;
  // Optional: dim tags that don't typically apply to this category. The
  // backend doesn't reject them (soft policy), but the UI signals it.
  preferredTags?: readonly ImpactTag[];
}

export function ImpactTagPicker({ value, onChange, preferredTags }: ImpactTagPickerProps) {
  const selected = new Set(value);
  const toggle = (tag: ImpactTag) => {
    const next = new Set(selected);
    if (next.has(tag)) next.delete(tag);
    else next.add(tag);
    // Preserve canonical order so backend doesn't see permutations as diffs.
    onChange(IMPACT_TAGS.filter((t) => next.has(t)));
  };
  const isPreferred = (tag: ImpactTag) => !preferredTags || preferredTags.includes(tag);

  return (
    <div className="flex flex-wrap gap-1.5">
      {IMPACT_TAGS.map((tag) => {
        const on = selected.has(tag);
        const palette = TAG_FAMILY_COLOR[tag];
        const offClass = isPreferred(tag) ? palette.off : "bg-gray-50 text-gray-400";
        return (
          <button
            key={tag}
            type="button"
            onClick={() => toggle(tag)}
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium border transition-colors ${
              on ? `${palette.on} border-transparent` : `${offClass} border-input hover:bg-accent`
            }`}
            aria-pressed={on}
            title={
              isPreferred(tag)
                ? TAG_LABEL[tag]
                : `${TAG_LABEL[tag]} — uncommon for this category`
            }
          >
            {TAG_LABEL[tag]}
          </button>
        );
      })}
    </div>
  );
}

/** Read-only chip render — used in table rows and view dialogs. */
export function ImpactTagChips({ tags }: { tags: string[] }) {
  if (!tags || tags.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <Badge key={tag} className={impactTagColorClass(tag)}>
          {impactTagLabel(tag)}
        </Badge>
      ))}
    </div>
  );
}
