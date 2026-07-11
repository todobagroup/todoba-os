# TODOBA CAPABILITY CATALOG

**Document Type:** Human-readable capability registry
**Repository Role:** Current capability source of truth
**Status:** Active
**Maintainer:** CTO 10
**Last Updated:** 2026-07-10

---

## 1. PURPOSE

This catalog records what TODOBA can currently do, where each capability lives, its maturity, and what must be built next.

It exists to prevent:

* rebuilding capabilities that already exist;
* forgetting previous work;
* confusing files with completed organizational capabilities;
* allowing conversations to become the source of truth;
* adding features without understanding the current system.

> **The repository is the source of truth. Memory is only a helper.**
> *(Repository là nguồn sự thật. Trí nhớ chỉ là công cụ hỗ trợ.)*

---

## 2. CAPABILITY STATUS DEFINITIONS

| Status        | Meaning                                                                                             |
| ------------- | --------------------------------------------------------------------------------------------------- |
| `CONCEPT`     | The capability has been defined but has no working implementation.                                  |
| `FOUNDATION`  | Core models, contracts, or structure exist.                                                         |
| `PROTOTYPE`   | A limited implementation works in controlled tests.                                                 |
| `OPERATIONAL` | The capability performs its intended job reliably.                                                  |
| `INTEGRATED`  | The capability is connected to the wider TODOBA system.                                             |
| `HARDENED`    | The capability has safety controls, observability, failure handling, and operational documentation. |

A file existing does not automatically mean that a capability is operational.

---

## 3. ORGANIZATIONAL CAPABILITY MAP

TODOBA develops through the following capability chain:

```text
Identity
   ↓
Memory
   ↓
Knowledge
   ↓
Understanding
   ↓
Decision
   ↓
Planning
   ↓
Workers
   ↓
Organization
   ↓
Evolution
```

Current development is concentrated on:

1. Memory and Brain foundations.
2. Trading execution foundations.
3. Telegram as an external input channel.
4. MT5 as an execution environment.
5. Connecting isolated components into one controlled workflow.

---

# 4. FOUNDATION CAPABILITIES

## CAP-FND-001 — Organizational Identity

**Status:** `FOUNDATION`

**Purpose:**
Preserve the permanent identity, purpose, principles, Founder role, CTO role, and culture of TODOBA.

**Primary locations:**

```text
constitution.md
docs/Foundation/TODOBA.md
docs/Foundation/FOUNDER.md
docs/Foundation/CTO.md
docs/Foundation/CULTURE.md
docs/Foundation/COVENANT.md
backend/brain/identity.md
```

**Current abilities:**

* Defines TODOBA as a Living AI Organization.
* Preserves the North Star.
* Defines Founder and CTO responsibilities.
* Preserves long-term architectural principles.
* Provides stable constraints for future decisions.

**Current limitations:**

* Foundation documents are not automatically loaded into every Brain operation.
* No automated consistency check currently verifies new decisions against the Constitution.

**Next maturity target:** `INTEGRATED`

---

## CAP-FND-002 — Repository Boot Context

**Status:** `FOUNDATION`

**Purpose:**
Allow a new CTO session or operator to reconstruct the project state from repository documents instead of conversational memory.

**Primary locations:**

```text
docs/000_BOOT.md
docs/CTO_CONTEXT.md
docs/CTO_LOG.md
docs/SPRINTS.md
docs/TODOBA_KERNEL.md
docs/README.md
```

**Current abilities:**

* Provides a documented project boot path.
* Records strategic and operational context.
* Preserves sprint-level direction.
* Reduces dependence on one conversation.

**Current limitations:**

* Project state may become stale if documents are not updated after implementation.
* Boot documents do not yet validate themselves against the actual code tree.

**Next maturity target:** `INTEGRATED`

---

## CAP-FND-003 — Capability Governance

**Status:** `FOUNDATION`

**Purpose:**
Maintain an explicit registry of TODOBA capabilities, maturity, ownership, dependencies, and next development targets.

**Primary locations:**

```text
docs/CAPABILITY_CATALOG.md
backend/brain/brain_capability_map.md
backend/brain/capability_template.md
```

**Current abilities:**

* Defines known organizational and technical capabilities.
* Distinguishes architectural intent from operational implementation.
* Supports reuse-before-rewrite decisions.
* Provides a human-readable system inventory.

**Current limitations:**

* No machine-readable capability registry has yet been confirmed.
* Capability status is not automatically derived from tests or runtime health.

**Next maturity target:** `INTEGRATED`

---

# 5. BRAIN CAPABILITIES

## CAP-BRN-001 — Experience Model

**Status:** `FOUNDATION`

**Purpose:**
Represent an event or experience received by TODOBA in a consistent form.

**Primary locations:**

```text
backend/brain/models/experience.py
backend/brain/memory/models/experience.py
```

**Current abilities:**

* Represents experiences as structured objects.
* Supports identity and timestamp fields.
* Can be consumed by Brain, Memory, and Planning components.

**Known architectural concern:**

There appear to be experience models in more than one location. These must be inspected before further expansion to avoid duplicated contracts.

**Next action:**

* Select one canonical Experience model.
* Migrate imports to the canonical model.
* Remove or deprecate duplicates safely.

**Next maturity target:** `INTEGRATED`

---

## CAP-BRN-002 — Meaning Extraction

**Status:** `PROTOTYPE`

**Purpose:**
Transform raw experience into information that has organizational meaning.

**Primary location:**

```text
backend/brain/meaning.py
```

**Current abilities:**

* Provides a beginning structure for interpreting experiences.
* Separates raw input from meaningful organizational experience.

**Current limitations:**

* Meaning rules remain limited.
* No confidence score or interpretation provenance has been confirmed.
* Not yet connected to all external input channels.

**Next maturity target:** `INTEGRATED`

---

## CAP-BRN-003 — Memory Engine

**Status:** `PROTOTYPE`

**Purpose:**
Preserve meaningful experience so it can influence future decisions.

> **Memory is not storage. Storage stores data. Memory preserves meaning.**
> *(Trí nhớ không phải là kho lưu trữ. Kho lưu trữ giữ dữ liệu. Trí nhớ bảo tồn ý nghĩa.)*

**Primary locations:**

```text
backend/brain/memory.py
backend/brain/memory/
backend/brain/engine.py
backend/brain/blueprint.md
backend/brain/memory_flow.md
backend/brain/brain_memory_contract.md
```

**Current abilities:**

* Defines the philosophical and architectural role of Memory.
* Receives structured Experience objects.
* Provides early memory-engine behavior.
* Separates memory responsibilities from decision, planning, and delegation.

**Current limitations:**

* Persistence behavior must be verified.
* Recall behavior is not yet confirmed as operational.
* Reinforcement and relevance scoring are not complete.
* Multiple Memory entry points may exist and require consolidation.

**Next maturity target:** `INTEGRATED`

---

## CAP-BRN-004 — Planning

**Status:** `PROTOTYPE`

**Purpose:**
Convert an experience or intent into a Task that can later be executed.

**Primary locations:**

```text
backend/brain/planner.py
backend/brain/models/task.py
tests/test_planner.py
```

**Current abilities:**

* Creates Task objects from supported Brain inputs.
* Establishes separation between planning and execution.
* Has test coverage for the current limited behavior.

**Current limitations:**

* Planning is rule-limited.
* No multi-step planning graph has been confirmed.
* No prioritization, scheduling, dependency resolution, or replanning loop.

**Next maturity target:** `INTEGRATED`

---

## CAP-BRN-005 — Task Queue

**Status:** `PROTOTYPE`

**Purpose:**
Hold planned tasks until an appropriate Worker executes them.

**Primary locations:**

```text
backend/brain/task_queue.py
tests/test_task_queue.py
```

**Current abilities:**

* Queues Task objects.
* Supports basic insertion and retrieval.
* Creates an initial boundary between Brain and Workers.

**Current limitations:**

* Queue appears memory-local.
* No durable persistence.
* No retry, dead-letter queue, timeout, priority, locking, or worker ownership.
* No confirmed restart recovery.

**Next maturity target:** `OPERATIONAL`

---

## CAP-BRN-006 — Brain Orchestration

**Status:** `PROTOTYPE`

**Purpose:**
Coordinate experience intake, memory, planning, and task creation.

**Primary locations:**

```text
backend/brain_engine.py
backend/brain/engine.py
backend/main.py
```

**Current abilities:**

* Provides early orchestration entry points.
* Connects some Brain models and components.
* Exposes Brain functionality through the application layer.

**Current limitations:**

* Multiple engine locations may overlap.
* A single canonical Brain entry point has not yet been confirmed.
* External integrations are not yet consistently routed through one ingestion contract.
* Runtime observability remains limited.

**Next maturity target:** `INTEGRATED`

---

# 6. TRADING KNOWLEDGE CAPABILITIES

## CAP-TRD-001 — Trading Signal Model

**Status:** `FOUNDATION`

**Purpose:**
Represent a normalized trading signal independently of Telegram wording or broker implementation.

**Primary location:**

```text
backend/trading/models/signal.py
```

**Current abilities:**

* Represents symbol, order direction, entry, stop loss, and take profit.
* Supports immediate market instructions such as BUY NOW and SELL NOW.
* Creates a boundary between message parsing and trading execution.

**Current limitations:**

* Multi-take-profit structures have not been confirmed.
* Signal provenance and source-message identifiers are not yet confirmed.
* Signal expiration and modification lifecycle are not yet confirmed.

**Next maturity target:** `INTEGRATED`

---

## CAP-TRD-002 — Trading Signal Parser

**Status:** `PROTOTYPE`

**Purpose:**
Convert human Telegram trading messages into normalized Signal objects.

**Primary locations:**

```text
backend/trading/parser/signal_parser.py
tests/test_signal_parser.py
tests/test_signal_parser_negative.py
```

**Current abilities:**

* Parses BUY and SELL instructions.
* Recognizes NOW orders.
* Parses ENTRY, SL, and TP values.
* Rejects empty messages.
* Rejects invalid order sides.
* Requires SL and TP.
* Requires ENTRY for non-NOW signals.
* Resolves raw symbols through the symbol resolver.

**Current limitations:**

* Supports a narrow message format.
* Does not yet confirm handling for emojis, comments, ranges, multiple TPs, edits, replies, or multilingual signals.
* Numeric conversion failures require controlled error handling at integration boundaries.

**Next maturity target:** `INTEGRATED`

---

## CAP-TRD-003 — Symbol Resolution

**Status:** `PROTOTYPE`

**Purpose:**
Normalize human symbol names into TODOBA trading symbols and later into broker-specific symbols.

**Primary locations:**

```text
backend/trading/symbol_resolver.py
backend/trading/broker/broker_symbol_resolver.py
tests/test_mt5_symbols.py
```

**Current abilities:**

* Resolves supported signal symbols.
* Separates domain symbol normalization from broker-specific resolution.
* Provides a foundation for handling broker symbol suffixes or aliases.

**Current limitations:**

* Supported alias coverage must be documented.
* Broker discovery and resolution require integration tests against real MT5 environments.

**Next maturity target:** `INTEGRATED`

---

## CAP-TRD-004 — Trading Profile

**Status:** `FOUNDATION`

**Purpose:**
Describe how a customer or strategy is allowed to trade without storing credentials.

**Primary locations:**

```text
backend/trading/profile/trading_profile.py
tests/test_trading_profile.py
```

**Current abilities:**

* Defines profile name.
* Defines risk percentage.
* Defines maximum open trades.
* Defines allowed symbols.
* Defines the lot-sizing policy.
* Keeps broker secrets outside the profile object.

**Current limitations:**

* No confirmed profile persistence.
* No profile-selection mechanism connected to Telegram source groups.
* No account-level override or policy versioning.

**Next maturity target:** `INTEGRATED`

---

## CAP-TRD-005 — Signal Validation

**Status:** `PROTOTYPE`

**Purpose:**
Determine whether a normalized Signal is allowed under a Trading Profile.

**Primary locations:**

```text
backend/trading/validation/validation_policy.py
backend/trading/validation/validation_result.py
backend/trading/execution/execution_validator.py
tests/test_validation_policy.py
tests/test_validation_policy_negative.py
tests/test_validation_result.py
```

**Current abilities:**

* Represents validation outcomes.
* Applies initial trading restrictions.
* Separates validation from execution.
* Includes positive and negative tests.

**Current limitations:**

* Must be inspected for overlapping validation responsibilities.
* Live account conditions are not yet confirmed as part of validation.
* Spread, market status, duplicate signal, stale signal, and existing exposure checks are not yet confirmed.

**Next maturity target:** `INTEGRATED`

---

## CAP-TRD-006 — Lot Calculation

**Status:** `PROTOTYPE`

**Purpose:**
Calculate order volume according to a named lot policy.

**Primary locations:**

```text
backend/trading/execution/lot_calculator.py
```

**Current abilities:**

* Supports the fixed policy `FIXED_001`.
* Returns `0.01` lot for that policy.
* Rejects unknown policies.

**Current limitations:**

* Risk-percent calculation is not implemented.
* Does not yet calculate from stop-loss distance, symbol properties, balance, equity, or currency conversion.
* Current implementation must not be described as a full risk engine.

**Next maturity target:** `OPERATIONAL`

---

## CAP-TRD-007 — Execution Planning

**Status:** `PROTOTYPE`

**Purpose:**
Convert an approved Signal and Trading Profile into an immutable Execution Plan.

**Primary locations:**

```text
backend/trading/execution/execution_plan.py
backend/trading/execution/execution_planner.py
tests/test_execution_plan.py
```

**Current abilities:**

* Creates an immutable execution instruction.
* Includes symbol, order type, entry, SL, TP, lot, magic number, and comment.
* Separates Brain-approved intent from broker execution.
* Uses the configured lot policy.

**Current limitations:**

* Uses a fixed magic number.
* Uses a fixed comment.
* No correlation ID between Telegram message, Signal, Task, Execution Plan, and broker result has been confirmed.
* No versioned execution-policy metadata.

**Next maturity target:** `INTEGRATED`

---

# 7. BROKER AND MT5 CAPABILITIES

## CAP-MT5-001 — Broker Abstraction

**Status:** `FOUNDATION`

**Purpose:**
Prevent trading logic from depending directly on one broker implementation.

**Primary locations:**

```text
backend/trading/broker/broker_client.py
backend/trading/broker/mt5_client.py
```

**Current abilities:**

* Establishes a broker-client boundary.
* Provides an MT5 implementation path.
* Supports future broker replacement or additional broker adapters.

**Current limitations:**

* Interface completeness must be verified.
* Error contracts and retry behavior are not yet confirmed.
* Broker capability discovery is not fully integrated.

**Next maturity target:** `INTEGRATED`

---

## CAP-MT5-002 — MT5 Connection

**Status:** `PROTOTYPE`

**Purpose:**
Connect TODOBA to a MetaTrader 5 terminal and obtain trading environment information.

**Primary locations:**

```text
backend/trading/broker/mt5_client.py
backend/trading/knowledge/broker_discovery.py
tests/test_mt5_symbols.py
```

**Current abilities:**

* Provides an MT5 client implementation.
* Supports early symbol and broker discovery work.
* Establishes the basis for account and market information retrieval.

**Current limitations:**

* Production connection lifecycle is not yet confirmed.
* Reconnect handling, health status, terminal availability, and account mismatch controls require verification.
* Secrets must remain outside the repository.

**Next maturity target:** `OPERATIONAL`

---

## CAP-MT5-003 — MT5 Order Building

**Status:** `PROTOTYPE`

**Purpose:**
Translate an Execution Plan into an MT5-compatible order request.

**Primary locations:**

```text
backend/trading/broker/mt5_order_builder.py
tests/test_mt5_order_builder.py
```

**Current abilities:**

* Separates TODOBA Execution Plans from MT5 request structures.
* Provides a controlled translation layer.
* Supports testing without directly placing live orders.

**Current limitations:**

* All supported MT5 order types must be verified.
* Broker-specific filling modes and symbol constraints require runtime validation.

**Next maturity target:** `INTEGRATED`

---

## CAP-MT5-004 — MT5 Safety Gate

**Status:** `PROTOTYPE`

**Purpose:**
Prevent unintended live trading and require explicit permission before sending an order.

**Primary locations:**

```text
backend/trading/broker/mt5_safety.py
tests/test_mt5_safety.py
```

**Current abilities:**

* Establishes a safety boundary before order transmission.
* Supports controlled demonstration and test workflows.
* Protects the system from treating every parsed Telegram message as authorization to trade.

**Current limitations:**

* Safety policy must be verified before Telegram is connected to order sending.
* No live execution should be enabled until dry-run, account allowlist, and explicit execution mode are confirmed.

**Next maturity target:** `HARDENED`

---

## CAP-MT5-005 — MT5 Order Sending

**Status:** `PROTOTYPE`

**Purpose:**
Send an approved and safety-checked MT5 order request and return a normalized result.

**Primary locations:**

```text
backend/trading/broker/mt5_sender.py
backend/trading/models/order_result.py
tests/test_mt5_send_order_demo.py
tests/test_order_result.py
```

**Current abilities:**

* Provides an order-sending component.
* Represents normalized order results.
* Supports demonstration-level testing.

**Current limitations:**

* Must remain disabled from automatic Telegram execution until the complete integration pipeline passes dry-run tests.
* Duplicate protection, retry policy, idempotency, partial-fill handling, and reconciliation require verification.

**Next maturity target:** `OPERATIONAL`

---

# 8. TELEGRAM CAPABILITIES

## CAP-TEL-001 — Telegram Client Connection

**Status:** `PROTOTYPE`

**Purpose:**
Connect TODOBA to Telegram through a dedicated integration client.

**Primary locations:**

```text
backend/integrations/telegram_client.py
backend/config.py
```

**Current abilities:**

* Uses Telethon.
* Loads Telegram configuration from the application configuration layer.
* Provides a reusable Telegram client object.

**Current limitations:**

* Configuration validation must be verified.
* Session-file location and secret handling must be documented.
* Connection and reconnection behavior require tests.

**Next maturity target:** `OPERATIONAL`

---

## CAP-TEL-002 — Telegram Group Discovery

**Status:** `PROTOTYPE`

**Purpose:**
Discover Telegram groups and identify the source group that TODOBA should observe.

**Primary location:**

```text
backend/integrations/telegram_groups.py
```

**Current abilities:**

* Reuses the Telegram client.
* Provides a foundation for finding group identifiers.
* Supports configuring the intended signal source.

**Current limitations:**

* Group allowlisting must be enforced.
* Discovery tooling must remain separate from the production listener.
* Source identity should be recorded in normalized message metadata.

**Next maturity target:** `OPERATIONAL`

---

## CAP-TEL-003 — Telegram Message Listener

**Status:** `PROTOTYPE`

**Purpose:**
Listen for new messages from an approved Telegram signal group.

**Primary locations:**

```text
backend/integrations/telegram_listener.py
backend/config.py
```

**Current abilities:**

* Uses Telethon event handling.
* Can target a configured Telegram group.
* Provides an external input channel for TODOBA.

**Current limitations:**

* The complete handoff from Telegram message to Signal Parser must be verified.
* No confirmed normalized Telegram message envelope.
* No confirmed duplicate-message protection.
* No confirmed edit, deletion, reply, or forwarded-message policy.
* No confirmed error isolation or structured audit log.
* Listener must not directly send MT5 orders.

**Next maturity target:** `INTEGRATED`

---

## CAP-TEL-004 — Telegram Trading Signal Ingestion

**Status:** `CONCEPT`

**Purpose:**
Safely transform an approved Telegram message into a traceable TODOBA experience and trading signal.

**Required pipeline:**

```text
Telegram Message
    ↓
Source Allowlist
    ↓
Message Normalization
    ↓
Duplicate Check
    ↓
Experience Creation
    ↓
Signal Parsing
    ↓
Trading Profile Selection
    ↓
Validation
    ↓
Execution Planning
    ↓
Dry-Run Result
```

**Safety rule:**

```text
Telegram ingestion must end in DRY RUN by default.
Live order sending is a separate capability and requires explicit activation.
```

**Required components:**

```text
backend/integrations/telegram_message.py
backend/integrations/telegram_ingestion.py
tests/test_telegram_message.py
tests/test_telegram_ingestion.py
```

**Required data lineage:**

Every accepted Telegram message should preserve:

* Telegram chat ID;
* Telegram message ID;
* sender ID when available;
* message date;
* original text;
* normalized text;
* TODOBA experience ID;
* parsed signal;
* validation result;
* execution-plan ID or correlation ID;
* processing status;
* failure reason when rejected.

**Next maturity target:** `PROTOTYPE`

---

# 9. APPLICATION CAPABILITIES

## CAP-APP-001 — FastAPI Application

**Status:** `PROTOTYPE`

**Purpose:**
Expose TODOBA capabilities through an application runtime and diagnostic interface.

**Primary locations:**

```text
backend/main.py
backend/config.py
```

**Current abilities:**

* Runs a FastAPI application.
* Provides early Brain access.
* Supports a Brain viewer or HTML response.
* Acts as a possible runtime host for integration health endpoints.

**Current limitations:**

* Application lifecycle integration with Telegram must be designed carefully.
* Telegram listening should not be started multiple times by development reload processes.
* Health, readiness, integration state, and structured error endpoints are not yet confirmed.

**Next maturity target:** `OPERATIONAL`

---

# 10. TEST CAPABILITY

## CAP-TST-001 — Automated Component Tests

**Status:** `PROTOTYPE`

**Purpose:**
Protect existing behavior and permit safe integration of TODOBA capabilities.

**Primary location:**

```text
tests/
```

**Confirmed test areas include:**

* Brain planner;
* Task queue;
* Signal parser;
* Negative signal parsing;
* Trading profile;
* Validation policy;
* Negative validation cases;
* Validation result;
* MT5 symbol handling;
* MT5 safety;
* MT5 order building;
* Order result;
* Demonstration order sending.

**Current limitations:**

* Full test count and current pass status must be recorded.
* Telegram integration tests are not yet confirmed.
* No complete end-to-end dry-run test has been confirmed.
* External MT5 and Telegram dependencies require isolated adapters or controlled integration tests.

**Next maturity target:** `INTEGRATED`

---

# 11. CURRENT END-TO-END READINESS

## Existing component chain

The repository currently appears to contain components for:

```text
Telegram
    ↓
Signal Parser
    ↓
Trading Profile
    ↓
Validation
    ↓
Execution Planner
    ↓
MT5 Order Builder
    ↓
MT5 Safety
    ↓
MT5 Sender
```

However, the existence of these components does not prove that the full chain is integrated.

## Current system-level status

```text
Component foundations: PRESENT
Unit-level behavior: PARTIALLY TESTED
Telegram-to-Brain integration: NOT YET CONFIRMED
Telegram-to-Trading integration: NOT YET CONFIRMED
End-to-end dry run: NOT YET CONFIRMED
Automatic live trading: NOT APPROVED
```

---

# 12. ACTIVE INTEGRATION PRIORITY

## Mission: Telegram Integration Phase 1

The immediate objective is:

> Receive one approved Telegram signal message, preserve its origin, parse it, validate it, create an Execution Plan, and print or return a DRY-RUN result without sending a live MT5 order.

### Phase 1 acceptance criteria

Telegram Integration Phase 1 is complete only when:

1. TODOBA connects to Telegram successfully.
2. Only the configured source group is accepted.
3. Every message has a stable source identity.
4. Duplicate messages are ignored.
5. Invalid messages fail safely without stopping the listener.
6. Valid messages pass through the existing Signal Parser.
7. A selected Trading Profile is applied.
8. Validation returns a structured result.
9. Valid signals produce an Execution Plan.
10. The result is logged as `DRY_RUN`.
11. MT5 Sender is not called.
12. Automated tests pass.

---

# 13. ARCHITECTURAL RULES

## Rule 1 — Reuse Before Rewrite

Before creating a new component, inspect whether an existing component already owns the responsibility.

> **Reuse before rewrite.**
> *(Tái sử dụng trước khi viết lại.)*

## Rule 2 — One Canonical Owner

Each organizational responsibility must have one canonical module or contract.

Duplicated models, engines, validators, or integration entry points must be consolidated deliberately.

## Rule 3 — Integrations Are Inputs, Not the Brain

Telegram transports messages. It does not make trading decisions.

MT5 executes approved plans. It does not determine organizational intent.

## Rule 4 — Preserve Provenance

TODOBA must be able to answer:

* Where did this instruction come from?
* What original message created it?
* How was it interpreted?
* Which policies approved or rejected it?
* What action was planned?
* What result occurred?

## Rule 5 — Dry Run Before Live Execution

No external message may automatically produce a live order until the complete pipeline has:

* traceability;
* duplicate protection;
* source allowlisting;
* validation;
* safety gating;
* structured failure handling;
* dry-run tests;
* explicit Founder approval.

## Rule 6 — Capability Before Feature

> **A feature performs an action. A capability preserves the ability to perform that action reliably, repeatedly, and safely.**
> *(Tính năng thực hiện một hành động. Năng lực duy trì khả năng thực hiện hành động đó một cách đáng tin cậy, lặp lại được và an toàn.)*

---

# 14. NEXT CAPABILITIES TO BUILD

Development order:

```text
1. Audit existing Telegram modules
2. Establish canonical Telegram message model
3. Implement Telegram ingestion service
4. Connect ingestion to existing Signal Parser
5. Apply Trading Profile and Validation
6. Generate Execution Plan
7. Add dry-run audit output
8. Add duplicate protection
9. Add automated tests
10. Run complete regression suite
11. Update this Capability Catalog
12. Commit and push
```

Live MT5 execution is not part of Telegram Integration Phase 1.

---

# 15. DEFINITION OF DONE

A TODOBA capability is not complete merely because code exists.

A capability is complete only when:

* its purpose is explicit;
* its owner is explicit;
* its inputs and outputs are explicit;
* its boundaries are explicit;
* failures are controlled;
* safety rules are enforced;
* tests protect its behavior;
* documentation reflects reality;
* it is connected to the wider organization;
* the repository records its current state.

---

## FINAL PRINCIPLE

> **TODOBA is not software pretending to be an organization. TODOBA is an organization that happens to be built with software.**
> *(TODOBA không phải phần mềm giả vờ là một tổ chức. TODOBA là một tổ chức được xây dựng bằng phần mềm.)*
