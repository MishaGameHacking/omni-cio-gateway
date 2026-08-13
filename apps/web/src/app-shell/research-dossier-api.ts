import type { ResearchDossierCollectionView } from "./research-dossier-contracts";

export async function readResearchDossiers(): Promise<ResearchDossierCollectionView> {
  const response = await fetch("/api/v10/web/research-dossiers", {
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`WP20_RESEARCH_API_${response.status}`);
  return (await response.json()) as ResearchDossierCollectionView;
}
