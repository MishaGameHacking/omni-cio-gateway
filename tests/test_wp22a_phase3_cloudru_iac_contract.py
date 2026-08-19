from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
IAC = ROOT / "infrastructure" / "cloudru" / "wp22a"


def _read(name: str) -> str:
    return (IAC / name).read_text(encoding="utf-8")


def test_phase3_cloudru_iac_files_exist() -> None:
    assert (IAC / "README.md").is_file()
    assert (IAC / "versions.tf").is_file()
    assert (IAC / "variables.tf").is_file()
    assert (IAC / "safety.tf").is_file()


def test_official_cloudru_provider_family_is_source_controlled() -> None:
    versions = _read("versions.tf")
    assert 'source  = "cloud-ru/cloudru"' in versions
    assert 'version = "~> 2.0.0"' in versions


def test_phase3_mutation_public_cost_and_product_gates_default_closed() -> None:
    variables = _read("variables.tf")
    safety = _read("safety.tf")

    for variable in (
        "provider_apply_authorized",
        "public_ingress_enabled",
        "public_multi_user_enabled",
        "real_trading_enabled",
    ):
        block = re.search(
            rf'variable\s+"{variable}"\s*\{{(?P<body>.*?)\n\}}',
            variables,
            flags=re.DOTALL,
        )
        assert block, f"missing fail-closed variable: {variable}"
        assert re.search(r"\bdefault\s*=\s*false\b", block.group("body"))

    spend = re.search(
        r'variable\s+"authorized_recurring_rub"\s*\{(?P<body>.*?)\n\}',
        variables,
        flags=re.DOTALL,
    )
    assert spend
    assert re.search(r"\bdefault\s*=\s*0\b", spend.group("body"))

    assert 'protected_v9_entrypoint    = "app:app"' in safety
    assert "trading_methods_enabled    = false" in safety
    assert "wp23_unlocked              = false" in safety


def test_phase3_root_has_no_provider_credentials_or_mutating_blocks() -> None:
    terraform = "\n".join(path.read_text(encoding="utf-8") for path in IAC.glob("*.tf"))

    # This first focused increment is intentionally a dormant contract root.
    assert re.search(r'^\s*resource\s+"', terraform, flags=re.MULTILINE) is None
    assert re.search(r'^\s*data\s+"', terraform, flags=re.MULTILINE) is None
    assert re.search(r'^\s*provider\s+"', terraform, flags=re.MULTILINE) is None

    forbidden_value_fields = (
        "auth_secret",
        "auth_key_id",
        "project_id =",
        "api_token",
        "access_token",
        "private_key",
        "broker_token",
        "telegram_token",
        "vk_token",
    )
    lowered = terraform.lower()
    for forbidden in forbidden_value_fields:
        assert forbidden not in lowered


def test_terraform_runtime_state_and_inputs_are_gitignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for rule in (".terraform/", "*.tfstate", "*.tfstate.*", "*.tfvars", "*.tfvars.json"):
        assert rule in gitignore


def test_phase3_readme_does_not_claim_provider_apply_or_acceptance() -> None:
    readme = _read("README.md")
    assert "does not" in readme.lower()
    assert "provider_apply_authorized = false" in readme
    assert "authorized_recurring_rub = 0" in readme
    assert "not Phase-3 acceptance by itself" in readme
