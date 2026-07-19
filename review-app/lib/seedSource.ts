export interface CatalogEntry {
  id: string;
  section: string;
  tag: string;
  en: string;
  fr: string;
  status: string;
}

export interface SourceRow {
  id: string;
  page: string;
  english: string;
  liveFrench: string | null;
  suggestedFrench: string;
}

const TAG_RE = /<[^>]+>/g;
const WS_RE = /\s+/g;
const ENTITY_RE = /&amp;|&lt;|&gt;|&quot;|&#39;/g;
const ENTITIES: Record<string, string> = {
  "&amp;": "&",
  "&lt;": "<",
  "&gt;": ">",
  "&quot;": '"',
  "&#39;": "'",
};

/** Plain-text form of a (possibly markup-bearing) catalog string: tags
 * stripped, entities decoded, whitespace runs collapsed. Mirrors
 * scripts/build_artifact.py's plain() so review-app text matches what the
 * reviewer previously saw in the artifact. */
export function plainText(s: string): string {
  const noTags = s.replace(TAG_RE, "");
  const decoded = noTags.replace(ENTITY_RE, (m) => ENTITIES[m]);
  return decoded.replace(WS_RE, " ").trim();
}

export function derivePage(id: string): string {
  const idx = id.indexOf(" § ");
  return idx === -1 ? id : id.slice(0, idx);
}

export function deriveSourceRows(
  catalogEntries: CatalogEntry[],
  liveFrench: Record<string, string>
): SourceRow[] {
  return catalogEntries.map((entry) => {
    const live = liveFrench[entry.id];
    return {
      id: entry.id,
      page: derivePage(entry.id),
      english: plainText(entry.en),
      liveFrench: live ? plainText(live) : null,
      suggestedFrench: plainText(entry.fr),
    };
  });
}
