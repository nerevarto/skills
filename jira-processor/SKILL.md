---
name: jira-processor
description: Automatically process Jira tickets from configured projects. Query tickets assigned to current user, analyze actionability, implement code changes or run investigations, verify changes, and create PRs.
allowed-tools: Read, Grep, Glob, Bash, Edit, Write, mcp__atlassian__searchJiraIssuesUsingJql, mcp__atlassian__getJiraIssue, mcp__atlassian__atlassianUserInfo, mcp__atlassian__getAccessibleAtlassianResources, mcp__atlassian__addCommentToJiraIssue, mcp__github__create_branch, mcp__github__push_files, mcp__github__create_pull_request, mcp__github__list_pull_requests, Skill
---

# Jira Ticket Processor

Automatically process Jira tickets from configured projects, implementing code changes or running investigations based on ticket type.

## Configuration

This skill reads repo-specific configuration from `.claude/jira-config.yaml` (or `.claude/jira-config.json`) in each repository. If no config exists, the skill will not know which Jira projects to query.

### Required Config Structure

Create `.claude/jira-config.yaml` (or `.json`) in your repository:

```yaml
jira:
  projects:
    - key: PROJECT1
      title_filter: "Prefix*"  # Optional: filter by title pattern
    - key: PROJECT2
      title_filter: null       # No filter - all assigned tickets
  statuses:
    - "Open"
    - "In Progress"
    - "To Do"
  max_tickets_per_run: 10

github:
  owner: "YourOrg"
  repo: "your-repo"
  base_branch: "main"
  branch_prefix: "feature/"

verification:
  test_command: "python -m pytest"
  build_command: "docker-compose build"
  timeout_seconds: 300

# Optional: map keywords to code files
code_mapping:
  patterns:
    - keywords: [index, filter]
      files: [config/indexConfig.py]
    - keywords: [api, endpoint]
      files: [src/api/]

# Optional: map URLs to index names (for investigation tickets)
index_url_mapping:
  example.com: example-index
  staging.example.com: staging-index

# Optional: project context for investigation relevance checking
project:
  name: "Project Name"
  description: "Brief description of what this project does"
  domain_keywords:
    - keyword1
    - keyword2

# Optional: investigation configuration
investigation:
  # Skills available for diagnostics (skill name → description)
  available_skills:
    skill-name: "Description of when to use this skill"
  # Guidance for how to investigate issues in this project
  guidance: |
    When investigating issues in this project:
    - Guidance line 1
    - Guidance line 2
```

## Invocation

| Mode | Command | Behavior |
|------|---------|----------|
| Auto-query | `/jira-processor` | Query all matching tickets from configured projects |
| Single ticket | `/jira-processor PROJ-123` | Process specific ticket by ID |
| Multiple tickets | `/jira-processor PROJ-123 PROJ-456` | Process specific tickets |

## Communication Guidelines

When adding comments to Jira tickets, use cautious language since automated analysis can make mistakes:
- Use "likely", "probably", "should" instead of definitive statements
- Avoid claiming 100% certainty about outcomes
- Include disclaimers where appropriate

## Workflow

Follow these steps in order:

### Step 1: Initialize

1. Load repo configuration:
   - Read `.claude/jira-config.yaml` from current repo
   - If not found, inform user they need to create the config file

2. Get your Atlassian user info:
   ```
   Use mcp__atlassian__atlassianUserInfo to get your account ID
   ```

3. Get the cloud ID:
   ```
   Use mcp__atlassian__getAccessibleAtlassianResources to get the cloud ID
   ```

### Step 2: Query Tickets

**If specific ticket IDs were provided:**
- Fetch each ticket directly using `mcp__atlassian__getJiraIssue`

**If auto-query mode (no ticket IDs):**
- For each project in config, build JQL query:
  ```
  project = {PROJECT_KEY} AND assignee = currentUser() AND status in ({statuses})
  ```
- If project has `title_filter`, add: `AND summary ~ "{title_filter}"`

Use `mcp__atlassian__searchJiraIssuesUsingJql` with appropriate JQL.

### Step 3: Process Each Ticket

For each ticket, fetch full details and classify:

#### 3a. Classify Ticket Type

Run the classifier:
```bash
python ~/.claude/skills/jira-processor/scripts/analyze_ticket.py \
  --summary "TICKET_SUMMARY" \
  --description "TICKET_DESCRIPTION" \
  --json
```

The classifier returns one of three types:

| Type | Action |
|------|--------|
| `CODE_CHANGE` | Implement code changes, verify, create PR |
| `INVESTIGATION` | Run diagnostics, add findings to Jira |
| `SKIP` | Log reason and continue to next ticket |

#### 3b. Handle SKIP Type

If type is `SKIP`:
1. Log: "Skipping {TICKET-KEY}: {reason}"
2. Continue to next ticket

#### 3c. Handle INVESTIGATION Type

If type is `INVESTIGATION`:

1. **Load Project Context**
   - Read `project` section from `.claude/jira-config.yaml` for project description and domain keywords
   - Read `investigation` section for available skills and guidance

2. **Check Project Relevance**
   - Determine if the ticket relates to this codebase based on:
     - Domain keywords match (from `project.domain_keywords`)
     - Code/file references in ticket
     - URLs or identifiers relevant to this project
   - If not relevant: Skip with reason "Ticket not related to this project"

3. **Analyze the Issue**
   - Read investigation guidance from config (`investigation.guidance`)
   - Identify what needs to be investigated based on ticket content
   - If needed, explore relevant code using Grep/Glob/Read to understand the issue

4. **Run Diagnostics (if applicable)**
   - Check `investigation.available_skills` in config
   - If a skill is relevant to the issue, invoke it using the Skill tool
   - Example: For ISBN visibility issues with index-filter-test available, run `/index-filter-test --isbn {isbn}`

5. **Formulate Findings**
   - Based on code analysis and diagnostic results
   - Determine root cause or likely explanation
   - Suggest next steps or resolution

6. **Add Comment to Jira**
   ```
   Use mcp__atlassian__addCommentToJiraIssue with:
   - cloudId: (from step 1)
   - issueIdOrKey: {TICKET-KEY}
   - commentBody: Contextual findings based on actual analysis (not a template)
   ```

   Comment should include:
   - Brief summary of what was investigated
   - Findings from code analysis and/or diagnostic skills
   - Suggested next steps
   - Disclaimer: "Note: This is an automated analysis and may require manual verification."

7. Continue to next ticket

#### 3d. Handle CODE_CHANGE Type

If type is `CODE_CHANGE`:

1. **Parse Requirements**
   - Read the ticket description carefully
   - Identify what code changes are needed
   - Use the `suggested_files` from the classifier output

2. **Explore Codebase**
   - Use Grep/Glob to find relevant code
   - Read existing implementations for patterns
   - Understand the context before making changes

3. **Create Feature Branch**
   ```
   Use mcp__github__create_branch with:
   - owner: {from repo config}
   - repo: {from repo config}
   - branch: {branch_prefix}{TICKET-KEY}-{short-description}
   - from_branch: {base_branch from config}
   ```

4. **Implement Changes**
   - Make the required code changes using Edit tool
   - Follow existing patterns in the codebase
   - Keep changes minimal and focused

5. **Verification Loop** (max 3 attempts)

   Run verification:
   ```bash
   python ~/.claude/skills/jira-processor/scripts/verify_build.py --run-all --json
   ```

   If verification fails:
   - Analyze the failure output
   - Fix the issues
   - Re-run verification
   - After 3 failed attempts, log error and skip PR creation

6. **Create Pull Request**
   ```
   Use mcp__github__create_pull_request with:
   - owner: {from repo config}
   - repo: {from repo config}
   - title: [{TICKET-KEY}] {ticket summary}
   - body: (see template below)
   - head: {branch_prefix}{TICKET-KEY}-{short-description}
   - base: {base_branch from config}
   ```

   PR body template:
   ```markdown
   ## Summary

   Implements changes for [{TICKET-KEY}]({jira_base_url}/browse/{TICKET-KEY})

   {Brief description of changes}

   ## Changes

   - {List of files modified}
   - {Brief description of each change}

   ## Testing

   - [x] Tests pass
   - [x] Build succeeds

   ---
   🤖 Generated with Claude Code
   ```

7. **Add Comment to Jira**
   ```
   Use mcp__atlassian__addCommentToJiraIssue with:
   - commentBody: "PR created: {PR_URL}\n\nOnce merged and deployed, this should address the issue."
   ```

### Step 4: Generate Summary Report

After processing all tickets, output a summary:

```
## Jira Processor Summary

**Tickets processed:** {total}
**PRs created:** {count}
**Investigations completed:** {count}
**Tickets skipped:** {count}

### Details

| Ticket | Type | Result |
|--------|------|--------|
| PROJ-123 | CODE_CHANGE | PR #456 created |
| PROJ-789 | INVESTIGATION | Comment added |
| PROJ-456 | SKIP | Blocked by external dependency |
```

## Error Handling

- **Missing config**: Inform user to create `.claude/jira-config.yaml`
- **API failures**: Retry up to 3 times with backoff
- **Verification failures**: Fix and retry up to 3 times, then skip
- **Git conflicts**: Abort and log, do not force push
- **Unknown ticket type**: Default to SKIP with reason

## Safety Rules

1. Never force push to any branch
2. Never commit directly to main/master or the configured base branch
3. Always verify before creating PR
4. Only process tickets assigned to current user
5. Maximum tickets per run defined in config (default: 10)
