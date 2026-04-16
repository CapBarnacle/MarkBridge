# Agent Operating Model

## Principle
Subagents should split work by stable responsibility boundaries, not by temporary tasks.

## Agents

### 1. Orchestrator
- reads project docs
- determines next implementation step
- coordinates subagent outputs
- updates decision log

### 2. Parser Architect
- defines parser interfaces
- maintains parser capability registry
- aligns parser outputs to shared IR

### 3. Routing Policy Agent
- defines inspection features
- maintains deterministic routing rules
- defines LLM invocation conditions

### 4. Table IR Agent
- designs nested table / merged cell / continuation table handling
- defines semantic table model

### 5. Renderer Agent
- converts IR to Markdown
- defines block rendering rules

### 6. QA/Eval Agent
- builds benchmark fixtures
- defines quality metrics
- compares deterministic vs LLM-assisted routes

### 7. Docs Maintainer
- keeps docs aligned with implementation
- updates architecture spec, WBS, and decision log