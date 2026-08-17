terraform {
  required_version = "1.12.5"

  required_providers {
    cloudflare = {
      source  = "registry.terraform.io/cloudflare/cloudflare"
      version = "5.22.0"
    }
  }
}

provider "cloudflare" {}

data "cloudflare_zero_trust_organization" "existing" {
  account_id = var.cloudflare_account_id
}

data "cloudflare_zero_trust_access_identity_providers" "existing" {
  account_id = var.cloudflare_account_id
}

locals {
  cloudflare_owner_idps = [
    for idp in data.cloudflare_zero_trust_access_identity_providers.existing.result : idp
    if idp.type == "cloudflare" && try(idp.config.restrict_to_account_members, false)
  ]
  cloudflare_owner_idp_id = one(local.cloudflare_owner_idps).id
}

check "existing_zero_trust_organization_is_hardened" {
  assert {
    condition = (
      data.cloudflare_zero_trust_organization.existing.auth_domain == "${var.team_name}.cloudflareaccess.com" &&
      data.cloudflare_zero_trust_organization.existing.allow_authenticate_via_warp == false &&
      data.cloudflare_zero_trust_organization.existing.deny_unmatched_requests == true
    )
    error_message = "Existing Cloudflare Zero Trust organization must match the reviewed team name, disable WARP authentication, and deny unmatched requests before WP22A apply."
  }
}

check "single_restricted_cloudflare_identity_provider" {
  assert {
    condition     = length(local.cloudflare_owner_idps) == 1
    error_message = "Exactly one Cloudflare identity provider restricted to account members must already exist before WP22A apply."
  }
}

resource "cloudflare_zero_trust_tunnel_cloudflared" "omni_cio" {
  account_id = var.cloudflare_account_id
  name       = var.tunnel_name
  config_src = "cloudflare"
}

resource "cloudflare_zero_trust_access_policy" "owner" {
  account_id       = var.cloudflare_account_id
  name             = "Omni-CIO exact Cloudflare account member"
  decision         = "allow"
  session_duration = "24h"

  include = [{
    cloudflare_account_member = {
      account_id = var.cloudflare_account_id
    }
  }]

  require = [{
    login_method = {
      id = local.cloudflare_owner_idp_id
    }
  }]
}

resource "cloudflare_zero_trust_access_application" "omni_cio" {
  account_id                  = var.cloudflare_account_id
  name                        = "Omni-CIO OWNER Web"
  domain                      = var.hostname
  type                        = "self_hosted"
  allowed_idps                = [local.cloudflare_owner_idp_id]
  auto_redirect_to_identity   = true
  allow_authenticate_via_warp = false
  allow_iframe                = false
  app_launcher_visible        = false
  enable_binding_cookie       = true
  http_only_cookie_attribute  = true
  options_preflight_bypass    = false
  path_cookie_attribute       = false
  session_duration            = "24h"

  policies = [{
    id         = cloudflare_zero_trust_access_policy.owner.id
    precedence = 1
  }]
}

resource "cloudflare_zero_trust_tunnel_cloudflared_config" "omni_cio" {
  account_id = var.cloudflare_account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.omni_cio.id

  config = {
    ingress = [
      {
        hostname = var.hostname
        service  = "http://127.0.0.1:8765"
        origin_request = {
          http_host_header = var.hostname
          access = {
            required  = true
            team_name = var.team_name
            aud_tag   = [cloudflare_zero_trust_access_application.omni_cio.aud]
          }
        }
      },
      {
        service = "http_status:404"
      }
    ]
  }
}

resource "cloudflare_dns_record" "omni_cio" {
  zone_id = var.cloudflare_zone_id
  name    = var.hostname
  type    = "CNAME"
  content = "${cloudflare_zero_trust_tunnel_cloudflared.omni_cio.id}.cfargotunnel.com"
  proxied = true
  ttl     = 1
  comment = "Omni-CIO V10 WP22A clientless OWNER Web"

  # The hostname is the external reachability switch. Keep it last on apply and
  # first on destroy: Access and cloudflared's Access-validated ingress must
  # already exist before DNS can publish the route.
  depends_on = [
    cloudflare_zero_trust_access_application.omni_cio,
    cloudflare_zero_trust_tunnel_cloudflared_config.omni_cio,
  ]
}

output "access_application_aud" {
  value = cloudflare_zero_trust_access_application.omni_cio.aud
}

output "tunnel_id" {
  value = cloudflare_zero_trust_tunnel_cloudflared.omni_cio.id
}
