check "phase3_provider_apply_locked" {
  assert {
    condition     = var.provider_apply_authorized == false
    error_message = "WP22A Phase 3 cannot authorize Cloud.ru provider mutation."
  }
}

check "phase3_public_ingress_locked" {
  assert {
    condition     = var.public_ingress_enabled == false
    error_message = "WP22A Phase 3 cannot activate public DNS/IP/HTTPS ingress."
  }
}

check "phase3_zero_recurring_spend" {
  assert {
    condition     = var.authorized_recurring_rub == 0
    error_message = "Recurring infrastructure authorization must remain 0 RUB/month in Phase 3."
  }
}

check "phase3_product_activation_locked" {
  assert {
    condition     = var.public_multi_user_enabled == false && var.real_trading_enabled == false
    error_message = "Public multi-user or real trading activation is outside WP22A Phase 3 authority."
  }
}

locals {
  wp22a_phase3_authority = {
    provider                   = "Cloud.ru Evolution"
    source_only                = true
    provider_apply_authorized  = false
    public_ingress_enabled     = false
    authorized_recurring_rub   = 0
    public_multi_user_enabled  = false
    trading_methods_enabled    = false
    real_trading_enabled       = false
    protected_v9_entrypoint    = "app:app"
    wp23_unlocked              = false
  }
}

output "wp22a_phase3_authority" {
  description = "Non-secret source authority summary for deterministic review; creates no provider resources."
  value       = local.wp22a_phase3_authority
}
