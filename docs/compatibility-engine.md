# Compatibility engine

The engine accepts a validated device/part fact set and returns independent checks. Each check has `pass`, `conflict` or `unknown`, required and observed values, an explanation and source/fact IDs.

Current checks:

- exact laptop and exact part identity;
- DDR generation;
- physical form factor;
- proposed capacity against documented system and explicit per-module limits;
- confirmed free slots and documented sockets;
- ECC, voltage and buffering when both sides are documented;
- speed/profile, where a higher advertised rate alone is not treated as a conflict;
- other documented restrictions.

Overall state is:

```text
any critical conflict                  → CONFLICT_FOUND
otherwise any critical unknown        → NEEDS_INFORMATION
otherwise                             → MATCHES_CHECKED_SPECIFICATIONS
```

`MANUFACTURER-LISTED` is a separate candidate property, not a guarantee. A listed part can still have an unresolved installed configuration. Missing data never becomes pass, and total capacity is never inferred by dividing a system maximum by slot count.
