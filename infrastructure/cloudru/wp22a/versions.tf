terraform {
  required_version = ">= 1.5.0, < 2.0.0"

  required_providers {
    cloudru = {
      source  = "cloud-ru/cloudru"
      version = "~> 2.0.0"
    }
  }
}
