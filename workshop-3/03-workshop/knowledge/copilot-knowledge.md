# GitHub Copilot Comprehensive Guide

A complete reference for GitHub Copilot features, configuration, and best practices for AI-assisted development training.

---

## Table of Contents

1. [Custom Instructions (copilot-instructions.md)](#custom-instructions)
2. [Path-Specific Instructions](#path-specific-instructions)
3. [Prompt Files](#prompt-files)
4. [Agent Skills](#agent-skills)
5. [Chat Participants, Slash Commands, and Context Variables](#chat-syntax)
6. [Modes: Ask, Edit, and Agent](#modes)
7. [Copilot Coding Agent (Autonomous)](#coding-agent)
8. [Code Review](#code-review)
9. [Model Context Protocol (MCP)](#mcp)
10. [VS Code Settings and Configuration](#vscode-settings)
11. [Enterprise Policies and Content Exclusion](#enterprise-policies)
12. [Prompt Engineering Best Practices](#prompt-engineering)
13. [Resources](#resources)

---

## Custom Instructions

Custom instructions allow you to provide project-specific context and coding standards to Copilot.

### Repository-Level Instructions

Create a `.github/copilot-instructions.md` file in your repository root:

```markdown
# Project Context

This is a Node.js backend service using Express.js and PostgreSQL.
It follows a layered architecture with controllers, services, and repositories.

## Tech Stack
- Node.js 20+
- Express.js 4.x
- PostgreSQL with Prisma ORM
- Jest for testing

## Coding Standards
- Use TypeScript with strict mode enabled
- Follow ESLint airbnb-base configuration
- All functions must have JSDoc comments
- Use async/await over callbacks
- Prefer named exports over default exports

## Testing Requirements
- Unit tests for all service layer functions
- Integration tests for API endpoints
- Minimum 80% code coverage

## Error Handling
- Use custom error classes from src/errors/
- Always include error codes and messages
- Log errors with correlation IDs
```

### Best Practices for Instructions

1. **Keep it concise**: Instructions should be no longer than 2 pages
2. **Use self-contained statements**: Each guideline should be independently understandable
3. **Be specific**: Avoid ambiguous terms; be explicit about conventions
4. **Version control**: Treat it like documentation that evolves with your project
5. **Don't overthink it**: An imperfect file delivers more impact than nothing at all

### Let Copilot Generate Instructions

Ask Copilot coding agent to generate an instructions file for you:
> "Generate a copilot-instructions.md file based on the patterns and conventions in this codebase"

**Sources:**
- [Adding custom instructions for GitHub Copilot - GitHub Docs](https://copilot-instructions.md/)
- [5 tips for writing better custom instructions - GitHub Blog](https://github.blog/ai-and-ml/github-copilot/5-tips-for-writing-better-custom-instructions-for-copilot/)

---

## Path-Specific Instructions

For instructions that apply to specific file types or directories, create `*.instructions.md` files in `.github/instructions/`.

### File Structure

```
.github/
  copilot-instructions.md          # Global instructions
  instructions/
    react-components.instructions.md
    unit-tests.instructions.md
    api-endpoints.instructions.md
```

### Example: React Components

`.github/instructions/react-components.instructions.md`:

```markdown
---
applyTo:
  - "src/components/**/*.tsx"
  - "src/components/**/*.jsx"
---

# React Component Guidelines

## Component Structure
- Use functional components with hooks
- Place state declarations at the top
- Group related hooks together
- Extract complex logic to custom hooks

## Naming Conventions
- PascalCase for component names
- camelCase for props and state
- Use descriptive prop names

## Props
- Define prop types with TypeScript interfaces
- Place interface definition above component
- Use destructuring in function parameters

## Styling
- Use CSS Modules for styling
- Follow BEM naming convention for class names
```

### Example: Unit Tests

`.github/instructions/unit-tests.instructions.md`:

```markdown
---
applyTo:
  - "**/*.test.ts"
  - "**/*.test.tsx"
  - "**/*.spec.ts"
---

# Unit Test Guidelines

## Framework
- Use Jest with React Testing Library
- Use jest.mock() for external dependencies

## Structure
- Use describe blocks for grouping
- Use 'it' for individual tests
- Follow Arrange-Act-Assert pattern

## Naming
- Test names should describe the expected behavior
- Format: "should [expected behavior] when [condition]"

## Coverage
- Test happy path first
- Include edge cases and error scenarios
- Mock external services and APIs
```

**Sources:**
- [Unlocking the full power of Copilot code review - GitHub Blog](https://github.blog/ai-and-ml/unlocking-the-full-power-of-copilot-code-review-master-your-instructions-files/)
- [Custom instructions in VS Code](https://code.visualstudio.com/docs/copilot/customization/custom-instructions)

---

## Prompt Files

Prompt files define reusable prompts for specific tasks that you can invoke on-demand. They enable creating a library of standardized development workflows.

### File Location and Format

Store prompt files in `.github/prompts/` with the `.prompt.md` extension:

```
.github/
  prompts/
    create-api-endpoint.prompt.md
    generate-unit-tests.prompt.md
    code-review-checklist.prompt.md
    refactor-component.prompt.md
```

### Prompt File Structure

```markdown
---
mode: agent
model: claude-sonnet-4
tools:
  - filesystem
  - terminal
description: "Generate a new REST API endpoint with tests"
---

# Create REST API Endpoint

Create a new REST API endpoint with the following specifications:

## Requirements
- Follow existing patterns in src/controllers/
- Include request validation using Zod
- Add comprehensive error handling
- Create corresponding service layer function
- Generate unit tests with >80% coverage

## Endpoint Details
- Route: ${input:route}
- HTTP Method: ${input:method}
- Description: ${input:description}

## Files to Create/Modify
1. Controller in src/controllers/
2. Service in src/services/
3. Route registration in src/routes/
4. Tests in src/__tests__/

Reference the existing patterns in #file:src/controllers/userController.ts
```

### YAML Frontmatter Options

| Option | Description | Values |
|--------|-------------|--------|
| `mode` | Copilot interaction mode | `ask`, `edit`, `agent` |
| `model` | AI model to use | `gpt-4o`, `claude-sonnet-4`, etc. |
| `tools` | Tools available to agent | `filesystem`, `terminal`, etc. |
| `description` | Brief description of the prompt | Free text |

### Using Prompt Files

1. **Via slash command**: Type `/prompt-name` in Copilot Chat
2. **Via hashtag**: Type `#prompt:prompt-name`
3. **From command palette**: Search for "Run Prompt"

### Best Practices

- Reference other markdown files using links: `[coding-standards](../copilot-instructions.md)`
- Use built-in variables: `${selection}`, `${file}`, `${input:variable-name}`
- Keep prompts focused on single tasks
- Include examples of expected output

**Sources:**
- [Use prompt files in VS Code](https://code.visualstudio.com/docs/copilot/customization/prompt-files)
- [Prompt files - GitHub Docs](https://docs.github.com/en/copilot/tutorials/customization-library/prompt-files)
- [Boost Your Copilot Collaboration with Reusable Prompt Files - Visual Studio Blog](https://devblogs.microsoft.com/visualstudio/boost-your-copilot-collaboration-with-reusable-prompt-files/)

---

## Agent Skills

Agent Skills are folders containing instructions, scripts, and resources that Copilot automatically loads when relevant to your prompt. They enable specialized capabilities and workflows.

### Creating a Skill

```
.github/
  skills/
    webapp-testing/
      SKILL.md
      scripts/
        run-e2e-tests.sh
      examples/
        test-example.ts
```

### SKILL.md Structure

```markdown
---
name: webapp-testing
description: "Run end-to-end tests for web applications using Playwright"
---

# Web Application Testing Skill

This skill provides capabilities for running E2E tests on web applications.

## When to Use
- When asked to run end-to-end tests
- When asked to verify web application functionality
- When debugging failing E2E tests

## Available Commands
- `npm run test:e2e` - Run all E2E tests
- `npm run test:e2e -- --headed` - Run with browser visible
- `npm run test:e2e -- --debug` - Run in debug mode

## Test Patterns
Tests are located in `tests/e2e/` and follow the pattern:
- `*.spec.ts` for test files
- `*.page.ts` for page objects

## Example Usage
To run tests for a specific feature:
```bash
npm run test:e2e -- --grep "login"
```
```

### YAML Frontmatter Requirements

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier (lowercase, hyphens for spaces) |
| `description` | Yes | What the skill does and when Copilot should use it |

### Skill Locations

- **Project-level**: `.github/skills/` in your repository
- **Personal**: `~/.copilot/skills/` (shared across projects)
- **Organization-level**: Coming soon

### Availability

Agent Skills work with:
- Copilot coding agent
- GitHub Copilot CLI
- VS Code Insiders (agent mode)

**Sources:**
- [About Agent Skills - GitHub Docs](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills)
- [Use Agent Skills in VS Code](https://code.visualstudio.com/docs/copilot/customization/agent-skills)
- [GitHub Copilot now supports Agent Skills - GitHub Changelog](https://github.blog/changelog/2025-12-18-github-copilot-now-supports-agent-skills/)

---

## Chat Participants, Slash Commands, and Context Variables

### Chat Participants (@)

Chat participants are domain experts that specialize in specific areas. Type `@` to see available participants.

| Participant | Description | Example Use |
|-------------|-------------|-------------|
| `@workspace` | Knows your entire codebase | "How is authentication implemented?" |
| `@terminal` | Terminal and command expertise | "How do I run tests?" |
| `@vscode` | VS Code features and settings | "How do I configure formatting?" |
| `@github` | GitHub features and repositories | "Show recent PRs" |

**Usage**: `@workspace How does the payment processing work?`

### Slash Commands (/)

Slash commands are shortcuts for common actions. Type `/` to see available commands.

| Command | Description |
|---------|-------------|
| `/explain` | Explain selected code |
| `/fix` | Fix issues in selected code |
| `/tests` | Generate unit tests |
| `/doc` | Generate documentation comments |
| `/help` | Show available commands |
| `/clear` | Clear chat history |
| `/new` | Start a new conversation |

**Usage**: `/explain` with code selected, or `/tests for the calculateTax function`

### Context Variables (#)

Context variables specify files, code, or other context for your prompt.

| Variable | Description | Example |
|----------|-------------|---------|
| `#file:path` | Reference a specific file | `#file:src/utils/helpers.ts` |
| `#selection` | Currently selected code | `Explain #selection` |
| `#codebase` | Your entire codebase | `Find all usages of #codebase` |
| `#terminalLastCommand` | Last terminal command | `Why did #terminalLastCommand fail?` |
| `#terminalSelection` | Selected terminal output | `Explain this error #terminalSelection` |

**Combining Syntax**:
```
@workspace /explain #file:src/auth/middleware.ts
```

**Sources:**
- [GitHub Copilot Chat cheat sheet - GitHub Docs](https://docs.github.com/en/copilot/reference/cheat-sheet)
- [Manage context for AI - VS Code](https://code.visualstudio.com/docs/copilot/chat/copilot-chat-context)
- [Code Faster and Better with GitHub Copilot's New Features - Visual Studio Blog](https://devblogs.microsoft.com/visualstudio/copilot-chat-slash-commands-and-context-variables/)

---

## Modes: Ask, Edit, and Agent

GitHub Copilot in VS Code offers three interaction modes, each with different capabilities.

### Ask Mode

**Purpose**: Get answers and explanations without modifying files.

**Capabilities**:
- Answer questions about code
- Explain algorithms and patterns
- Provide documentation
- Generate code snippets (displayed, not applied)

**Best For**:
- Learning and understanding code
- Research and exploration
- Getting recommendations

### Edit Mode

**Purpose**: Make changes directly to your files.

**Capabilities**:
- Suggest inline code changes
- Create new files
- Modify existing code
- Multi-file editing in a single session

**Usage**:
1. Select files to include in the edit session
2. Describe the changes you want
3. Review proposed changes inline
4. Accept or reject each change

**Best For**:
- Well-defined, scoped tasks
- Single-feature implementations
- Code refactoring

### Agent Mode

**Purpose**: Autonomous operation for complex, multi-step tasks.

**Capabilities**:
- Autonomously determines relevant files
- Executes terminal commands
- Iterates until task is complete
- Self-corrects based on errors
- Runs tests and validates changes

**How It Works**:
1. Receives high-level prompt
2. Plans the steps needed
3. Selects files to modify
4. Makes code changes
5. Runs terminal commands (build, test)
6. Iterates if errors occur

**Best For**:
- Multi-file changes
- Tasks requiring terminal commands
- Open-ended problems
- Feature implementation across layers

### Switching Modes

Click the mode selector in the bottom-left corner of the Copilot Chat panel, or use:
- `@workspace` for codebase-aware questions (Ask-like)
- Select "Edit" or "Agent" from the dropdown

### Usage Considerations

| Aspect | Ask | Edit | Agent |
|--------|-----|------|-------|
| Speed | Fast | Medium | Slower |
| Autonomy | None | Low | High |
| File changes | No | Yes | Yes |
| Terminal access | No | No | Yes |
| Premium requests | Low | Medium | High |

**Recommendation**: Start with Edit mode for well-defined tasks. Use Agent mode when you need multiple edits, terminal commands, or more open-ended exploration.

**Sources:**
- [Copilot ask, edit, and agent modes - GitHub Blog](https://github.blog/ai-and-ml/github-copilot/copilot-ask-edit-and-agent-modes-what-they-do-and-when-to-use-them/)
- [Introducing GitHub Copilot agent mode - VS Code Blog](https://code.visualstudio.com/blogs/2025/02/24/introducing-copilot-agent-mode)
- [GitHub Copilot Introduces Agent Mode - GitHub Newsroom](https://github.com/newsroom/press-releases/agent-mode)

---

## Copilot Coding Agent (Autonomous)

The Copilot coding agent is an autonomous AI developer that works independently to complete development tasks, creating pull requests for your review.

### How It Works

1. **Trigger**: Assign a GitHub issue to Copilot or delegate from chat
2. **Environment**: Agent spins up secure development environment via GitHub Actions
3. **Planning**: Agent analyzes the task and plans the implementation
4. **Execution**: Makes code changes, runs tests, iterates on errors
5. **Pull Request**: Creates a draft PR with all changes
6. **Review**: You review, comment, and the agent revises as needed

### Invoking the Coding Agent

**From GitHub Issues**:
1. Open an issue
2. Assign `@copilot` as the assignee
3. Watch the agent work in the PR

**From Copilot Chat (VS Code)**:
```
"Create a PR that adds input validation to the user registration endpoint"
```

**From GitHub CLI**:
```bash
gh copilot pr create --issue 123
```

### Best Practices for Issues

Write clear, specific issues:

```markdown
## Feature Request: Add Rate Limiting to API

### Description
Implement rate limiting for all public API endpoints to prevent abuse.

### Requirements
- Limit: 100 requests per minute per IP
- Return 429 status code when exceeded
- Include `X-RateLimit-Remaining` header
- Store counts in Redis

### Acceptance Criteria
- [ ] Rate limiter middleware created
- [ ] Applied to all routes in src/routes/public/
- [ ] Unit tests with >90% coverage
- [ ] Integration tests for rate limit behavior
```

### Capabilities

- Low-to-medium complexity tasks
- Adding features and fixing bugs
- Extending tests
- Refactoring code
- Improving documentation
- Works best in well-tested codebases

### Security & Compliance

- Existing branch protections still apply
- PRs require human approval before CI/CD runs
- The person who assigned the issue cannot approve the PR
- Full audit trail of agent actions

### Pricing

Starting June 2025, coding agent uses one premium request per model request.

**Sources:**
- [About GitHub Copilot coding agent - GitHub Docs](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent)
- [GitHub Copilot: Meet the new coding agent - GitHub Blog](https://github.blog/news-insights/product-news/github-copilot-meet-the-new-coding-agent/)
- [Assigning and completing issues with coding agent - GitHub Blog](https://github.blog/ai-and-ml/github-copilot/assigning-and-completing-issues-with-coding-agent-in-github-copilot/)

---

## Code Review

Copilot can automatically review pull requests and provide feedback with suggested fixes.

### Requesting a Review

**On-Demand**:
1. Open a pull request
2. Click "Request review"
3. Select "Copilot" as a reviewer

**Automatic Reviews**:
Configure repository rules to trigger Copilot review on:
- PR creation
- Each push to the PR
- Draft pull requests

### Configuration

Navigate to Repository Settings > Rules > Rulesets:

```yaml
# Example ruleset configuration
name: Copilot Auto Review
target: branch
conditions:
  ref_name:
    include: ["*"]
rules:
  - type: copilot_code_review
    parameters:
      run_on_push: true
      run_on_drafts: true
```

### Custom Coding Guidelines

Create guidelines for Copilot to enforce during reviews.

Repository Settings > Code review > Coding guidelines:

```markdown
## Security Guidelines
- Never log sensitive data (passwords, tokens, PII)
- Always validate and sanitize user input
- Use parameterized queries for database operations

## Performance Guidelines
- Avoid N+1 queries in loops
- Use pagination for list endpoints
- Cache frequently accessed data

## Code Style
- Maximum function length: 50 lines
- Maximum cyclomatic complexity: 10
- All public methods must have documentation
```

### Review Behavior

- Copilot leaves "Comment" reviews (not "Approve" or "Request changes")
- Reviews don't count toward required approvals
- Reviews don't block merging
- Suggested fixes can be applied with one click

### New Features (2025)

- `@copilot` mentions in PR comments trigger automatic fixes
- Stacked PRs created for suggested changes
- Organizations can enable reviews for contributors without Copilot licenses

**Sources:**
- [Using GitHub Copilot code review - GitHub Docs](https://docs.github.com/copilot/using-github-copilot/code-review/using-copilot-code-review)
- [Copilot code review now generally available - GitHub Changelog](https://github.blog/changelog/2025-04-04-copilot-code-review-now-generally-available/)
- [Configuring coding guidelines - GitHub Docs](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/request-a-code-review/configure-coding-guidelines)

---

## Model Context Protocol (MCP)

MCP is an open standard that connects AI models to external tools and data sources.

### Overview

MCP allows Copilot to:
- Access external services and APIs
- Use tools beyond its built-in capabilities
- Integrate with development infrastructure

### GitHub MCP Server

GitHub provides an official MCP server with tools for:
- Listing and searching repositories
- Creating and managing pull requests
- Working with issues and projects
- Accessing repository content

### Setting Up MCP in VS Code

1. Enable MCP in VS Code settings:
```json
{
  "github.copilot.chat.mcp.enabled": true
}
```

2. Configure MCP servers in `.vscode/mcp.json`:
```json
{
  "servers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-github"],
      "env": {
        "GITHUB_TOKEN": "${env:GITHUB_TOKEN}"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-filesystem", "/path/to/allowed/dir"]
    }
  }
}
```

### Using MCP with Coding Agent

The coding agent can use MCP tools during autonomous work:

```markdown
<!-- In your issue description -->
Use the Jira MCP server to:
1. Fetch ticket details from PROJ-123
2. Update ticket status when PR is created
```

### Available MCP Servers

- **GitHub**: Repository management, PRs, issues
- **Filesystem**: File operations outside workspace
- **Database**: Query databases directly
- **Slack**: Send notifications
- **Custom**: Build your own servers

### Policy Configuration (Enterprise)

Enterprises can enable/disable MCP via policies:
- Settings > Copilot > Policies > MCP servers
- Disabled by default for Business/Enterprise
- Not governed by policy for Free/Pro/Pro+

**Sources:**
- [About Model Context Protocol - GitHub Docs](https://docs.github.com/en/copilot/concepts/context/mcp)
- [Extending Copilot Chat with MCP - GitHub Docs](https://docs.github.com/copilot/customizing-copilot/using-model-context-protocol/extending-copilot-chat-with-mcp)
- [Use MCP servers in VS Code](https://code.visualstudio.com/docs/copilot/customization/mcp-servers)

---

## VS Code Settings and Configuration

### Essential Settings

Add to `.vscode/settings.json` for project-specific configuration:

```json
{
  // Enable/disable Copilot for specific languages
  "github.copilot.enable": {
    "*": true,
    "plaintext": false,
    "markdown": true,
    "scminput": false
  },

  // Enable inline suggestions
  "editor.inlineSuggest.enabled": true,

  // Configure suggestion behavior
  "github.copilot.editor.enableAutoCompletions": true,

  // Enable chat features
  "github.copilot.chat.enabled": true,

  // Configure MCP
  "github.copilot.chat.mcp.enabled": true,

  // Agent mode settings
  "github.copilot.chat.agent.enabled": true,

  // Custom instructions
  "github.copilot.chat.codeGeneration.useInstructionFiles": true
}
```

### Keybindings

Add to `keybindings.json`:

```json
[
  {
    "key": "tab",
    "command": "editor.action.inlineSuggest.commit",
    "when": "inlineSuggestionVisible"
  },
  {
    "key": "escape",
    "command": "editor.action.inlineSuggest.hide",
    "when": "inlineSuggestionVisible"
  },
  {
    "key": "alt+]",
    "command": "editor.action.inlineSuggest.showNext",
    "when": "inlineSuggestionVisible"
  },
  {
    "key": "alt+[",
    "command": "editor.action.inlineSuggest.showPrevious",
    "when": "inlineSuggestionVisible"
  },
  {
    "key": "cmd+i",
    "command": "github.copilot.chat.focus"
  },
  {
    "key": "cmd+shift+i",
    "command": "github.copilot.chat.inline.focus"
  }
]
```

### GitHub Enterprise Configuration

```json
{
  "github.copilot.advanced": {
    "authProvider": "github-enterprise"
  },
  "github-enterprise.uri": "https://github.your-company.com"
}
```

### VS Code Profiles for Teams

Create a `.code-profile` file to share settings across your team:

1. File > Preferences > Profiles > Create Profile
2. Select: Settings, Extensions, Keybindings
3. Export as `.code-profile` file
4. Commit to repository

### Recommended Extensions

- **GitHub Copilot** (required)
- **GitHub Copilot Chat** (required)
- **GitHub Pull Requests and Issues**
- **GitLens** (enhanced git integration)

**Sources:**
- [GitHub Copilot in VS Code settings reference](https://code.visualstudio.com/docs/copilot/reference/copilot-settings)
- [Set up GitHub Copilot in VS Code](https://code.visualstudio.com/docs/copilot/setup)
- [Managing GitHub Copilot & VS Code Settings Across Teams](https://dev.to/pwd9000/managing-github-copilot-vs-code-settings-across-teams-1phj)

---

## Enterprise Policies and Content Exclusion

### Content Exclusion

Control which files Copilot can access to generate suggestions.

**Effects of Exclusion**:
- No code completions in excluded files
- Excluded content won't inform suggestions in other files
- Excluded files won't be used in chat responses
- Excluded files won't be reviewed in code review

### Configuring Content Exclusions

**Repository Level** (Settings > Copilot > Content exclusion):

```yaml
# Exclude all files in secrets directory
"*":
  - "secrets/**"
  - "**/.env*"
  - "**/credentials*"

# Exclude specific file types
"*":
  - "**/*.pem"
  - "**/*.key"
  - "**/*.cert"
```

**Organization Level**:
Navigate to Organization Settings > Copilot > Content exclusion

**Enterprise Level**:
Navigate to Enterprise Settings > Policies > Copilot > Content Exclusions

### Policy Hierarchy

1. Enterprise-level rules apply to all users
2. If enterprise rules exist, org rules only apply to that org's Copilot seats
3. Repository rules are additive to org/enterprise rules

### Available Policies

| Policy | Description |
|--------|-------------|
| Copilot in IDE | Enable/disable code completions |
| Copilot Chat in IDE | Enable/disable chat features |
| Copilot on GitHub.com | Enable/disable web features |
| MCP Servers | Enable/disable MCP integration |
| Suggestions matching public code | Block/allow matches to public code |

### Limitations

Content exclusion does NOT apply to:
- GitHub Copilot CLI
- Copilot coding agent
- Agent mode in Copilot Chat

**Note**: Changes take up to 30 minutes to apply in IDEs.

**Sources:**
- [Excluding content from GitHub Copilot - GitHub Docs](https://docs.github.com/en/copilot/how-tos/configure-content-exclusion/exclude-content-from-copilot)
- [Content exclusion for GitHub Copilot - GitHub Docs](https://docs.github.com/en/copilot/concepts/context/content-exclusion)
- [Managing policies for Copilot in your organization - GitHub Docs](https://docs.github.com/copilot/managing-copilot/managing-github-copilot-in-your-organization/managing-github-copilot-features-in-your-organization/managing-policies-for-copilot-in-your-organization)

---

## Prompt Engineering Best Practices

### The SCOPE Framework

**S - Specific**: Be explicit about what you want
```
Bad:  "Make this better"
Good: "Refactor this function to use async/await instead of callbacks"
```

**C - Context**: Provide relevant background
```
Bad:  "Write a function to validate input"
Good: "Write a function to validate user registration input according to our UserSchema in #file:types/user.ts"
```

**O - Output Format**: Specify desired format
```
Good: "Generate a unit test using Jest with describe/it blocks and AAA pattern"
```

**P - Purpose**: Explain why you need it
```
Good: "Create a caching layer for API responses to reduce database load during high traffic"
```

**E - Examples**: Provide examples when helpful
```
Good: "Format error responses like: { error: { code: 'VALIDATION_ERROR', message: '...' } }"
```

### Inline Completion Tips

1. **Write descriptive comments first**:
```javascript
// Calculate the compound interest for a given principal, rate, and time period
// Using the formula: A = P(1 + r/n)^(nt)
function calculateCompoundInterest(
```

2. **Name variables descriptively**:
```python
# Good - clear intent
user_email_validation_result =

# Bad - ambiguous
result =
```

3. **Open relevant files**: Copilot uses open tabs for context

4. **Start with function signature**:
```typescript
async function fetchUserOrders(
  userId: string,
  options: { limit?: number; offset?: number }
): Promise<Order[]> {
```

### Chat Prompt Patterns

**Pattern 1: Explain First**
```
I have a React component that renders a list of items with infinite scroll.
It currently fetches all data at once, causing performance issues.

Help me refactor it to:
1. Fetch data in pages of 20 items
2. Load more when user scrolls to bottom
3. Show loading indicator during fetch
```

**Pattern 2: Constraints First**
```
Constraints:
- Must use existing AuthService class
- Must maintain backward compatibility
- No new dependencies

Task: Add OAuth2 support to the authentication flow
```

**Pattern 3: Step-by-Step**
```
Let's implement a rate limiter step by step:

Step 1: Create the RateLimiter class with a constructor that accepts requests per minute
```

### Iterating on Results

1. **If suggestion is close but not right**:
   - Accept it and ask for modifications
   - "Now modify this to handle the edge case where..."

2. **If suggestion is wrong direction**:
   - Clear and rephrase with more context
   - Add examples of what you want

3. **If suggestion uses wrong patterns**:
   - Reference existing code: "Follow the pattern in #file:existing-example.ts"

### What to Avoid

- **Ambiguous pronouns**: "Fix this" → "Fix the null check in the validateUser function"
- **Multiple unrelated requests**: Break into separate prompts
- **Assuming context**: Always reference specific files
- **Generic requests**: "Make it better" → "Improve error handling by adding try-catch blocks and descriptive error messages"

**Sources:**
- [Best practices for using GitHub Copilot - GitHub Docs](https://docs.github.com/en/copilot/get-started/best-practices)
- [How to write better prompts - GitHub Blog](https://github.blog/developer-skills/github/how-to-write-better-prompts-for-github-copilot/)
- [Prompt engineering for GitHub Copilot Chat - GitHub Docs](https://docs.github.com/en/copilot/concepts/prompting/prompt-engineering)
- [Prompt engineering in VS Code](https://code.visualstudio.com/docs/copilot/guides/prompt-engineering-guide)

---

## Resources

### Official Documentation

- [GitHub Copilot Documentation](https://docs.github.com/en/copilot)
- [VS Code Copilot Documentation](https://code.visualstudio.com/docs/copilot/overview)
- [GitHub Copilot Features](https://docs.github.com/en/copilot/get-started/features)
- [GitHub Copilot Cheat Sheet](https://docs.github.com/en/copilot/reference/cheat-sheet)

### Community Resources

- [awesome-copilot Repository](https://github.com/github/awesome-copilot) - Community-contributed instructions, prompts, and configurations
- [GitHub Copilot Community Discussions](https://github.com/orgs/community/discussions/categories/copilot)

### Training & Learning

- [Introduction to GitHub Copilot - Microsoft Learn](https://learn.microsoft.com/en-us/training/modules/introduction-to-github-copilot/)
- [GitHub Copilot Fundamentals - GitHub Skills](https://skills.github.com/)
- [Prompt Engineering with GitHub Copilot - Microsoft Learn](https://learn.microsoft.com/en-us/training/modules/introduction-prompt-engineering-with-github-copilot/)

### Changelog & Updates

- [GitHub Changelog - Copilot](https://github.blog/changelog/label/copilot/)
- [VS Code Release Notes](https://code.visualstudio.com/updates)

---

## Quick Reference Card

### Keyboard Shortcuts (VS Code)

| Action | Windows/Linux | macOS |
|--------|---------------|-------|
| Accept suggestion | `Tab` | `Tab` |
| Dismiss suggestion | `Esc` | `Esc` |
| Next suggestion | `Alt+]` | `Option+]` |
| Previous suggestion | `Alt+[` | `Option+[` |
| Open Copilot Chat | `Ctrl+I` | `Cmd+I` |
| Inline Chat | `Ctrl+Shift+I` | `Cmd+Shift+I` |

### Essential Files

```
.github/
  copilot-instructions.md       # Global project instructions
  instructions/
    *.instructions.md           # Path-specific instructions
  prompts/
    *.prompt.md                 # Reusable prompts
  skills/
    skill-name/
      SKILL.md                  # Skill definition
```

### Chat Syntax Quick Reference

```
@workspace     - Query entire codebase
@terminal      - Terminal expertise
@github        - GitHub features
/explain       - Explain code
/fix           - Fix issues
/tests         - Generate tests
/doc           - Generate docs
#file:path     - Reference file
#selection     - Selected code
#codebase      - Full codebase
```

---

*Last updated: January 2025*
