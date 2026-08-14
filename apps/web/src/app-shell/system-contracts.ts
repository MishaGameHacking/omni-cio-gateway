import type { OperationalState } from "../design-system/contracts";

export type SystemAvailability =
  | "AVAILABLE"
  | "NOT_CONFIGURED"
  | "NOT_AVAILABLE"
  | "LOCKED_FUTURE_WP";

export interface SystemServiceView {
  id: string;
  label: string;
  state: OperationalState;
  availability: SystemAvailability;
  detail: string;
  observed_at: string | null;
}

export interface SystemStatusView {
  schema_version: "1.0.0";
  generated_at: string;
  state: OperationalState;
  release: {
    release: string;
    git_sha: string | null;
    git_sha_source: string;
    last_deploy_at: string | null;
    last_deploy_source: string;
  };
  database: {
    state: OperationalState;
    availability: SystemAvailability;
    current_migration: string | null;
    expected_migration: string | null;
    migration_count: number;
    exact_migration_state: boolean;
  };
  backup: {
    state: OperationalState;
    availability: SystemAvailability;
    last_success_at: string | null;
    rpo_minutes: number;
    rto_minutes: number;
  };
  resources: {
    disk: {
      state: OperationalState;
      availability: SystemAvailability;
      free_gib: number | null;
      free_percent: number | null;
      warning_threshold_gib: number;
      block_threshold_gib: number;
    };
    temperature: {
      state: OperationalState;
      availability: SystemAvailability;
      gpu_c: number | null;
      limit_c: number;
    };
  };
  safety: {
    mode: "READ_ONLY_DIAGNOSTIC";
    real_trading_enabled: boolean;
    trading_methods: false;
    broker_write_authority: false;
    public_ingress: false;
    watchtower_enabled: boolean;
  };
  services: SystemServiceView[];
  recent_jobs: Array<{
    job_type: string;
    state: string;
    attempts: number;
    max_attempts: number;
    error_class: string | null;
    observed_at: string | null;
  }>;
  recent_errors: Array<{
    job_type: string;
    state: string;
    error_class: string;
    observed_at: string | null;
  }>;
  limits: {
    recent_jobs: number;
    recent_errors: number;
  };
}
