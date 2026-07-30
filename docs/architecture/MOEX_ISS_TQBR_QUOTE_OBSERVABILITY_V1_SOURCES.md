# Official MOEX source notes for PR-91

The PR-91 telemetry boundary relies on the following public facts from Moscow Exchange documentation:

- ISS provides market and historical data over a web API;
- free access is delayed, while real-time access requires subscription;
- public/guest market data may be delayed by 15 minutes;
- these limits must remain explicit in operational metadata and must not be converted into a real-time guarantee.

This file contains no copied market values, instrument identifiers, credentials, account data or raw upstream payload.
