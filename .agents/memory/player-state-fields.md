---
name: Player state fields
description: Rule for adding persistent mutable settings to CapeVerse player records
---

Any new mutable player setting must be represented in new-account defaults and permitted by the guarded player-update path.

**Why:** A feature can appear to save successfully while silently discarding its state if only the UI and database reader are updated.

**How to apply:** When adding player-level state, verify both new and existing accounts: define a safe default, allow guarded updates, and test persistence by reading the record back.