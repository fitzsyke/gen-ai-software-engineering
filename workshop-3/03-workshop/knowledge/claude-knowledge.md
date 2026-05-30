# Claude Code Best Practices & Specification-Driven Development Guide

> A comprehensive reference for maximizing Claude Code effectiveness through CLAUDE.md configuration, specification-driven development, and advanced workflows.

---

## Table of Contents

1. [Foundational Mindset](#foundational-mindset)
2. [CLAUDE.md Configuration](#claudemd-configuration)
3. [Specification-Driven Development](#specification-driven-development)
4. [Best Practices](#best-practices)
5. [Tools & Features](#tools--features)
6. [Agents & Subagents](#agents--subagents)
7. [Skills & Commands](#skills--commands)
8. [Hooks & Automation](#hooks--automation)
9. [MCP Servers](#mcp-servers)
10. [Session Management](#session-management)
11. [CLI Reference](#cli-reference)
12. [Common Failure Patterns](#common-failure-patterns)

---

## Foundational Mindset

### Core Principle: Deterministic Outputs

**"Artifacts over conversations. Files over explanations. Commits over suggestions."**

Every Claude Code interaction should produce verifiable, usable artifacts (code, scripts, documents, configurations) rather than chat responses. This transforms Claude from a conversational assistant into a productive coding partner.

### The Fundamental Constraint

**Claude's context window fills up fast, and performance degrades as it fills.**

- The context window holds your entire conversation, files read, and command outputs
- A single debugging session might consume tens of thousands of tokens
- LLM performance degrades as context fills - Claude may "forget" instructions or make more mistakes
- **Context management is the most important skill to develop**

### Agentic Coding Philosophy

Claude Code is an agentic coding environment:
- Unlike a chatbot, it reads files, runs commands, makes changes, and works autonomously
- You describe what you want; Claude figures out how to build it
- Claude explores, plans, and implements while you watch, redirect, or step away

---

## CLAUDE.md Configuration

### What is CLAUDE.md?

CLAUDE.md is a special file that Claude reads at the start of every conversation. It provides persistent context that Claude can't infer from code alone - the single most important configuration file for Claude Code.

### File Locations (Hierarchical Loading)

```
~/.claude/CLAUDE.md          # Global - applies to all projects
./CLAUDE.md                  # Project root - check into git (recommended)
./CLAUDE.local.md            # Project root - gitignored, personal overrides
./parent/CLAUDE.md           # Parent directories - useful for monorepos
./subdir/CLAUDE.md           # Child directories - loaded on demand
```

### Essential Structure

**The Three Components (WHAT, WHY, HOW):**

1. **WHAT**: Technology stack, project structure, codebase organization
2. **WHY**: Project purpose, component functions
3. **HOW**: Build tools, testing, compilation, verification

**Example CLAUDE.md:**

```markdown
# Project Overview
FastAPI REST API for banking transactions using SQLAlchemy and Pydantic.

# Directory Structure
- app/models/ - database models (use Decimal for money)
- app/api/ - route handlers
- app/core/ - configuration and utilities
- tests/ - pytest test suite

# Commands
- npm run build: Build the project
- npm run typecheck: Run the typechecker
- pytest tests/ -v: Run test suite

# Code Style
- Use ES modules (import/export) syntax, not CommonJS (require)
- Destructure imports when possible
- Use type hints on all functions
- ALWAYS use decimal.Decimal for monetary calculations, NEVER float

# Workflow
- Be sure to typecheck when you're done making changes
- Prefer running single tests, not the whole test suite
- Run verification before claiming task complete

# Domain Rules
- Treat account numbers as PII - never log raw values
- All financial operations require audit logging
```

### What to Include vs Exclude

| Include | Exclude |
|---------|---------|
| Bash commands Claude can't guess | Things Claude can figure out by reading code |
| Code style rules that differ from defaults | Standard language conventions |
| Testing instructions and preferred runners | Detailed API docs (link instead) |
| Repository etiquette (branch naming, PR conventions) | Information that changes frequently |
| Architectural decisions specific to project | Long explanations or tutorials |
| Developer environment quirks (required env vars) | File-by-file descriptions |
| Common gotchas or non-obvious behaviors | Self-evident practices like "write clean code" |
| Domain-specific standards (banking, compliance) | Code style that linters handle |

### Critical Guidelines

**Keep It Concise:**
- Frontier LLMs can follow ~150-200 instructions with reasonable consistency
- Claude Code's system prompt already contains ~50 instructions
- Target under 300 lines; HumanLayer's root file is under 60 lines
- For each line, ask: *"Would removing this cause Claude to make mistakes?"* If not, cut it

**Avoid Style in CLAUDE.md:**
- Never send an LLM to do a linter's job
- Use deterministic tools (ESLint, Prettier, Black) for formatting
- LLMs are expensive and slow compared to linters

**Use Progressive Disclosure:**
- Don't tell Claude everything upfront
- Tell it how to find information when needed
- Use `@path/to/import` syntax to reference other files:

```markdown
See @README.md for project overview and @package.json for npm commands.

# Additional Instructions
- Git workflow: @docs/git-instructions.md
- Personal overrides: @~/.claude/my-project-instructions.md
```

**Tune with Emphasis:**
- Add "IMPORTANT" or "YOU MUST" for critical rules
- If Claude ignores a rule, the file is probably too long

**Maintenance:**
- Check CLAUDE.md into git so your team can contribute
- Review it when things go wrong, prune regularly
- Test changes by observing if Claude's behavior shifts
- Update when Claude makes mistakes to prevent recurrence

### The # Key Shortcut

Press `#` to give Claude an instruction that it will automatically incorporate into the relevant CLAUDE.md. Include CLAUDE.md changes in commits so team members benefit.

### Getting Started: /init Command

Run `/init` to generate a starter CLAUDE.md based on your current project structure. The command analyzes:
- Package files and dependencies
- Documentation and configuration
- Build systems and test frameworks
- Code patterns

Treat the output as a foundation to refine based on actual team practices.

---

## Specification-Driven Development

### The Fundamental Pattern: WHAT vs HOW

- **Specification (WHAT)**: Detailed, version-controlled document defining functional goals, user stories, data models, API contracts, security requirements, and acceptance criteria
- **Implementation (HOW)**: AI agents translate the specification into code, tests, documentation while adhering strictly to spec constraints
- **Separation of Concerns**: Human engineers focus on high-level architecture and product definition; AI handles implementation

### Why Specification-Driven Development Matters

**For AI-Assisted Development:**
- **Agentic Fidelity**: Formalized specs provide extensive context for complex multi-step AI agents to operate autonomously without drifting
- **Context Window Management**: Uses refined, structured specification as initial context, preventing AI from being overwhelmed
- **Governance & Auditability**: Every line of generated code traces back to specific requirements (critical for regulated industries)
- **Decoupling Intent from Implementation**: Can change tech stacks without modifying specifications

### Four-Phase Development Workflow

| Phase | Input | Output |
|-------|-------|--------|
| **1. Specify** | UX and business logic | Requirements, user stories, acceptance criteria |
| **2. Plan** | Architecture and technical constraints | Technical design, data schemas, API definitions |
| **3. Task** | Validate atomic work units | Traceability, focused implementation tasks |
| **4. Implement** | Review AI-generated code | Production-ready code with passing tests |

### Specification Template: Five Essential Sections

**1. High-Level Objective**
- Single sentence describing the feature
- Example: *"Build a comprehensive KYC API that validates customer information and performs compliance checks"*

**2. Mid-Level Objectives**
- 3-5 testable, measurable requirements
- Example:
  - Create complete OpenAPI 3.1 specification
  - Implement FastAPI endpoints with validation
  - Build document verification capabilities
  - Add compliance checking for sanctions/AML
  - Implement comprehensive contract testing

**3. Implementation Notes**
- Technical constraints and standards
- Technology choices (frameworks, versions)
- Data handling requirements
- Security and compliance standards
- Quality targets

**4. Context**
- **Beginning Context**: What files/state exist initially
- **Ending Context**: What files should exist after completion

**5. Low-Level Tasks**
- Specific, actionable AI prompts
- Structure:
  ```
  What prompt would you run?
  What file to CREATE or UPDATE?
  What function to CREATE or UPDATE?
  What details to add?
  ```

### Claude Code Spec Workflow Tool

An automated spec-driven development package that provides:

**Project Structure:**
```
.claude/
├── commands/          # 14+ slash commands
├── steering/          # product.md, tech.md, structure.md
├── templates/         # Document templates
├── specs/            # Generated specifications
├── bugs/             # Bug fix workflows
└── agents/           # AI agents
```

**Steering Documents (Project Context):**
- **product.md** - Vision, target users, key features, success metrics
- **tech.md** - Technology stack, tools, constraints, integrations
- **structure.md** - File organization, naming conventions, import patterns

**Commands:**
- `/spec-create feature-name "description"` - Create new feature spec
- `/spec-steering-setup` - Initialize steering documents
- `/bug-create`, `/bug-analyze`, `/bug-fix`, `/bug-verify` - Bug fix workflow

**Installation:**
```bash
npm i -g @pimzino/claude-code-spec-workflow
claude-code-spec-workflow
```

### Test-Driven Development Integration

TDD becomes more powerful with agentic coding:

1. Tell Claude to do test-driven development explicitly
2. Instruct Claude to write failing tests first (not implementation)
3. Tell Claude to run tests and confirm they fail
4. Commit the tests when satisfied
5. Ask Claude to write code that passes the tests (without modifying tests)
6. Tell Claude to keep going until all tests pass

---

## Best Practices

### Give Claude Verification Methods

**The single highest-leverage thing you can do.**

Claude performs dramatically better when it can verify its own work through tests, screenshots, or expected outputs.

| Strategy | Before | After |
|----------|--------|-------|
| **Provide verification criteria** | *"implement email validation"* | *"write validateEmail function. test: user@example.com is true, invalid is false. run tests after"* |
| **Verify UI visually** | *"make dashboard look better"* | *"[paste screenshot] implement this design. screenshot result and compare. list differences and fix"* |
| **Address root causes** | *"the build is failing"* | *"build fails with this error: [paste]. fix it and verify build succeeds. address root cause"* |

### Explore First, Then Plan, Then Code

Separate research and planning from implementation:

1. **Explore** (Plan Mode): Read files and answer questions without making changes
2. **Plan** (Plan Mode): Create detailed implementation plan; press `Ctrl+G` to edit plan
3. **Implement** (Normal Mode): Code with verification against the plan
4. **Commit**: Descriptive message and create PR

**When to skip planning:** Clear scope, small fix (typo, log line, rename). If you could describe the diff in one sentence, skip the plan.

### Provide Specific Context

| Strategy | Before | After |
|----------|--------|-------|
| **Scope the task** | *"add tests for foo.py"* | *"write test for foo.py covering user logout edge case. avoid mocks"* |
| **Point to sources** | *"why does ExecutionFactory have weird api?"* | *"look through ExecutionFactory's git history and summarize how its api came to be"* |
| **Reference patterns** | *"add a calendar widget"* | *"look at HotDogWidget.php to understand patterns. follow the pattern to implement calendar widget"* |
| **Describe symptoms** | *"fix the login bug"* | *"users report login fails after session timeout. check auth flow in src/auth/. write failing test, then fix"* |

### Provide Rich Content

- **Reference files with `@`** instead of describing locations
- **Paste images directly** via copy/paste or drag-and-drop
- **Give URLs** for documentation; use `/permissions` to allowlist domains
- **Pipe in data**: `cat error.log | claude`
- **Let Claude fetch**: Tell Claude to pull context itself

### Course-Correct Early

- **`Esc`**: Stop Claude mid-action
- **`Esc + Esc` or `/rewind`**: Restore previous conversation and code state
- **`"Undo that"`**: Have Claude revert changes
- **`/clear`**: Reset context between unrelated tasks

**If you've corrected Claude more than twice on the same issue**, run `/clear` and start fresh with a better prompt.

---

## Tools & Features

### The Four Modes of Operation

| Mode | Behavior | Best For |
|------|----------|----------|
| **Standard** | Proposes changes, waits for confirmation | Learning, careful review |
| **Accept Edits** | Applies changes directly (no confirmation) | Executing pre-reviewed plans |
| **Plan** | Analyzes and plans without making changes | Complex features, exploration |
| **Web** | Background persistent sessions | Long-running tasks, cross-device |

**Recommended Workflow:** Start in Plan Mode to develop strategy, then switch to Accept Edits (`Shift+Tab` to cycle modes).

### File References

```
@./src/components/Button.tsx     # Single file
@./src/                          # Directory (recursive)
@./src/**/*.test.ts              # Glob patterns
```

### Key CLI Flags

```
--model              Specify Claude model (sonnet/opus/haiku)
--add-dir            Include additional working directories
--allowedTools       Pre-approve specific tools
--disallowedTools    Block specific tools
--max-turns          Limit conversation turns
--output-format      Set format (text/json/stream-json)
--verbose            Enable detailed logging
```

### Interactive Session Commands

| Command | Function |
|---------|----------|
| `/help` | Display available commands |
| `/config` | Configure settings interactively |
| `/vim` | Enable vim-style editing |
| `/agents` | Manage subagents |
| `/mcp` | Configure Model Context Protocol |
| `/permissions` | Manage tool permissions |
| `/sandbox` | Enable OS-level isolation |
| `/hooks` | Configure automation hooks |
| `/clear` | Reset context |
| `/rewind` | Restore previous state |
| `/compact` | Summarize context manually |
| `!command` | Execute shell commands |

---

## Agents & Subagents

### What Are Subagents?

Subagents run in their own context with their own set of allowed tools. They're useful for:
- Tasks that read many files
- Specialized focus without cluttering main conversation
- Parallel investigation

### Defining Custom Subagents

Create in `.claude/agents/`:

```markdown
# .claude/agents/security-reviewer.md
---
name: security-reviewer
description: Reviews code for security vulnerabilities
tools: Read, Grep, Glob, Bash
model: opus
---
You are a senior security engineer. Review code for:
- Injection vulnerabilities (SQL, XSS, command injection)
- Authentication and authorization flaws
- Secrets or credentials in code
- Insecure data handling

Provide specific line references and suggested fixes.
```

### Using Subagents for Investigation

Since context is the fundamental constraint, subagents are powerful:

```
Use subagents to investigate how our authentication system handles token
refresh, and whether we have any existing OAuth utilities I should reuse.
```

The subagent explores the codebase and reports back summaries without cluttering your main conversation.

### Multi-Agent Orchestration Patterns

**Intermediate (Single Agent):**
- Explore Agent - Find files, understand patterns
- Background Tasks - Hand off with `&` for web execution
- Research Agent - Gather information from codebase

**Advanced Patterns:**
- **Parallel Independent Tasks** - Code + Tests + Docs simultaneously
- **Sequential with Handoff** - Design -> Implement -> Test -> Review
- **Writer/Reviewer Pattern** - One session writes, another reviews with fresh context
- **Coordinator Pattern** - One agent coordinates multiple workers

**Configuration:**
```json
{
  "agents": {
    "max_concurrent": 3,
    "timeout_ms": 300000,
    "require_review": true
  }
}
```

---

## Skills & Commands

### Skills System

Skills extend Claude's knowledge with project-specific information. Claude applies them automatically when relevant, or you invoke directly with `/skill-name`.

**Creating a Skill:**

```markdown
# .claude/skills/api-conventions/SKILL.md
---
name: api-conventions
description: REST API design conventions for our services
---
# API Conventions
- Use kebab-case for URL paths
- Use camelCase for JSON properties
- Always include pagination for list endpoints
- Version APIs in the URL path (/v1/, /v2/)
```

**Workflow Skills:**

```markdown
# .claude/skills/fix-issue/SKILL.md
---
name: fix-issue
description: Fix a GitHub issue
disable-model-invocation: true
---
Analyze and fix the GitHub issue: $ARGUMENTS.

1. Use `gh issue view` to get the issue details
2. Understand the problem described in the issue
3. Search the codebase for relevant files
4. Implement the necessary changes to fix the issue
5. Write and run tests to verify the fix
6. Ensure code passes linting and type checking
7. Create a descriptive commit message
8. Push and create a PR
```

Run `/fix-issue 1234` to invoke. Use `disable-model-invocation: true` for workflows with side effects.

### Core Skills (Superpowers)

**Process Skills (Use First):**
- **brainstorming** - New features, design decisions -> Proposes approaches, writes design doc
- **systematic-debugging** - Bugs, test failures -> Reproduce -> Hypothesize -> Trace -> Fix -> Verify
- **writing-plans** - Multi-step work -> Break into tasks, specify paths, add verification

**Implementation Skills:**
- **test-driven-development** - Write failing test -> Write minimum code -> Pass test -> Refactor -> Commit
- **verification-before-completion** - Run verification, confirm output, check regressions

**Parallelization Skills:**
- **dispatching-parallel-agents** - 2+ independent tasks without shared state
- **subagent-driven-development** - Execute plans with agents in current session
- **executing-plans** - Run implementation plans with review checkpoints

### Custom Commands

Commands are markdown files in `.claude/commands/` that define reusable prompts:

```markdown
# .claude/commands/review-pr.md
---
command: review-pr
description: Review a pull request with prioritized feedback
---

# Review Pull Request

## Arguments
- `$ARGUMENTS` - PR number or URL

## Instructions
1. Fetch PR details using gh CLI
2. Review all changed files
3. Categorize issues as P1 (blocking), P2 (should fix), P3 (nice to have)
4. Check for security vulnerabilities
5. Verify test coverage
6. Output structured review to ./reviews/PR-$ARGUMENTS.md
```

---

## Hooks & Automation

### What Are Hooks?

Hooks run scripts automatically at specific points in Claude's workflow. Unlike CLAUDE.md instructions (advisory), hooks are **deterministic and guaranteed**.

### Configuration

In `.claude/settings.json`:

```json
{
  "hooks": {
    "pre-commit": {
      "command": "npm run lint-staged",
      "description": "Lint staged files",
      "timeout": 10000
    },
    "pre-push": {
      "command": "npm test -- --coverage",
      "description": "Full test suite before push",
      "timeout": 120000
    },
    "session-start": {
      "command": "git status --short",
      "description": "Show git status on start"
    }
  }
}
```

### Common Hook Types

- `pre-commit` - Lint, type-check, format (keep fast <10 seconds)
- `pre-push` - Full test suite, build
- `session-start` - Environment verification
- `tool-invocation` - Validate specific tool usage
- `PreToolUse`, `PostToolUse` - Before/after tool execution

### Best Practices

- Keep pre-commit fast (<10 seconds)
- Move slow checks to pre-push
- Provide clear error messages
- Use hooks for actions that must happen every time

**Let Claude write hooks:**
- *"Write a hook that runs eslint after every file edit"*
- *"Write a hook that blocks writes to the migrations folder"*

Run `/hooks` for interactive configuration.

---

## MCP Servers

### What Are MCP Servers?

Model Context Protocol servers extend Claude Code with access to external systems like Notion, Figma, databases, and monitoring tools.

### Built-in Servers

- `filesystem` - Enhanced file operations
- `git` - Repository analysis

### Advanced Servers (require tokens)

- `github` - PR management, issues (needs GITHUB_TOKEN)
- `slack` - Notifications (needs SLACK_BOT_TOKEN)
- `postgres` - Database queries (needs DATABASE_URL)

### Configuration

In `.claude/mcp/servers.json`:

```json
{
  "servers": {
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "--root", "."]
    },
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${env:GITHUB_TOKEN}"
      }
    }
  }
}
```

### Security

- Use environment variables, never hardcode tokens
- Apply minimal required permissions
- Review what Claude can access via MCP

---

## Session Management

### Context Management

**Aggressive context management is critical:**

- Use `/clear` frequently between unrelated tasks
- When auto compaction triggers, Claude summarizes important code and decisions
- Run `/compact <instructions>` for manual control: `/compact Focus on API changes`
- Add compaction instructions to CLAUDE.md: *"When compacting, preserve full list of modified files"*

### Checkpoints and Rewind

Every action creates a checkpoint. Double-tap `Escape` or run `/rewind` to:
- Restore conversation only (keep code changes)
- Restore code only (keep conversation)
- Restore both

Checkpoints persist across sessions.

### Resume Conversations

```bash
claude --continue    # Resume most recent conversation
claude --resume      # Select from recent conversations
```

Use `/rename` to give sessions descriptive names for later retrieval.

### Parallel Sessions

**Terminal Setup:**
- Multiple tabs with separate Claude instances
- Each session works in isolated git worktree
- Session 1 handles planning/coordination
- Other sessions handle specific tasks

**Git Worktree Isolation:**
```bash
git worktree add ../project-feature-a feature-a
git worktree add ../project-feature-b feature-b
```

**Web Integration:**
- Additional background sessions on claude.ai/code
- Hand off with `&`: `> task description &`
- Teleport back with session IDs: `claude -t abc123def456`

### Headless Mode

```bash
# One-off queries
claude -p "Explain what this project does"

# Structured output for scripts
claude -p "List all API endpoints" --output-format json

# Streaming for real-time processing
claude -p "Analyze this log file" --output-format stream-json
```

### Fan Out Pattern

For large migrations:

1. Have Claude list all files needing migration
2. Loop through with scoped permissions:
```bash
for file in $(cat files.txt); do
  claude -p "Migrate $file from React to Vue. Return OK or FAIL." \
    --allowedTools "Edit,Bash(git commit *)"
done
```

---

## CLI Reference

### Installation

```bash
npm install -g @anthropic-ai/claude-code
export ANTHROPIC_API_KEY="YOUR_KEY"
```

### Core Commands

| Command | Purpose |
|---------|---------|
| `claude` | Start interactive REPL |
| `claude "query"` | Begin with initial prompt |
| `claude -p "query"` | Print mode (query once, exit) |
| `cat file \| claude -p "query"` | Process piped input |
| `claude -c` | Continue recent conversation |
| `claude -r "id" "query"` | Resume specific session |

### Configuration Files

**Hierarchy (applied in order):**
- User: `~/.claude/settings.json`
- Project: `.claude/settings.json`
- Local: `.claude/settings.local.json`

### Models Available

| Model | Best For |
|-------|----------|
| **Sonnet 4.5** | Most tasks (default) |
| **Haiku 4.5** | Faster, token-efficient |
| **Opus 4.5** | Complex planning, state-of-art |

### Permission Configuration

```json
{
  "permissions": {
    "allow": [
      "Read",
      "Write",
      "Edit",
      "Bash(npm:*)",
      "Bash(git:*)",
      "Task"
    ],
    "deny": [
      "Bash(rm -rf /)",
      "Bash(sudo:*)"
    ]
  }
}
```

---

## Common Failure Patterns

### Kitchen Sink Session
**Problem:** Start with one task, ask something unrelated, go back. Context full of irrelevant information.
**Fix:** `/clear` between unrelated tasks.

### Correcting Over and Over
**Problem:** Claude does something wrong, you correct repeatedly. Context polluted with failed approaches.
**Fix:** After two failed corrections, `/clear` and write a better initial prompt.

### Over-Specified CLAUDE.md
**Problem:** CLAUDE.md too long, Claude ignores half of it.
**Fix:** Ruthlessly prune. If Claude already does something correctly without the instruction, delete it.

### Trust-Then-Verify Gap
**Problem:** Claude produces plausible-looking implementation that doesn't handle edge cases.
**Fix:** Always provide verification (tests, scripts, screenshots). If you can't verify it, don't ship it.

### Infinite Exploration
**Problem:** Ask Claude to "investigate" without scoping. Claude reads hundreds of files, filling context.
**Fix:** Scope investigations narrowly or use subagents.

---

## Banking Domain Standards

When working on financial/banking applications:

### Monetary Calculations
- **ALWAYS** use `decimal.Decimal`, **NEVER** `float`
- Support ISO 4217 currency codes (USD, EUR, GBP)
- Handle currency conversion with proper precision

### Data Privacy & Security
- Treat account numbers, names, transaction details as PII
- Implement data sanitization in logs
- Use secure file handling practices
- Follow PCI DSS standards

### Audit Requirements
- Log all operations with timestamps
- Include transaction counts and processing status
- Maintain compliance audit trails

### Fraud Detection Patterns
- High-value transactions (>$10,000 USD)
- Velocity checks (rapid successive transactions)
- Unusual timing patterns
- Cross-border transaction monitoring
- Currency conversion anomalies

---

## Sources

- [Claude Code Best Practices - Official Docs](https://code.claude.com/docs/en/best-practices)
- [Shipyard Claude Code Cheatsheet](https://shipyard.build/blog/claude-code-cheat-sheet/)
- [Writing a Good CLAUDE.md - HumanLayer](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- [Using CLAUDE.md Files - Claude Blog](https://claude.com/blog/using-claude-md-files)
- [Claude Code Spec Workflow](https://github.com/Pimzino/claude-code-spec-workflow)
- SPD Training Materials - Day 1 Workshop 3: Specification-Driven Development
- SPD Training Materials - Claude Code Reference Materials
