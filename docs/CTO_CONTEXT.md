# TODOBA CTO CONTEXT

> This document is the operational source of truth for every CTO taking over TODOBA.
>
> Read this file first before reading any code.
> Update this file at the end of every completed Sprint.

---

# PROJECT

TODOBA Trading Operating System

Founder:
- Vision owner
- Product owner
- Production validation owner

CTO:
- Architecture owner
- Runtime owner
- Code quality owner

---

# WORKING DNA

Every Sprint follows exactly this workflow:

Survey

↓

Replace Whole File

↓

Compile

↓

Focused Test

↓

Integration

↓

Full Regression

↓

Production Validation

Never patch individual lines.

---

# CURRENT STATE

Current Sprint:

Sprint 401

Current Branch:

main

Production Status:

- MT5 LIVE_DEMO VERIFIED
- Telegram VERIFIED
- Stable Lot VERIFIED
- Persistence VERIFIED
- Reflection VERIFIED
- Runtime Health VERIFIED

Regression:

Latest regression green.

Focused tests green.

---

# COMPLETED CAPABILITIES

✓ Telegram Integration

✓ Trading Department

✓ Trading Runtime

✓ Runtime Recovery

✓ Stable Lot Policy

✓ Persistence

✓ Lifecycle

✓ Reflection

✓ Memory

✓ Runtime Health

✓ Production Event Logger

✓ Trade Timeline

✓ Trade Timeline Service

✓ Timeline Integration

---

# CURRENT PRODUCTION BUG

Decision Engine still blocks new trades using:

has_open_position

Architecture decision:

Replace

has_open_position

with

open_position_count

+

max_open_trades

Goal:

Allow multiple valid positions.

Reject only when:

open_position_count >= max_open_trades

---

# CURRENT IMPLEMENTATION STATUS

Completed today:

✓ decision_engine.py updated

✓ telegram_task_producer.py updated

Remaining:

□ decision_gateway.py

□ telegram_task_execution_bridge.py

□ telegram_listener.py

Production validation required after completion.

---

# ARCHITECTURE

Telegram

↓

IncomingSignal

↓

Decision

↓

Task

↓

Trading Department

↓

Trading Runtime

↓

Execution

↓

Persistence

↓

Lifecycle

↓

Reflection

↓

Memory

↓

Timeline

Trading Department owns the trading lifecycle.

Runtime executes.

Telegram never executes MT5 directly.

---

# PRINCIPLES

Architecture before Features.

Production before Expansion.

Bug first.

Capability second.

Every capability has exactly one owner.

Repository is the source of truth.

Chat is only discussion.

---

# NEXT CTO

If you are the next CTO:

Do not redesign TODOBA first.

Read:

1. CTO_CONTEXT.md

2. CAPABILITY_CATALOG.md

3. CTO_PLAYBOOK.md

Then inspect the current Sprint work.

Continue the existing architecture.

Do not introduce a parallel architecture.

Always preserve ownership boundaries.