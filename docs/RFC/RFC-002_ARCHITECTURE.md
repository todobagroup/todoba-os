# RFC-002 ARCHITECTURE

# TRADING OPERATIONS DEPARTMENT

Version: Draft 1.0

Status: Research

---

# SYSTEM ARCHITECTURE

                           Founder
                               │
                               │ Supervision
                               ▼
                         TODOBA Brain
                               │
     ┌───────────────┬──────────┴───────────┬───────────────┐
     │               │                      │               │
  Memory         Knowledge             Decision         Planner
     │               │                      │               │
     └───────────────┴──────────┬───────────┴───────────────┘
                                │
                                ▼
                 Trading Operations Department
                                │
 ┌─────────────────────────────────────────────────────────────┐
 │                                                             │
 │ Telegram Listener                                            │
 │        │                                                     │
 │        ▼                                                     │
 │ Signal Parser                                                │
 │        │                                                     │
 │        ▼                                                     │
 │ Signal Validator                                             │
 │        │                                                     │
 │        ▼                                                     │
 │ Risk Validator                                               │
 │        │                                                     │
 │        ▼                                                     │
 │ Execution Worker                                             │
 │        │                                                     │
 │        ▼                                                     │
 │ Position Monitor                                             │
 │        │                                                     │
 │        ├──────────────► Alert Worker                         │
 │        │                                                     │
 │        ▼                                                     │
 │ Journal Worker                                               │
 │        │                                                     │
 │        ▼                                                     │
 │ Learning Worker                                              │
 │                                                             │
 └─────────────────────────────────────────────────────────────┘
                                │
                                ▼
                         Broker / Exchange

---

# INFORMATION FLOW

Technical Team

↓

Telegram

↓

Trading Operations Department

↓

Brain Validation

↓

Broker

↓

Result

↓

Brain Memory

↓

Knowledge

↓

Founder Report

---

# DESIGN RULES

The Department does not own memory.

The Department does not own knowledge.

The Department requests decisions from the Brain.

The Brain remains the only organizational authority.

---

# FOUNDER CONTROL

Founder can:

- Pause Department
- Resume Department
- Stop Execution
- Change Trading Rules
- Override Decisions

The Founder is always above the Brain.

---

# ORGANIZATIONAL PRINCIPLE

Brain thinks.

Department operates.

Workers execute.

Founder supervises.