# Omni-CIO V10 — Public Product Brand Identity

Status: **OWNER-APPROVED DECISION / PROPOSED FOR ACCEPTED `main`**  
Decision date: **2026-09-01**  
Execution unit: **FOCUSED_CHANGE — documentation / product identity**

Machine-readable companion:

`V10_PUBLIC_PRODUCT_BRAND_IDENTITY_CONTRACT.json`

## 1. Decision

The public product brand is:

**KURS**

The underlying system/platform name remains:

**Omni-CIO**

Canonical relationship:

`KURS = public product brand`  
`Omni-CIO = system/platform/engineering identity`

KURS does not replace or rename Omni-CIO as the technical system.

## 2. Meaning

The brand name intentionally carries a short double meaning suitable for the investment product:

- `курс` as the price/rate of a security or currency;
- `курс` as direction, strategy and a chosen path.

The public brand therefore represents an investment product that helps a USER understand the market, choose direction and maintain disciplined capital governance, while Omni-CIO remains the system that provides the underlying deterministic Core, portfolio/risk/research/decision/recovery and later gated execution capabilities.

## 3. Technical namespace boundary

This branding decision does **not** authorize a mass technical rename.

The following remain Omni-CIO technical identifiers unless a later focused migration proves a concrete need:

- repository `MishaGameHacking/omni-cio-gateway`;
- `OmniCIOUserAccount`, tenant/session and API contracts;
- Python/JavaScript package/module names;
- environment-variable prefixes and secret names;
- database schemas/migrations;
- Cloudflare Worker/service identifiers;
- CI workflow/check names;
- V9/V10 recovery assets, release provenance and historical evidence.

Do not duplicate the product into a second KURS stack. KURS is the public brand of the same one Omni-CIO product line.

## 4. User-facing presentation boundary

Future authorized user-facing branding may present `KURS` as the primary product name and may identify the technical platform as `powered by Omni-CIO` or equivalent wording where useful.

This decision alone does not authorize visual redesign, logo work, domain/DNS mutation, production deployment or a second Web application. The prepared `WEB-VISUAL-INTEGRATED` update remains separately OWNER-locked by its existing START gate.

## 5. Domain and legal boundary

The KURS brand decision does not claim that any specific domain is available and does not claim trademark exclusivity or legal clearance.

Before a public commercial brand launch, trademark filing, paid marketing or irreversible domain/brand spend, perform the applicable Russian-market name/trademark/domain clearance under the existing legal-gate process. A domain choice is a separate OWNER decision and must not be guessed from this document.

## 6. Security / authority / activation effect

This decision changes product naming only. It does not change:

- `PUBLIC_MULTI_USER_ENABLED=false` current fail-closed state;
- Telegram Login / VK ID external provider gates;
- tenant/session/RLS authority;
- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- transfer/withdrawal/margin/leverage/uncovered-short prohibitions;
- protected V9 `app:app` recovery boundary;
- Cloudflare production cutover requirements;
- WP23+ lock.

A KURS name, logo, domain, GitHub merge or Cloudflare deployment is never broker-submit or Real-money authorization.

## 7. Progress / release effect

This is a focused identity/documentation decision. It does not advance V10 implementation percentage, mark CF-D production acceptance GREEN, activate public users, or replace `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` as dynamic progress authority.

Current production/release blockers must be resolved through their existing owning gates independently of this brand decision.

## 8. Acceptance law

This decision becomes accepted repository authority only after the focused branch completes the normal exact-head review/CI lifecycle and is squash-merged into protected `main`, followed by the applicable exact-new-main post-merge verification.
