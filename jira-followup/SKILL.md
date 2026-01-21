---
name: jira-followup
description: Respond to follow-up comments on Jira tickets previously processed by jira-processor.
allowed-tools: Read, Grep, Glob, Bash, mcp__atlassian__getJiraIssue, mcp__atlassian__addCommentToJiraIssue, mcp__atlassian__atlassianUserInfo, mcp__atlassian__getAccessibleAtlassianResources, Skill
---

# Jira Follow-up Skill

Responds to new comments on tickets that jira-processor has already analyzed. This skill is designed to handle follow-up questions, corrections, or additional requests from other users on tickets where the current user has already commented.

## Invocation

Called automatically by jira-processor when it detects previous engagement, or manually:

| Mode | Command | Behavior |
|------|---------|----------|
| Basic | `/jira-followup ECWS-1234` | Process follow-up for specific ticket |
| With account ID | `/jira-followup ECWS-1234 --user-account-id abc123` | Skip API call for account ID |

## Workflow

Follow these steps in order:

### Step 1: Initialize

1. Parse arguments:
   - Extract ticket key from first argument
   - Check for `--user-account-id` flag to skip API call

2. Get user account ID (if not provided via flag):
   ```
   Use mcp__atlassian__atlassianUserInfo to get your account ID
   ```

3. Get the cloud ID:
   ```
   Use mcp__atlassian__getAccessibleAtlassianResources to get the cloud ID
   ```

### Step 2: Fetch Ticket with Comments

Fetch the full ticket including comments:
```
Use mcp__atlassian__getJiraIssue with:
- cloudId: (from step 1)
- issueIdOrKey: {TICKET-KEY}
- expand: "comment"
```

### Step 3: Find Comments

1. Get ALL comments made by current user (by account ID matching `author.accountId`)
2. Get the timestamp of the most recent comment by current user
3. Extract comments by OTHER users after that timestamp

Use the comment detector utilities:
```python
from utils.comment_detector import (
    find_user_comments,
    get_latest_user_comment,
    get_comments_after,
    has_followup_from_others
)
```

### Step 4: Check for New Comments

If no newer comments from others exist:
- Report: "No new comments to address on {TICKET-KEY}"
- Exit skill

### Step 5: Build Context

Gather context for the follow-up analysis:

```
Ticket: {TICKET-KEY}
Summary: {ticket summary}

Your Previous Comments:
{all formatted comments by current user, chronologically}

New Comments From Others (since your last comment):
{formatted new comments with author and timestamp}
```

### Step 6: Analyze New Comments

Read the new comments and determine what the other users are asking:
- Questions about the previous analysis
- Corrections or additional information
- Requests to check additional scenarios
- Follow-up investigations needed

### Step 7: Run Investigations (if needed)

If the new comments request additional investigation:

1. Load the repo config from `.claude/jira-config.yaml`
2. Check `investigation.available_skills` for relevant skills
3. Invoke skills as needed using the Skill tool

Examples:
- If asked to check a specific index: `/index-filter-test --isbn {isbn} --indices {index_name}`
- If asked to check a specific ISBN: `/index-filter-test --isbn {isbn}`
- If asked about code: Use Grep/Glob/Read to explore

### Step 8: Post Follow-up Comment

Use `mcp__atlassian__addCommentToJiraIssue` to post a contextual response:

Comment structure:
- Acknowledge the specific questions/requests from new comments
- Provide findings from any investigations run
- Answer questions based on context from previous analysis
- Include caveat: "Note: This is an automated follow-up analysis."

Example format:
```
Regarding your request to check {specific thing mentioned in new comments}:

{Investigation findings or answer to question}

{Additional context if relevant}

Note: This is an automated follow-up analysis.
```

## Communication Guidelines

- Reference specific points from the new comments
- Be specific about what was checked and what was found
- Use cautious language ("likely", "should", "appears to") since this is automated
- Keep responses focused on what was asked

## Error Handling

- **No ticket key provided**: Ask user to provide ticket key
- **Ticket not found**: Report error
- **No previous comments found**: Report "No previous engagement found on this ticket"
- **API failures**: Report error with details
