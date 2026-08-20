variable "provider_apply_authorized" {
  description = "Phase-4 provider mutation gate. WP22A Phase 3 must remain false."
  type        = bool
  default     = false

  validation {
    condition     = var.provider_apply_authorized == false
    error_message = "Provider apply is locked until the separately accepted WP22A Phase-4 privileged boundary and OWNER/provider authorization."
  }
}

variable "public_ingress_enabled" {
  description = "Public DNS/IP/HTTPS activation gate. WP22A Phase 3 must remain false."
  type        = bool
  default     = false

  validation {
    condition     = var.public_ingress_enabled == false
    error_message = "Public ingress remains locked until WP22A public-hosted acceptance authority."
  }
}

variable "authorized_recurring_rub" {
  description = "Current OWNER-authorized recurring infrastructure spend in RUB/month."
  type        = number
  default     = 0

  validation {
    condition     = var.authorized_recurring_rub == 0
    error_message = "WP22A Phase 3 source work is authorized at 0 RUB/month only."
  }
}

variable "public_multi_user_enabled" {
  description = "Product activation gate mirrored from the accepted application boundary."
  type        = bool
  default     = false

  validation {
    condition     = var.public_multi_user_enabled == false
    error_message = "PUBLIC_MULTI_USER_ENABLED remains false until its owning acceptance gate."
  }
}

variable "real_trading_enabled" {
  description = "Real broker execution gate mirrored from the protected product boundary."
  type        = bool
  default     = false

  validation {
    condition     = var.real_trading_enabled == false
    error_message = "REAL_TRADING_ENABLED remains false; WP22A grants no broker-write authority."
  }
}
