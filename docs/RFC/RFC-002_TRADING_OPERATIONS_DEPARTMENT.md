# RFC-002

# TRADING OPERATIONS DEPARTMENT

Version: Draft 1.0

Status: Research

Author: CTO10

---

# PURPOSE

Build the first operational department of TODOBA.

The department executes trading operations based on Founder-approved strategy.

It does not create trading strategies.

It executes them.

---

# MISSION

Allow TODOBA to operate trading activities continuously, even when the Founder is offline.

---

# ORGANIZATIONAL POSITION

Founder

↓

Brain

↓

Decision

↓

Trading Operations Department

↓

Workers

---

# RESPONSIBILITIES

The department is responsible for:

- Receiving trading signals.
- Understanding signals.
- Validating execution conditions.
- Executing trades.
- Monitoring positions.
- Reporting to the Founder.
- Recording trading history.
- Learning from completed trades.

---

# DOES NOT

The department does NOT:

- Invent trading strategies.
- Ignore Founder rules.
- Override risk management.
- Change system architecture.

---

# DEPARTMENT STRUCTURE

Trading Operations Department

├── Telegram Listener

├── Signal Parser

├── Signal Validator

├── Risk Validator

├── Execution Worker

├── Position Monitor

├── Alert Worker

├── Journal Worker

└── Learning Worker

---

# WORKER PURPOSES

Telegram Listener

Receive trading signals.

---

Signal Parser

Convert signals into structured information.

---

Signal Validator

Verify signal completeness.

---

Risk Validator

Verify:

- Risk
- Lot Size
- Daily Loss
- Maximum Positions
- Trading Time

---

Execution Worker

Execute approved trades.

---

Position Monitor

Track every active position.

---

Alert Worker

Notify the Founder.

---

Journal Worker

Record every trading action.

---

Learning Worker

Extract lessons after trade completion.

---

# OPERATION FLOW

Technical Team

↓

Telegram Signal

↓

Telegram Listener

↓

Signal Parser

↓

Signal Validator

↓

Risk Validator

↓

Brain Decision

↓

Execution Worker

↓

Broker

↓

Position Monitor

↓

Alert Worker

↓

Journal Worker

↓

Learning Worker

↓

Memory

↓

Knowledge

---

# FOUNDER SUPERVISION

The Founder always remains above the department.

The Founder can:

- Pause execution.
- Resume execution.
- Override decisions.
- Change trading rules.

No worker may override the Founder.

---

# MVP

The first release only needs to support:

✓ Telegram Signal

✓ Signal Parsing

✓ Risk Validation

✓ Order Execution

✓ Founder Notification

No AI prediction.

No autonomous strategy.

---

# SUCCESS METRIC

The department can execute approved trading signals without Founder intervention while maintaining complete reporting and risk control.

---

# FUTURE EXPANSION

Future workers may include:

- Portfolio Manager

- News Monitor

- AI Market Analyst

- Strategy Optimizer

- Broker Optimizer

- Capital Allocation Manager

These are outside MVP.

---

# PRINCIPLE

Execution before Intelligence.

Reliability before Automation.

Discipline before Prediction.