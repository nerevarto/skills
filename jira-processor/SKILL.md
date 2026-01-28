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
      epic_filter: null        # Optional: filter to tickets within specific epic
    - key: PROJECT2
      title_filter: null       # No filter - all assigned tickets
      epic_filter: "PROJ-100"  # Only tickets in this epic
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

# Optional: Ralph Wiggum iterative development configuration
ralph:
  enabled: true                    # Enable/disable Ralph loop for eligible tickets
  max_iterations: 10               # Maximum iterations before giving up
  completion_promise: "COMPLETE"   # Token to signal task completion

# Optional: code review configuration
review:
  enabled: true                    # Enable/disable review step (default: true)
  style_review: true               # Run code-review skill if available (default: true)
  deep_review: true                # Run deep-review skill if available (default: true)
  requirements_alignment: true     # Check diff against ticket requirements (default: true)
  max_fix_attempts: 3              # Max attempts to fix style review issues (default: 3)
  max_alignment_attempts: 2        # Max attempts to fix alignment issues (default: 2)
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
- If project has `epic_filter`, add: `AND "Epic Link" = {epic_filter}`

Use `mcp__atlassian__searchJiraIssuesUsingJql` with appropriate JQL.

### Step 3: Process Each Ticket

For each ticket, fetch full details including comments and classify:

#### 3a. Fetch Ticket with Comments

When fetching the ticket, include comments by using:
```
mcp__atlassian__getJiraIssue with:
- cloudId: (from step 1)
- issueIdOrKey: {TICKET-KEY}
- expand: "comment"
```

The response will include `fields.comment.comments[]` with each comment containing:
- `author.displayName`: Who wrote the comment
- `body`: Comment content in ADF format
- `created`: Timestamp

#### 3a-bis. Check for Previous Engagement

Before classifying, check if current user has already commented on the ticket:

1. Get current user's account ID (already retrieved in Step 1 from `atlassianUserInfo`)
2. Search comments where `author.accountId` matches current user's account ID
3. **If comments by current user found:**
   - Get timestamp of user's most recent comment
   - Check for comments by OTHER users after that timestamp
   - **If newer comments from others exist:** Delegate to jira-followup:
     ```
     Use Skill tool with:
     - skill: "jira-followup"
     - args: "{TICKET-KEY} --user-account-id {account_id}"
     ```
     Then continue to next ticket.
   - **If no newer comments from others:** Skip ticket (already handled, no follow-up needed)
     Log: "Skipping {TICKET-KEY}: Already processed, no new follow-up comments"
     Continue to next ticket.
4. **If current user has not commented:** Continue with normal classification (step 3b onwards)

Use the comment detector utilities:
```python
from utils.comment_detector import (
    find_user_comments,
    has_followup_from_others,
    get_latest_user_comment,
    get_comments_after
)

comments = ticket["fields"]["comment"]["comments"]
user_account_id = user_info["accountId"]

if find_user_comments(comments, user_account_id):
    if has_followup_from_others(comments, user_account_id):
        # Delegate to jira-followup skill
        pass
    else:
        # Skip - already handled, no new comments
        pass
else:
    # Process normally - first time seeing this ticket
    pass
```

#### 3b. Parse Comments

Extract plain text from ADF-formatted comments using the parser:
```python
from utils.adf_parser import parse_jira_comments, format_comments_for_analysis

# Parse the comments array from the Jira response
comments = parse_jira_comments(ticket["fields"]["comment"]["comments"])
# Format into a single string for the classifier
comments_text = format_comments_for_analysis(comments)
```

Or manually extract text from each comment's ADF body by recursively processing `content` nodes and extracting `text` values.

#### 3c. Classify Ticket Type

Run the classifier with comments included:
```bash
python ~/.claude/skills/jira-processor/scripts/analyze_ticket.py \
  --summary "TICKET_SUMMARY" \
  --description "TICKET_DESCRIPTION" \
  --comments "FORMATTED_COMMENTS" \
  --json
```

The classifier returns one of three types:

| Type | Action |
|------|--------|
| `CODE_CHANGE` | Implement code changes, verify, create PR |
| `INVESTIGATION` | Run diagnostics, add findings to Jira |
| `SKIP` | Log reason and continue to next ticket |

#### 3d. Handle SKIP Type

If type is `SKIP`:
1. Log: "Skipping {TICKET-KEY}: {reason}"
2. Continue to next ticket

#### 3e. Handle INVESTIGATION Type

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

#### 3f. Handle CODE_CHANGE Type

If type is `CODE_CHANGE`:

1. **Parse Requirements**
   - Read the ticket description carefully
   - Identify what code changes are needed
   - Use the `suggested_files` from the classifier output

2. **Check Ralph-Eligibility**

   The classifier output includes `ralph_eligibility` assessment:
   ```json
   {
     "eligible": true,
     "confidence": 0.8,
     "criteria_met": ["existing_tests", "specific_files"],
     "disqualifiers": [],
     "reason": "Ralph-eligible: existing_tests, specific_files"
   }
   ```

   A ticket is Ralph-eligible if it has **verifiable success criteria**:
   - Existing tests cover the affected area
   - Explicit test requirements in ticket ("add test", "ensure tests pass")
   - Build/lint criteria mentioned ("fix build", "type error")
   - Specific file/function references

   **Disqualifying factors:**
   - Vague language: "improve", "enhance", "better" without metrics
   - Design decisions required: "decide how to...", "choose between..."
   - No specific file/function scope

3. **Explore Codebase**
   - Use Grep/Glob to find relevant code
   - Read existing implementations for patterns
   - Understand the context before making changes

4. **Create Feature Branch**
   ```
   Use mcp__github__create_branch with:
   - owner: {from repo config}
   - repo: {from repo config}
   - branch: {branch_prefix}{TICKET-KEY}-{short-description}
   - from_branch: {base_branch from config}
   ```

5. **Implement Changes**

   **If Ralph-eligible AND `ralph.enabled` is true in config:**

   Invoke the Ralph Wiggum loop for iterative development:
   ```
   Use Skill tool with:
   - skill: "ralph-wiggum:ralph-loop"
   - args: (see prompt template below)
   ```

   Ralph loop prompt template:
   ```
   Implement {TICKET-KEY}: {summary}.

   Requirements:
   {description}

   Files to modify: {suggested_files}

   Success criteria:
   - All tests pass
   - Build succeeds
   - {any explicit acceptance criteria from ticket}

   Output <promise>COMPLETE</promise> when implementation is verified.
   --max-iterations {ralph.max_iterations from config, default 10}
   --completion-promise "{ralph.completion_promise from config, default COMPLETE}"
   ```

   The Ralph loop will iterate until success criteria are met or max iterations reached.

   **If NOT Ralph-eligible OR `ralph.enabled` is false:**

   Use single-pass implementation:
   - Make the required code changes using Edit tool
   - Follow existing patterns in the codebase
   - Keep changes minimal and focused

6. **Verification** (single-pass only, Ralph handles its own verification)

   For single-pass implementation, run verification loop (max 3 attempts):
   ```bash
   python ~/.claude/skills/jira-processor/scripts/verify_build.py --run-all --json
   ```

   If verification fails:
   - Analyze the failure output
   - Fix the issues
   - Re-run verification
   - After 3 failed attempts, log error and skip PR creation

7. **Code Review & Requirements Alignment** (runs for both Ralph loop and single-pass paths)

   Read the `review` section from `.claude/jira-config.yaml`. All sub-steps default to enabled when the section is absent.

   **7a. Stage changes for review**
   ```bash
   git add -A
   ```

   **7b. Run style/pattern review (conditional)**
   - Check if `.claude/skills/code-review/SKILL.md` exists in the project
   - If it exists and `review.style_review` is not `false`:
     - Invoke via `Skill` tool with `skill: "code-review"`
     - If errors found: fix issues, re-stage (`git add -A`), re-run (max `review.max_fix_attempts`, default 3 attempts)
   - If the skill file doesn't exist, skip gracefully

   **7c. Run architectural review (conditional)**
   - Check if `.claude/skills/deep-review/SKILL.md` exists in the project
   - If it exists and `review.deep_review` is not `false`:
     - Invoke via `Skill` tool with `skill: "deep-review"`
     - Advisory only: note significant issues for inclusion in PR description, but do not enter a fix loop
   - If the skill file doesn't exist, skip gracefully

   **7d. Requirements alignment review (always runs unless `review.requirements_alignment` is `false`)**
   - Run `git diff {base_branch}...HEAD` to see all changes on the branch
   - Compare the diff against the original ticket summary, description, and comments (already in context from Step 3)
   - Check:
     - Every ticket requirement has a corresponding code change
     - No drift beyond the ticket's scope
     - No obvious logic errors in the implementation
   - If misaligned: fix implementation, re-verify (re-run Step 6 if single-pass), re-review (max `review.max_alignment_attempts`, default 2 attempts)

8. **Create Pull Request**
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

   ## Review

   - [x] Style review passed (or "N/A" if skill not available)
   - [x] Architectural review passed (or "N/A" if skill not available)
   - [x] Requirements alignment verified against {TICKET-KEY}
   ```

9. **Add Comment to Jira**
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
**Ralph loops used:** {count}

### Details

| Ticket | Type | Ralph Used | Iterations | Result |
|--------|------|------------|------------|--------|
| PROJ-123 | CODE_CHANGE | Yes | 4 | PR #456 created |
| PROJ-789 | CODE_CHANGE | No | - | PR #457 created |
| PROJ-101 | INVESTIGATION | - | - | Comment added |
| PROJ-456 | SKIP | - | - | Blocked by external dependency |
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
