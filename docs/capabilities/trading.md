# Trading Operations Department

## Purpose

Receive trading signals, execute trades safely, monitor positions, and report results.

---

## Capability Flow

Signal Source

↓

Signal Parser

↓

Validation Policy

↓

Execution Policy

↓

Account Manager

↓

Broker Adapter

↓

Execution Worker

↓

Position Monitor

↓

Notification Worker

↓

Journal Worker

---

## Build Order

1. Telegram Client ✅
2. Telegram Listener ✅
3. Signal Model
4. Signal Parser
5. Validation Policy
6. Execution Policy
7. Account Manager
8. Broker Adapter
9. Execution Worker
10. Position Monitor
11. Notification Worker
12. Journal Worker

---

## Principle

Each capability must:

- Have one responsibility.
- Be independently testable.
- Be independently deployable.
- Never know business logic outside its responsibility.

---

## Definition of Done

A capability is complete only when:

- Code runs.
- Test passes.
- Security checked.
- Git committed.
- Git pushed.