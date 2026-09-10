# AI-Trading-Lab-Platform — Agent Rules

## 1. Project Boundary

This repository is a completely separate project from:

https://github.com/rezajahanbakhsh2020-hue/AI-Trading-Lab

AI-Trading-Lab is the original trading engine and is the source of truth.

AI-Trading-Lab-Platform is the new presentation, application, and integration layer.

Think of:

- AI-Trading-Lab = the passenger
- AI-Trading-Lab-Platform = the boat

The boat must carry the passenger without modifying the passenger.

## 2. Absolute Protection of the Original Repository

NEVER modify the original AI-Trading-Lab repository.

NEVER:

- edit its files
- delete its files
- rename its files
- move its files
- refactor its code
- change its strategies
- change its backtest engine
- change its evaluation logic
- change stability logic
- change live runtime logic
- change risk logic
- change tests
- change workflows
- change dependencies
- commit to it
- push to it
- create pull requests against it
- use it as a destination for generated code

The original repository may only be inspected as a read-only reference.

If integration with the original project is unclear, document the problem and continue only within this repository.

Never modify the original project to make integration easier.

## 3. Platform Responsibility

This repository is responsible for building a professional trading application interface around the existing trading system.

The platform should eventually provide:

- professional dashboard
- market selector
- XAU/USD as the primary market
- timeframe selector
- interactive candlestick chart
- volume display when available
- current price
- price change
- BUY / SELL / HOLD / NO SIGNAL display
- strategy name
- stability score
- risk information
- entry level
- stop loss
- TP1
- TP2
- TP3
- signal timestamp
- data freshness
- live monitoring status
- alerts
- responsive mobile-friendly interface
- professional visual hierarchy
- clear error and unavailable states

The platform must not invent trading data, signals, confidence, prices, risk levels, or performance.

If information is unavailable, display it as unavailable.

## 4. Architecture

Use a clear separation:

AI-Trading-Lab
    |
    | read-only integration boundary
    v
AI-Trading-Lab-Platform
    |
    +-- UI
    +-- application services
    +-- adapters
    +-- visualization
    +-- tests

The platform must consume the original system through explicit interfaces or adapters.

Do not copy the original trading engine into this repository.

Do not reimplement existing trading logic unless there is a documented and unavoidable interface requirement.

Prefer integration over duplication.

## 5. Trading Execution

Real order execution is NOT part of the initial platform.

Do not implement real-money trading execution.

Do not request, store, or expose exchange API keys or private credentials.

The initial platform is a research, visualization, monitoring, and signal presentation system.

## 6. Data Integrity

Never fabricate:

- market prices
- candles
- volume
- signals
- strategy results
- stability scores
- risk values
- performance metrics
- timestamps
- live status

Clearly distinguish:

- real data
- historical data
- simulated/test data
- unavailable data

Test fixtures may use synthetic data, but the UI must not present test data as live market data.

## 7. Development Process

Before implementing major features:

1. Inspect the repository.
2. Understand the existing structure.
3. Inspect the original AI-Trading-Lab as a read-only reference when necessary.
4. Identify integration boundaries.
5. Design the smallest appropriate interface.
6. Implement incrementally.
7. Run tests.
8. Run linting/type checks/build checks when applicable.
9. Fix discovered problems.
10. Re-run validation.
11. Continue until the current phase is complete.

Do not stop after writing code if automated validation can be performed.

Do not declare a feature complete without validating it.

## 8. Change Discipline

Keep changes focused.

Do not introduce unnecessary dependencies.

Do not rewrite working code without a clear reason.

Do not create duplicate implementations of the same responsibility.

Prefer small, understandable modules.

Keep business logic separate from UI components.

Keep external integrations behind adapters.

## 9. UI/UX Principles

The application should feel like a professional modern trading platform.

Prioritize:

- clarity
- speed
- readability
- responsive design
- mobile usability
- intuitive navigation
- clear trading-state visualization
- consistent components
- accessible controls
- useful empty states
- useful loading states
- useful error states

The design may be inspired by modern trading platforms such as TradingView, Binance, BingX, and CoinEx, but must not copy proprietary branding or design assets.

## 10. Risk Presentation

Risk information must be visually clear.

When valid data is available, support visualization of:

- Entry
- Stop Loss
- TP1
- TP2
- TP3

Risk levels should be clearly differentiated on charts.

Do not imply guaranteed profit or trading success.

## 11. Testing

The platform must have its own test suite.

Tests should cover, as appropriate:

- adapters
- services
- data validation
- signal presentation
- risk presentation
- stability presentation
- error handling
- UI behavior
- integration boundaries
- end-to-end workflows

Tests must not modify the original AI-Trading-Lab repository.

## 12. Security

Treat all external market data as untrusted input.

Do not expose secrets in source code.

Do not commit credentials.

Do not store exchange API keys in the repository.

Use environment variables for future integrations.

Keep the original repository outside the platform's write boundary.

## 13. Agent Behavior

The coding agent is authorized to work on this repository.

The coding agent is NOT authorized to modify the original AI-Trading-Lab repository.

When uncertain, choose the option that preserves the original repository unchanged.

When an implementation would require modifying the original project, stop that approach and design an adapter or interface inside this repository instead.

## 14. Completion Standard

A phase is complete only when:

- implementation exists
- relevant tests exist
- tests pass
- build/type/lint validation passes when applicable
- no original repository files were modified
- no fake production data was introduced
- architecture remains modular
- the feature works on mobile-sized layouts when UI-related

The goal is a production-quality platform built around the existing AI-Trading-Lab without altering its core.
