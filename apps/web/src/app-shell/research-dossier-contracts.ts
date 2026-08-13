export type ResearchViewState = "EMPTY" | "PARTIAL" | "READY";
export type ResearchDossierState = "PARTIAL" | "READY";
export type ResearchFreshness = "FRESH" | "STALE" | "UNKNOWN";
export type ResearchConfidence = "SUPPORTED" | "CONTEXT_ONLY" | "STALE" | "CONTRADICTED" | "UNKNOWN";

export interface ResearchSourceView {
  provider: string;
  source_class: string;
  authority: string;
  source_id: string;
  location_text: string | null;
  href: string | null;
  retrieved_at: string;
  published_at: string | null;
  effective_at: string | null;
}

export interface ResearchFactView {
  record_sha256: string;
  fact_type: string;
  fact_key: string;
  value: { type: string; canonical: string; currency: string | null };
  material: boolean;
  evidence_use: "decision_grade" | "context_only";
  freshness: ResearchFreshness;
  confidence_state: ResearchConfidence;
  event_at: string;
  source: ResearchSourceView;
}

export interface ResearchContradictionView {
  fact_key: string;
  comparison_period: string | null;
  severity: string;
  record_sha256s: string[];
  distinct_values: string[];
  unresolved: boolean;
}

export interface ResearchUnknownView {
  requirement_id: string;
  fact_type: string;
  importance: string;
  reason: string;
}

export interface ResearchRelatedLinkView {
  kind: "credit" | "fund";
  label: string;
  path: string;
}

export type ResearchAiSummaryView =
  | { state: "UNAVAILABLE" }
  | {
      state: "AVAILABLE";
      kind: "AI_GENERATED_NON_AUTHORITATIVE";
      authoritative: false;
      dossier_sha256: string;
      generated_at: string;
      text: string;
    };

export interface ResearchDossierView {
  dossier_sha256: string;
  state: ResearchDossierState;
  assessed_at: string;
  decision_ready: boolean;
  strong_recommendation_allowed: boolean;
  identity: {
    candidate_id: string;
    instrument_uid: string;
    instrument_type: string;
    issuer_identity_state: "SOURCE_BOUND" | "UNKNOWN";
  };
  facts: ResearchFactView[];
  timeline: Array<{
    event_at: string;
    record_sha256: string;
    fact_key: string;
    value: { type: string; canonical: string; currency: string | null };
    source_class: string;
  }>;
  contradictions: ResearchContradictionView[];
  unknowns: ResearchUnknownView[];
  related_links: ResearchRelatedLinkView[];
  ai_summary: ResearchAiSummaryView;
  counts: {
    facts: number;
    rejected_records_hidden: number;
    contradictions: number;
    unknowns: number;
    stale_facts: number;
    unknown_freshness_facts: number;
  };
}

export interface ResearchDossierCollectionView {
  schema_version: "1.0.0";
  generated_at: string;
  state: ResearchViewState;
  counts: { dossiers: number; partial: number };
  dossiers: ResearchDossierView[];
}
