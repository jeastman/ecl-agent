# Policy Guide

This document explains the `[policy]` table in the runtime TOML in practical, implementation-level detail.

The most important fact up front is this:

- The `[policy]` table is intentionally open-ended.
- The loader only requires that `policy` is a TOML table.
- The current runtime only enforces a small set of keys.
- Any other keys are preserved, surfaced through `config.get`, and redacted if their names look sensitive, but they do not change runtime behavior unless code explicitly reads them.

If you want a policy that actually changes what the runtime allows, pauses, or denies, the keys that matter today are:

- `safe_command_classes`
- `deny_command_classes`
- `web_access_mode`

Two other keys appear in the example config and in UI output, but are not currently enforced by the runtime policy engine:

- `approval_mode`
- `sandbox_mode`

## Where Policy Applies

The runtime evaluates governed operations and returns one of three outcomes:

- `ALLOW`
- `REQUIRE_APPROVAL`
- `DENY`

Today, policy decisions are applied to these operation types:

- file writes
- command execution
- memory writes
- skill installation
- MCP server connection
- web fetch/search

Not every one of those behaviors is configurable. Some are hard-coded safety rules and approval boundaries.

## Mental Model

Think of policy as three layers:

1. Hard-coded safety invariants
2. Configurable policy knobs
3. Run-scoped approval reuse

### 1. Hard-coded safety invariants

These are enforced even if your policy is very permissive:

- Writes under `/.memory/identity/` are denied.
- Memory writes to `identity` scope are denied.
- Project memory writes into namespaces starting with `identity.` are denied.
- Skill install targets containing `..` are denied.
- Writes to `/workspace/artifacts/**`, `/tmp/**`, and `/.memory/**` do not require approval.
- `rm` commands that only target `/tmp/**` are allowed even though `rm` is normally classified as destructive.

### 2. Configurable policy knobs

These are the actual operator-controlled settings in the current runtime:

- which command classes are safe by default
- which command classes are always denied
- how outbound web access is handled

### 3. Run-scoped approval reuse

When an operation requires approval, the runtime derives a stable boundary key. If that boundary is approved once for the same task and run, future matching operations are allowed automatically for that run only.

Examples:

- approving a write boundary for `/workspace/src/**` allows later writes in that subtree during the same run
- approving web access to `example.com` allows later fetch/search operations to that host during the same run
- approving a `network` command in `/workspace` would only matter if your policy allows approval instead of outright denial for that command class

Approvals do not automatically carry to a different run.

## Supported Keys

### `safe_command_classes`

Type:

```toml
safe_command_classes = ["safe_read", "safe_exec"]
```

Purpose:

- Controls which command classes are allowed without approval.
- Only affects `command.execute`.

Default if omitted:

```toml
safe_command_classes = ["safe_read", "safe_exec"]
```

Validation behavior:

- Must be an array of strings to take effect.
- If the value is not a string array, the runtime silently falls back to the default set.
- Empty strings inside the list are ignored.

What it means:

- If a command class is in `safe_command_classes`, it is allowed unless it is also denied by `deny_command_classes`.
- If a command class is not in `safe_command_classes`, it requires approval unless it is denied outright.

Current command classifier:

- `network`: `curl`, `wget`, `nc`, `telnet`
- `destructive`: `rm`, `dd`, `mkfs`, `shutdown`, `reboot`
- `safe_read`: `ls`, `find`, `rg`, `grep`, `cat`, `sed`, `head`, `tail`, `wc`, `pwd`, `git`
- `safe_exec`: everything else, plus `python -c` and `python3 -c`

Important implications:

- Most commands you do not explicitly recognize will land in `safe_exec`.
- If you remove `safe_exec` from `safe_command_classes`, most non-read commands will start requiring approval.
- `git` is currently treated as `safe_read` even though some git subcommands can mutate state. The classifier is command-head based, not subcommand aware.

Examples:

Strict:

```toml
safe_command_classes = ["safe_read"]
```

Effect:

- `ls`, `rg`, `cat`, `git status` are allowed
- `python script.py` requires approval
- `bash script.sh` requires approval
- `curl https://example.com` is still denied by default because it is `network`

Balanced:

```toml
safe_command_classes = ["safe_read", "safe_exec"]
```

Effect:

- reads and ordinary execution are allowed
- `network`, `destructive`, and `secrets` behavior depends on `deny_command_classes`

Very lax:

```toml
safe_command_classes = ["safe_read", "safe_exec", "network"]
```

Effect:

- network commands no longer require approval
- but they are still denied if `network` remains in `deny_command_classes`

### `deny_command_classes`

Type:

```toml
deny_command_classes = ["destructive", "network", "secrets"]
```

Purpose:

- Controls which command classes are always denied.
- Only affects `command.execute`.

Default if omitted:

```toml
deny_command_classes = ["destructive", "network", "secrets"]
```

Validation behavior:

- Must be an array of strings to take effect.
- If the value is not a string array, the runtime silently falls back to the default set.
- Empty strings inside the list are ignored.

What it means:

- If a command class is listed here, the command is denied before the runtime considers approval.
- Deny wins over allow.

Important implications:

- `network` commands are denied by default.
- `destructive` commands are denied by default.
- `secrets` is denied by default even though the current command classifier does not produce `secrets` for shell commands. It is effectively reserved for present or future higher-risk classifications.
- Scratch-only `rm` operations targeting `/tmp/**` are a special case and remain allowed even when `destructive` is denied.

Examples:

Default:

```toml
deny_command_classes = ["destructive", "network", "secrets"]
```

Effect:

- `curl`, `wget`, `nc`, `telnet` are denied
- `rm file.txt` is denied unless every target resolves under `/tmp/**`

Approval-friendly:

```toml
deny_command_classes = ["destructive", "secrets"]
safe_command_classes = ["safe_read", "safe_exec"]
```

Effect:

- network commands are no longer denied
- because `network` is not in `safe_command_classes`, they require approval
- destructive commands remain denied except scratch-only `rm`

Very lax:

```toml
deny_command_classes = []
safe_command_classes = ["safe_read", "safe_exec", "network", "destructive", "secrets"]
```

Effect:

- almost every command class is allowed without approval
- scratch-only special casing still applies, but no longer matters much

Dangerous middle ground:

```toml
deny_command_classes = []
safe_command_classes = ["safe_read", "safe_exec"]
```

Effect:

- `network` and `destructive` commands are no longer denied
- they require approval instead
- this is often a better choice than fully allowing them

### `web_access_mode`

Type:

```toml
web_access_mode = "allow"
```

Allowed values:

- `"allow"`
- `"require_approval"`
- `"deny"`

Purpose:

- Governs `web.fetch`
- Governs `web.search`
- Governs imported remote MCP server connections

Default if omitted:

```toml
web_access_mode = "allow"
```

Validation behavior:

- Value must be a string.
- Matching is case-insensitive after trimming.
- Invalid values silently fall back to `"allow"`.

What it means:

- `"allow"`: web fetch/search is allowed; imported remote MCP servers are allowed
- `"require_approval"`: web fetch/search requires approval; imported remote MCP servers require approval
- `"deny"`: web fetch/search is denied; imported remote MCP servers are denied

What it does not affect:

- Native runtime TOML MCP servers are treated as operator-managed and are allowed regardless of `web_access_mode`.
- Imported project stdio MCP servers require approval regardless of `web_access_mode`.
- Shell commands classified as `network` are controlled by command-class policy, not `web_access_mode`.

Examples:

Open web posture:

```toml
web_access_mode = "allow"
deny_command_classes = ["destructive", "network", "secrets"]
```

Effect:

- built-in web tools can access the web freely
- `curl` is still denied because shell network commands are a separate policy path

Approval-gated web posture:

```toml
web_access_mode = "require_approval"
deny_command_classes = ["destructive", "secrets"]
safe_command_classes = ["safe_read", "safe_exec"]
```

Effect:

- web tool access pauses for approval per host
- imported remote MCP servers pause for approval per host
- shell network commands also pause for approval because `network` is not denied and not marked safe

Closed web posture:

```toml
web_access_mode = "deny"
deny_command_classes = ["destructive", "network", "secrets"]
```

Effect:

- web tool access is denied
- imported remote MCP servers are denied
- shell network commands are also denied

### `approval_mode`

Type:

```toml
approval_mode = "boundary"
```

Current runtime effect:

- None in the policy engine.
- The key is preserved and exposed in config views, but the runtime does not branch on it today.

What to use it for right now:

- documenting operator intent
- maintaining compatibility with existing example config
- surfacing a human-readable policy posture in config inspection or UI

What not to assume:

- changing `approval_mode` does not currently alter when approval is required
- changing it does not change boundary generation
- changing it does not disable run-scoped approval reuse

Recommendation:

- Keep `approval_mode = "boundary"` if you want your config to match the repository examples.
- Treat it as informational until enforcement logic is added.

### `sandbox_mode`

Type:

```toml
sandbox_mode = "governed"
```

Current runtime effect:

- None in the policy engine.
- The key is preserved and can appear in UI/config inspection, but it does not currently switch sandbox enforcement modes.

What actually governs sandbox behavior today:

- virtual paths must live under `/workspace`, `/tmp`, or `/.memory`
- workspace paths are rooted to the configured workspace directory
- sandbox path traversal outside the governed roots is rejected
- writes and command execution still pass through the runtime policy engine separately

Recommendation:

- Keep `sandbox_mode = "governed"` to match the shipped example and communicate intent.
- Do not rely on alternate string values to change behavior unless new code is added to enforce them.

## Arbitrary Custom Keys

Because the `[policy]` table is open-ended, you can add custom fields:

```toml
[policy]
approval_mode = "boundary"
sandbox_mode = "governed"
owner = "platform-team"
change_ticket = "SEC-142"
api_token = "super-secret-token"
```

Current behavior:

- the loader accepts these fields
- they are preserved in memory
- they appear in `config.get`
- keys whose path contains `secret`, `token`, `password`, or `api_key` are redacted in config inspection output

Important limitation:

- custom policy keys do not affect enforcement unless runtime code explicitly reads them

Redaction example:

- `policy.api_token` is shown as `***REDACTED***`
- `policy.owner` is shown as-is

## Non-Configurable Policy Behavior You Still Need To Understand

These behaviors are part of policy setup even though there is no TOML knob for them yet.

## File write policy

Allowed without approval:

- `/workspace/artifacts/**`
- `/tmp/**`
- `/.memory/**`, except identity memory paths

Require approval:

- other absolute virtual paths, for example `/workspace/src/main.py`

Denied:

- `/.memory/identity/**`

Approval boundary shape:

- writes are grouped by subtree
- `/workspace/src/main.py` becomes a boundary like `file.write:/workspace/src/**`
- another file under the same subtree, such as `/workspace/src/util.py`, reuses that same approval boundary

Practical consequence:

- approving one file write usually approves a broader subtree for the rest of the run

## Memory write policy

Allowed without approval:

- run-state memory writes

Require approval:

- project memory writes

Denied:

- identity memory writes
- project memory writes into namespaces starting with `identity.`

Approval boundary shape:

- project memory approval is namespaced
- example boundary: `memory.write:project:project.conventions`

## Skill installation policy

Allowed without approval:

- installs that do not overwrite, do not replace, and do not include scripts

Require approval:

- installs with scripts
- installs with overwrite behavior
- installs using `install_mode = "replace"`

Denied:

- install paths containing `..`

Approval boundary shape:

- boundary includes target scope, target role, skill id, and install mode

## MCP connection policy

Allowed without approval:

- native runtime TOML MCP servers

Require approval:

- imported project stdio MCP servers
- imported remote MCP servers when `web_access_mode = "require_approval"`

Denied:

- imported remote MCP servers when `web_access_mode = "deny"`

Allowed:

- imported remote MCP servers when `web_access_mode = "allow"`

Approval boundary shape:

- stdio boundary: per server name
- remote boundary: per transport and host

## Policy Recipes

## 1. Most restrictive practical setup

This is the closest thing to a lockdown mode while still letting the agent do local read/compute work.

```toml
[policy]
approval_mode = "boundary"
sandbox_mode = "governed"
safe_command_classes = ["safe_read"]
deny_command_classes = ["destructive", "network", "secrets"]
web_access_mode = "deny"
```

Behavior:

- read-only shell inspection is allowed
- ordinary execution requires approval
- destructive shell commands are denied
- shell network commands are denied
- built-in web tools are denied
- imported remote MCP servers are denied
- project stdio MCP servers still require approval if used

Best for:

- highly controlled audits
- environments where the agent should mostly inspect and propose

## 2. Strict but usable setup

```toml
[policy]
approval_mode = "boundary"
sandbox_mode = "governed"
safe_command_classes = ["safe_read", "safe_exec"]
deny_command_classes = ["destructive", "network", "secrets"]
web_access_mode = "require_approval"
```

Behavior:

- normal local execution is allowed
- destructive shell commands are denied
- shell network commands are denied
- web tool usage pauses for approval
- imported remote MCP servers pause for approval

Best for:

- day-to-day engineering work with explicit web review

## 3. Approval-heavy setup

```toml
[policy]
approval_mode = "boundary"
sandbox_mode = "governed"
safe_command_classes = ["safe_read", "safe_exec"]
deny_command_classes = ["destructive", "secrets"]
web_access_mode = "require_approval"
```

Behavior:

- most local commands are allowed
- shell network commands require approval instead of being denied
- destructive commands are denied
- web tool usage requires approval

Best for:

- teams that want a human in the loop for all outbound access but not for routine local work

## 4. Default example posture

This matches the repository example closely.

```toml
[policy]
approval_mode = "boundary"
sandbox_mode = "governed"
safe_command_classes = ["safe_read", "safe_exec"]
deny_command_classes = ["network", "destructive", "secrets"]
web_access_mode = "allow"
```

Behavior:

- routine local commands are allowed
- shell network commands are denied
- destructive commands are denied
- built-in web access is allowed
- imported remote MCP servers are allowed

Best for:

- local development where built-in web tools are acceptable but shell networking is intentionally blocked

## 5. Most lax setup

This removes nearly all policy friction that is currently configurable.

```toml
[policy]
approval_mode = "boundary"
sandbox_mode = "governed"
safe_command_classes = ["safe_read", "safe_exec", "network", "destructive", "secrets"]
deny_command_classes = []
web_access_mode = "allow"
```

Behavior:

- almost all command classes are allowed immediately
- web tool access is allowed
- imported remote MCP servers are allowed
- hard-coded denials still remain, such as identity memory mutation and skill-install path traversal

Best for:

- isolated, trusted environments where operator speed matters more than runtime friction

## Common Misunderstandings

`approval_mode = "boundary"` does not currently enable a special mode.
The runtime already uses boundary-based approvals regardless of that setting.

`sandbox_mode = "governed"` does not currently toggle sandbox logic.
Sandbox path rules are enforced independently of this string.

`web_access_mode` does not control shell commands like `curl`.
Those are command-execution policy decisions based on command classification.

Removing a class from `deny_command_classes` does not automatically allow it.
If the class is also absent from `safe_command_classes`, it requires approval.

Adding arbitrary keys to `[policy]` does not create new enforcement.
It only stores additional metadata unless code is added to interpret it.

## Recommended Baselines

If you want a safe default with minimal surprises:

```toml
[policy]
approval_mode = "boundary"
sandbox_mode = "governed"
safe_command_classes = ["safe_read", "safe_exec"]
deny_command_classes = ["network", "destructive", "secrets"]
web_access_mode = "require_approval"
```

If you want the repository example behavior exactly:

```toml
[policy]
approval_mode = "boundary"
sandbox_mode = "governed"
safe_command_classes = ["safe_read", "safe_exec"]
deny_command_classes = ["network", "destructive", "secrets"]
web_access_mode = "allow"
```

If you want a highly conservative posture:

```toml
[policy]
approval_mode = "boundary"
sandbox_mode = "governed"
safe_command_classes = ["safe_read"]
deny_command_classes = ["network", "destructive", "secrets"]
web_access_mode = "deny"
```

## Bottom Line

If you are tuning policy today, focus on these levers:

- `safe_command_classes`
- `deny_command_classes`
- `web_access_mode`

Keep these for clarity and future compatibility, but do not expect behavior changes from them yet:

- `approval_mode`
- `sandbox_mode`

And if you add extra keys under `[policy]`, assume they are documentation and metadata unless you have also added runtime code to enforce them.
