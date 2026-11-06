# ADR-GMS-001 — Optional extra with two gates

```toml
kind = "adr"
id = "ADR-GMS-001"
status = "accepted"
owner = "Claude"
specs = ["docs/specs/GMS-001.md"]
```

GMS uses paid API keys, so BATON keeps it out of the default path. `cryptography` stays an optional extra to preserve the standard-library base install. CI installs it so credential tests run instead of skipping.

Two gates stay separate. `--enable-gms` is an explicit decision per command, and the `/gms` switch is durable operator state. Requiring both means neither a stale switch nor a mistyped flag alone can send a request.

The subscription-only rule still governs model calls for Claude and Codex. GMS is its one named exception, and agents do not make real GMS calls for testing or verification.
