variable "cloudflare_account_id" {
  description = "Cloudflare account identifier supplied only at protected apply time."
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone identifier supplied only at protected apply time."
  type        = string
  sensitive   = true
}

variable "hostname" {
  description = "Reviewed OWNER Web hostname, for example omni.example.com."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$", var.hostname))
    error_message = "hostname must be a lowercase DNS hostname"
  }
}

variable "team_name" {
  description = "Cloudflare Zero Trust organization/team name without .cloudflareaccess.com."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", var.team_name))
    error_message = "team_name must be a lowercase DNS label"
  }
}

variable "tunnel_name" {
  description = "Stable Cloudflare Tunnel name."
  type        = string
  default     = "omni-cio-v10-owner-web"

  validation {
    condition     = length(var.tunnel_name) >= 3 && length(var.tunnel_name) <= 64
    error_message = "tunnel_name length must be between 3 and 64 characters"
  }
}
