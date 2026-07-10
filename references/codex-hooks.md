
# Codex Hooks Documentation (from developers.openai.com/codex/hooks)

Fetched on 2026-07-09. Source: https://developers.openai.com/codex/hooks

This document describes Codex's plugin hook system — lifecycle events that can trigger external scripts at various points during an agent session.

## Where Codex looks for hooks

Codex discovers hooks next to active config layers in either of these forms:

`hooks.json`
inline `[hooks]` tables inside `config.toml`

Installed plugins can also bundle lifecycle config through their plugin
manifest or a default `hooks/hooks.json` file. See Build
plugins for the
plugin packaging rules.
In practice, the four most useful locations are:

`~/.codex/hooks.json`
`~/.codex/config.toml`
`<repo>/.codex/hooks.json`
`<repo>/.codex/config.toml`

If more than one hook source exists, Codex loads all matching hooks.
Higher-precedence config layers don’t replace lower-precedence hooks.
If a single layer contains both `hooks.json` and inline `[hooks]`, Codex
merges them and warns at startup. Prefer one representation per layer.
Codex can also discover hooks bundled with enabled plugins. Plugin-bundled
hooks load alongside other hook sources and use the same trust-review flow as
other non-managed hooks.
Project-local hooks load only when the project `.codex/` layer is trusted. In
untrusted projects, Codex still loads user and system hooks from their own
active config layers.
Review and trust hooks
Codex lists configured hooks before deciding which ones can run. Before a
non-managed command hook can run, Codex requires you to review and trust the
exact hook definition. Codex records trust against the hook’s current hash, so
new or changed hooks are marked for review and skipped until trusted.
Use `/hooks` in the CLI to inspect hook sources, review new or changed hooks,
trust hooks, or disable individual non-managed hooks. If hooks need review at
startup, Codex prints a warning that tells you to open `/hooks`.
Managed hooks from system, MDM, cloud, or `requirements.toml` sources are marked
as managed, trusted by policy, and can’t be disabled from the user hook browser.
For one-off automation that already vets hook sources outside Codex, pass
`--dangerously-bypass-hook-trust` to run enabled hooks without requiring
persisted hook trust for that invocation.
Config shape
Hooks are organized in three levels:

A hook event such as `PreToolUse`, `PostToolUse`, `PreCompact`,
`SubagentStart`, or `Stop`
A matcher group that decides when that event matches
One or more hook handlers that run when the matcher group matches

```
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.codex/hooks/session_start.py",
            "statusMessage": "Loading session notes"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/pre_tool_use_policy.py\"",
            "statusMessage": "Checking Bash command"
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/permission_request.py\"",
            "statusMessage": "Checking approval request"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/post_tool_use_review.py\"",
            "statusMessage": "Reviewing Bash output"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/user_prompt_submit_data_flywheel.py\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/stop_continue.py\"",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

Notes:

`timeout` is in seconds.
If `timeout` is omitted, Codex uses `600` seconds.
`statusMessage` is optional.
`commandWindows` is an optional Windows-only command override. In TOML, use
`command_windows` or `commandWindows`.
`async` is parsed, but async command hooks aren’t supported yet. Codex skips
handlers with `async: true`.
Only `type: "command"` handlers run today. `prompt` and `agent` handlers are
parsed but skipped.
Commands run with the session `cwd` as their working directory.
For repo-local hooks, prefer resolving from the git root instead of using a
relative path such as `.codex/hooks/...`. Codex may be started from a
subdirectory, and a git-root-based path keeps the hook location stable.

Equivalent inline TOML in `config.toml`:

```
[[hooks.PreToolUse]]
matcher = "^Bash$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = '/usr/bin/python3 "$(git rev-parse --show-toplevel)/.codex/hooks/pre_tool_use_policy.py"'
timeout = 30
statusMessage = "Checking Bash command"

[[hooks.PostToolUse]]
matcher = "^Bash$"

[[hooks.PostToolUse.hooks]]
type = "command"
command = '/usr/bin/python3 "$(git rev-parse --show-toplevel)/.codex/hooks/post_tool_use_review.py"'
timeout = 30
statusMessage = "Reviewing Bash output"
```

Managed hooks from `requirements.toml`
Enterprise-managed requirements can also define hooks inline under `[hooks]`.
This is useful when admins want to enforce the hook configuration while
delivering the actual scripts through MDM or another device-management system.
To enforce managed hooks even for users who disabled hooks locally, pin
`[features].hooks = true` in `requirements.toml` alongside `[hooks]`. To ignore
user, project, session, and plugin hooks while still allowing administrator
managed hooks, set `allow_managed_hooks_only = true`.

```
allow_managed_hooks_only = true

[features]
hooks = true

[hooks]
managed_dir = "/enterprise/hooks"
windows_managed_dir = 'C:\enterprise\hooks'

[[hooks.PreToolUse]]
matcher = "^Bash$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "python3 /enterprise/hooks/pre_tool_use_policy.py"
command_windows = 'py -3 C:\enterprise\hooks\pre_tool_use_policy.py'
timeout = 30
statusMessage = "Checking managed Bash command"
```

Notes for managed hooks:

`managed_dir` is used on macOS and Linux.
`windows_managed_dir` is used on Windows.
Codex doesn’t distribute the scripts in `managed_dir`; your enterprise
tooling must install and update them separately.
Managed hook commands should use absolute script paths under the configured
managed directory.
`allow_managed_hooks_only = true` skips hooks from user, project, session, and
plugin sources, but still loads managed hooks from `requirements.toml` and
other managed config layers.

Plugin-bundled hooks
When a plugin is enabled, Codex can load lifecycle hooks from that plugin
alongside user, project, and managed hooks.
By default, Codex looks for `hooks/hooks.json` inside the plugin root. A plugin
manifest can override that default with a `hooks` entry in
`.codex-plugin/plugin.json`. The manifest entry can be a `./`-prefixed path, an
array of `./`-prefixed paths, an inline hooks object, or an array of inline
hooks objects.

```
{
  "name": "repo-policy",
  "hooks": "./hooks/hooks.json"
}
```

Manifest hook paths are resolved relative to the plugin root and must stay
inside that root. If a manifest defines `hooks`, Codex uses those manifest
entries instead of the default `hooks/hooks.json`.
Plugin hook commands receive these environment variables:

`PLUGIN_ROOT` is a Codex-specific extension that points to the installed
plugin root.
`PLUGIN_DATA` is a Codex-specific extension that points to the plugin’s
writable data directory.
Codex also sets `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` for
compatibility with existing plugin hooks.

Plugin hooks use the same event schema as other hooks. Installing or enabling a
plugin doesn’t automatically trust its hooks; Codex skips plugin-bundled hooks
until you review and trust the current hook definition.
Matcher patterns
The `matcher` field is a regex string that filters when hooks fire. Use `"*"`,
`""`, or omit `matcher` entirely to match every occurrence of a supported
event.
Only some current Codex events honor `matcher`:

EventWhat `matcher` filtersNotes`PermissionRequest`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`PostToolUse`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`PostCompact`compaction triggerValues are `manual` or `auto``PreCompact`compaction triggerValues are `manual` or `auto``PreToolUse`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`SessionStart`start sourceValues are `startup`, `resume`, `clear`, and `compact``SubagentStart`subagent typeValues depend on the subagent that starts`SubagentStop`subagent typeValues depend on the subagent that stops`UserPromptSubmit`not supportedAny configured `matcher` is ignored for this event`Stop`not supportedAny configured `matcher` is ignored for this event
*For `apply_patch`, `matcher` values can also use `Edit` or `Write`.
Examples:

`Bash`
`^apply_patch$`
`Edit|Write`
`mcp__filesystem__read_file`
`mcp__filesystem__.*`
`startup|resume|clear|compact`
`manual|auto`

Common input fields
Every command hook receives one JSON object on `stdin`.
These are the shared fields you will usually use:

FieldTypeMeaning`session_id``string`Current Codex session id. Subagent hooks use the parent session id.`transcript_path``string | null`Path to the session transcript file, if any`cwd``string`Working directory for the session`hook_event_name``string`Current hook event name`model``string`Codex-specific extension. Active model slug
Turn-scoped hooks list `turn_id` as a Codex-specific extension in their
event-specific tables.
`SessionStart`, `PreToolUse`, `PermissionRequest`, `PostToolUse`,
`UserPromptSubmit`, `SubagentStart`, `SubagentStop`, and `Stop` also include
`permission_mode`, which describes the current permission mode as `default`,
`acceptEdits`, `plan`, `dontAsk`, or `bypassPermissions`.
`transcript_path` points to a conversation transcript for convenience, but the
transcript format is not a stable interface for hooks and may change over time.
If you need the full wire format, see Schemas.
Common output fields
`SessionStart`, `PreCompact`, `PostCompact`, `UserPromptSubmit`,
`SubagentStop`, and `Stop` support these shared JSON fields. `SubagentStart`
accepts the same shape for `systemMessage` and hook-specific context, but
`continue: false` doesn’t stop the subagent:

```
{
  "continue": true,
  "stopReason": "optional",
  "systemMessage": "optional",
  "suppressOutput": false
}
```

FieldEffect`continue`If `false`, marks that hook run as stopped`stopReason`Recorded as the reason for stopping`systemMessage`Surfaced as a warning in the UI or event stream`suppressOutput`Parsed today but not yet implemented
Exit `0` with no output is treated as success and Codex continues.
`PreToolUse` and `PermissionRequest` support `systemMessage`, but `continue`,
`stopReason`, and `suppressOutput` aren’t currently supported for those events.
If a `PreToolUse` hook returns one of those unsupported fields, Codex marks
that hook run as failed, reports the error, and continues the tool call.
`PostToolUse` supports `systemMessage`, `continue: false`, and `stopReason`.
`suppressOutput` is parsed but not currently supported for that event.
Hooks
SessionStart
`matcher` is applied to `source` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`source``string`How the session started: `startup`, `resume`, `clear`, or `compact`
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and this
hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Load the workspace conventions before editing."
  }
}
```

That `additionalContext` text is added as extra developer context.
SubagentStart
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`permission_mode``string`Current permission mode
Plain text on `stdout` is added as extra developer context for the subagent.
JSON on `stdout` supports `systemMessage` and this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "Review the repository test conventions first."
  }
}
```

That `additionalContext` text is added as extra developer context for the
subagent. `continue: false` is parsed for compatibility, but it doesn’t stop the
subagent from starting.
PreToolUse
`PreToolUse` can intercept Bash, file edits performed through `apply_patch`,
and MCP tool calls. It’s still a guardrail rather than a complete enforcement
boundary because Codex can often perform equivalent work through another
supported tool path.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage`. To deny a supported tool call, return
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by hook."
  }
}
```

Codex also accepts this older block shape:

```
{
  "decision": "block",
  "reason": "Destructive command blocked by hook."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
To add model-visible context without blocking, return
`hookSpecificOutput.additionalContext`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "The pending command touches generated files."
  }
}
```

To rewrite a supported tool call without blocking, return
`permissionDecision: "allow"` with `updatedInput`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {
      "command": "echo rewritten"
    }
  }
}
```

For Bash commands and `apply_patch`, `updatedInput` must include a string
`command` field. For MCP tools, `updatedInput` is the replacement arguments
object. Return `updatedInput` only with `permissionDecision: "allow"`; other
`updatedInput` shapes are reported as errors.
`permissionDecision: "ask"`, legacy `decision: "approve"`, `continue: false`,
`stopReason`, and `suppressOutput` are parsed but not supported yet. Codex marks
the hook run as failed, reports the error, and continues the tool call.
PermissionRequest
`PermissionRequest` runs when Codex is about to ask for approval, such as a
shell escalation or managed-network approval. It can allow the request, deny
the request, or decline to decide and let the normal approval prompt continue.
It doesn’t run for commands that don’t need approval.
`matcher` is applied to `tool_name` and matcher aliases. Current canonical
values include `Bash`, `apply_patch`, and MCP tool names such as
`mcp__server__tool`; `apply_patch` also matches `Edit` and `Write`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all the args.`tool_input.description``string | null`Human-readable approval reason, when Codex has one
Plain text on `stdout` is ignored.
Some tool inputs may include a human-readable description, but don’t rely on a
`tool_input.description` field for every tool.
To approve the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow"
    }
  }
}
```

To deny the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Blocked by repository policy."
    }
  }
}
```

If multiple matching hooks return decisions, any `deny` wins. Otherwise, an
`allow` lets the request proceed without surfacing the approval prompt. If no
matching hook decides, Codex uses the normal approval flow.
Don’t return `updatedInput`, `updatedPermissions`, or `interrupt` for
`PermissionRequest`; those fields are reserved for future behavior and fail
closed today.
PostToolUse
`PostToolUse` runs after supported tools produce output, including Bash,
`apply_patch`, and MCP tool calls. For Bash, it also runs after commands that
exit with a non-zero status. It can’t undo side effects from the tool that
already ran.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.`tool_response``JSON value`Tool-specific output. For MCP tools, this is the MCP call result.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage` and this hook-specific shape:

```
{
  "decision": "block",
  "reason": "The Bash output needs review before continuing.",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "The command updated generated files."
  }
}
```

That `additionalContext` text is added as extra developer context.
For this event, `decision: "block"` doesn’t undo the completed Bash command.
Instead, Codex records the feedback, replaces the tool result with that
feedback, and continues the model from the hook-provided message.
You can also use exit code `2` and write the feedback reason to `stderr`.
To stop normal processing of the original tool result after the command has
already run, return `continue: false`. Codex will replace the tool result with
your feedback or stop text and continue from there.
`updatedMCPToolOutput` and `suppressOutput` are parsed but not supported yet.
Codex marks the hook run as failed, reports the error, and continues normal
processing of the tool result.
PreCompact
`PreCompact` runs before Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PreCompact` hook returns `continue: false`, Codex stops before
compacting.
PostCompact
`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();
• hooks.json
• inline [hooks] tables inside config.toml
• ~/.codex/hooks.json
• ~/.codex/config.toml
• <repo>/.codex/hooks.json
• <repo>/.codex/config.toml
• A hook event such as PreToolUse, PostToolUse, PreCompact,
SubagentStart, or Stop
• A matcher group that decides when that event matches
• One or more hook handlers that run when the matcher group matches
• timeout is in seconds.
• If timeout is omitted, Codex uses 600 seconds.
• statusMessage is optional.
• commandWindows is an optional Windows-only command override. In TOML, use
command_windows or commandWindows.
• async is parsed, but async command hooks aren’t supported yet. Codex skips
handlers with async: true.
• Only type: "command" handlers run today. prompt and agent handlers are
parsed but skipped.
• Commands run with the session cwd as their working directory.
• For repo-local hooks, prefer resolving from the git root instead of using a
relative path such as .codex/hooks/.... Codex may be started from a
subdirectory, and a git-root-based path keeps the hook location stable.
• managed_dir is used on macOS and Linux.
• windows_managed_dir is used on Windows.
• Codex doesn’t distribute the scripts in managed_dir; your enterprise
tooling must install and update them separately.
• Managed hook commands should use absolute script paths under the configured
managed directory.
• allow_managed_hooks_only = true skips hooks from user, project, session, and
plugin sources, but still loads managed hooks from requirements.toml and
other managed config layers.
• PLUGIN_ROOT is a Codex-specific extension that points to the installed
plugin root.
• PLUGIN_DATA is a Codex-specific extension that points to the plugin’s
writable data directory.
• Codex also sets CLAUDE_PLUGIN_ROOT and CLAUDE_PLUGIN_DATA for
compatibility with existing plugin hooks.
• Bash
• ^apply_patch$
• Edit|Write
• mcp__filesystem__read_file
• mcp__filesystem__.*
• startup|resume|clear|compact
• manual|auto

## Review and trust hooks

Codex lists configured hooks before deciding which ones can run. Before a
non-managed command hook can run, Codex requires you to review and trust the
exact hook definition. Codex records trust against the hook’s current hash, so
new or changed hooks are marked for review and skipped until trusted.
Use `/hooks` in the CLI to inspect hook sources, review new or changed hooks,
trust hooks, or disable individual non-managed hooks. If hooks need review at
startup, Codex prints a warning that tells you to open `/hooks`.
Managed hooks from system, MDM, cloud, or `requirements.toml` sources are marked
as managed, trusted by policy, and can’t be disabled from the user hook browser.
For one-off automation that already vets hook sources outside Codex, pass
`--dangerously-bypass-hook-trust` to run enabled hooks without requiring
persisted hook trust for that invocation.
Config shape
Hooks are organized in three levels:

A hook event such as `PreToolUse`, `PostToolUse`, `PreCompact`,
`SubagentStart`, or `Stop`
A matcher group that decides when that event matches
One or more hook handlers that run when the matcher group matches

```
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.codex/hooks/session_start.py",
            "statusMessage": "Loading session notes"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/pre_tool_use_policy.py\"",
            "statusMessage": "Checking Bash command"
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/permission_request.py\"",
            "statusMessage": "Checking approval request"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/post_tool_use_review.py\"",
            "statusMessage": "Reviewing Bash output"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/user_prompt_submit_data_flywheel.py\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/stop_continue.py\"",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

Notes:

`timeout` is in seconds.
If `timeout` is omitted, Codex uses `600` seconds.
`statusMessage` is optional.
`commandWindows` is an optional Windows-only command override. In TOML, use
`command_windows` or `commandWindows`.
`async` is parsed, but async command hooks aren’t supported yet. Codex skips
handlers with `async: true`.
Only `type: "command"` handlers run today. `prompt` and `agent` handlers are
parsed but skipped.
Commands run with the session `cwd` as their working directory.
For repo-local hooks, prefer resolving from the git root instead of using a
relative path such as `.codex/hooks/...`. Codex may be started from a
subdirectory, and a git-root-based path keeps the hook location stable.

Equivalent inline TOML in `config.toml`:

```
[[hooks.PreToolUse]]
matcher = "^Bash$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = '/usr/bin/python3 "$(git rev-parse --show-toplevel)/.codex/hooks/pre_tool_use_policy.py"'
timeout = 30
statusMessage = "Checking Bash command"

[[hooks.PostToolUse]]
matcher = "^Bash$"

[[hooks.PostToolUse.hooks]]
type = "command"
command = '/usr/bin/python3 "$(git rev-parse --show-toplevel)/.codex/hooks/post_tool_use_review.py"'
timeout = 30
statusMessage = "Reviewing Bash output"
```

Managed hooks from `requirements.toml`
Enterprise-managed requirements can also define hooks inline under `[hooks]`.
This is useful when admins want to enforce the hook configuration while
delivering the actual scripts through MDM or another device-management system.
To enforce managed hooks even for users who disabled hooks locally, pin
`[features].hooks = true` in `requirements.toml` alongside `[hooks]`. To ignore
user, project, session, and plugin hooks while still allowing administrator
managed hooks, set `allow_managed_hooks_only = true`.

```
allow_managed_hooks_only = true

[features]
hooks = true

[hooks]
managed_dir = "/enterprise/hooks"
windows_managed_dir = 'C:\enterprise\hooks'

[[hooks.PreToolUse]]
matcher = "^Bash$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "python3 /enterprise/hooks/pre_tool_use_policy.py"
command_windows = 'py -3 C:\enterprise\hooks\pre_tool_use_policy.py'
timeout = 30
statusMessage = "Checking managed Bash command"
```

Notes for managed hooks:

`managed_dir` is used on macOS and Linux.
`windows_managed_dir` is used on Windows.
Codex doesn’t distribute the scripts in `managed_dir`; your enterprise
tooling must install and update them separately.
Managed hook commands should use absolute script paths under the configured
managed directory.
`allow_managed_hooks_only = true` skips hooks from user, project, session, and
plugin sources, but still loads managed hooks from `requirements.toml` and
other managed config layers.

Plugin-bundled hooks
When a plugin is enabled, Codex can load lifecycle hooks from that plugin
alongside user, project, and managed hooks.
By default, Codex looks for `hooks/hooks.json` inside the plugin root. A plugin
manifest can override that default with a `hooks` entry in
`.codex-plugin/plugin.json`. The manifest entry can be a `./`-prefixed path, an
array of `./`-prefixed paths, an inline hooks object, or an array of inline
hooks objects.

```
{
  "name": "repo-policy",
  "hooks": "./hooks/hooks.json"
}
```

Manifest hook paths are resolved relative to the plugin root and must stay
inside that root. If a manifest defines `hooks`, Codex uses those manifest
entries instead of the default `hooks/hooks.json`.
Plugin hook commands receive these environment variables:

`PLUGIN_ROOT` is a Codex-specific extension that points to the installed
plugin root.
`PLUGIN_DATA` is a Codex-specific extension that points to the plugin’s
writable data directory.
Codex also sets `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` for
compatibility with existing plugin hooks.

Plugin hooks use the same event schema as other hooks. Installing or enabling a
plugin doesn’t automatically trust its hooks; Codex skips plugin-bundled hooks
until you review and trust the current hook definition.
Matcher patterns
The `matcher` field is a regex string that filters when hooks fire. Use `"*"`,
`""`, or omit `matcher` entirely to match every occurrence of a supported
event.
Only some current Codex events honor `matcher`:

EventWhat `matcher` filtersNotes`PermissionRequest`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`PostToolUse`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`PostCompact`compaction triggerValues are `manual` or `auto``PreCompact`compaction triggerValues are `manual` or `auto``PreToolUse`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`SessionStart`start sourceValues are `startup`, `resume`, `clear`, and `compact``SubagentStart`subagent typeValues depend on the subagent that starts`SubagentStop`subagent typeValues depend on the subagent that stops`UserPromptSubmit`not supportedAny configured `matcher` is ignored for this event`Stop`not supportedAny configured `matcher` is ignored for this event
*For `apply_patch`, `matcher` values can also use `Edit` or `Write`.
Examples:

`Bash`
`^apply_patch$`
`Edit|Write`
`mcp__filesystem__read_file`
`mcp__filesystem__.*`
`startup|resume|clear|compact`
`manual|auto`

Common input fields
Every command hook receives one JSON object on `stdin`.
These are the shared fields you will usually use:

FieldTypeMeaning`session_id``string`Current Codex session id. Subagent hooks use the parent session id.`transcript_path``string | null`Path to the session transcript file, if any`cwd``string`Working directory for the session`hook_event_name``string`Current hook event name`model``string`Codex-specific extension. Active model slug
Turn-scoped hooks list `turn_id` as a Codex-specific extension in their
event-specific tables.
`SessionStart`, `PreToolUse`, `PermissionRequest`, `PostToolUse`,
`UserPromptSubmit`, `SubagentStart`, `SubagentStop`, and `Stop` also include
`permission_mode`, which describes the current permission mode as `default`,
`acceptEdits`, `plan`, `dontAsk`, or `bypassPermissions`.
`transcript_path` points to a conversation transcript for convenience, but the
transcript format is not a stable interface for hooks and may change over time.
If you need the full wire format, see Schemas.
Common output fields
`SessionStart`, `PreCompact`, `PostCompact`, `UserPromptSubmit`,
`SubagentStop`, and `Stop` support these shared JSON fields. `SubagentStart`
accepts the same shape for `systemMessage` and hook-specific context, but
`continue: false` doesn’t stop the subagent:

```
{
  "continue": true,
  "stopReason": "optional",
  "systemMessage": "optional",
  "suppressOutput": false
}
```

FieldEffect`continue`If `false`, marks that hook run as stopped`stopReason`Recorded as the reason for stopping`systemMessage`Surfaced as a warning in the UI or event stream`suppressOutput`Parsed today but not yet implemented
Exit `0` with no output is treated as success and Codex continues.
`PreToolUse` and `PermissionRequest` support `systemMessage`, but `continue`,
`stopReason`, and `suppressOutput` aren’t currently supported for those events.
If a `PreToolUse` hook returns one of those unsupported fields, Codex marks
that hook run as failed, reports the error, and continues the tool call.
`PostToolUse` supports `systemMessage`, `continue: false`, and `stopReason`.
`suppressOutput` is parsed but not currently supported for that event.
Hooks
SessionStart
`matcher` is applied to `source` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`source``string`How the session started: `startup`, `resume`, `clear`, or `compact`
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and this
hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Load the workspace conventions before editing."
  }
}
```

That `additionalContext` text is added as extra developer context.
SubagentStart
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`permission_mode``string`Current permission mode
Plain text on `stdout` is added as extra developer context for the subagent.
JSON on `stdout` supports `systemMessage` and this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "Review the repository test conventions first."
  }
}
```

That `additionalContext` text is added as extra developer context for the
subagent. `continue: false` is parsed for compatibility, but it doesn’t stop the
subagent from starting.
PreToolUse
`PreToolUse` can intercept Bash, file edits performed through `apply_patch`,
and MCP tool calls. It’s still a guardrail rather than a complete enforcement
boundary because Codex can often perform equivalent work through another
supported tool path.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage`. To deny a supported tool call, return
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by hook."
  }
}
```

Codex also accepts this older block shape:

```
{
  "decision": "block",
  "reason": "Destructive command blocked by hook."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
To add model-visible context without blocking, return
`hookSpecificOutput.additionalContext`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "The pending command touches generated files."
  }
}
```

To rewrite a supported tool call without blocking, return
`permissionDecision: "allow"` with `updatedInput`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {
      "command": "echo rewritten"
    }
  }
}
```

For Bash commands and `apply_patch`, `updatedInput` must include a string
`command` field. For MCP tools, `updatedInput` is the replacement arguments
object. Return `updatedInput` only with `permissionDecision: "allow"`; other
`updatedInput` shapes are reported as errors.
`permissionDecision: "ask"`, legacy `decision: "approve"`, `continue: false`,
`stopReason`, and `suppressOutput` are parsed but not supported yet. Codex marks
the hook run as failed, reports the error, and continues the tool call.
PermissionRequest
`PermissionRequest` runs when Codex is about to ask for approval, such as a
shell escalation or managed-network approval. It can allow the request, deny
the request, or decline to decide and let the normal approval prompt continue.
It doesn’t run for commands that don’t need approval.
`matcher` is applied to `tool_name` and matcher aliases. Current canonical
values include `Bash`, `apply_patch`, and MCP tool names such as
`mcp__server__tool`; `apply_patch` also matches `Edit` and `Write`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all the args.`tool_input.description``string | null`Human-readable approval reason, when Codex has one
Plain text on `stdout` is ignored.
Some tool inputs may include a human-readable description, but don’t rely on a
`tool_input.description` field for every tool.
To approve the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow"
    }
  }
}
```

To deny the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Blocked by repository policy."
    }
  }
}
```

If multiple matching hooks return decisions, any `deny` wins. Otherwise, an
`allow` lets the request proceed without surfacing the approval prompt. If no
matching hook decides, Codex uses the normal approval flow.
Don’t return `updatedInput`, `updatedPermissions`, or `interrupt` for
`PermissionRequest`; those fields are reserved for future behavior and fail
closed today.
PostToolUse
`PostToolUse` runs after supported tools produce output, including Bash,
`apply_patch`, and MCP tool calls. For Bash, it also runs after commands that
exit with a non-zero status. It can’t undo side effects from the tool that
already ran.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.`tool_response``JSON value`Tool-specific output. For MCP tools, this is the MCP call result.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage` and this hook-specific shape:

```
{
  "decision": "block",
  "reason": "The Bash output needs review before continuing.",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "The command updated generated files."
  }
}
```

That `additionalContext` text is added as extra developer context.
For this event, `decision: "block"` doesn’t undo the completed Bash command.
Instead, Codex records the feedback, replaces the tool result with that
feedback, and continues the model from the hook-provided message.
You can also use exit code `2` and write the feedback reason to `stderr`.
To stop normal processing of the original tool result after the command has
already run, return `continue: false`. Codex will replace the tool result with
your feedback or stop text and continue from there.
`updatedMCPToolOutput` and `suppressOutput` are parsed but not supported yet.
Codex marks the hook run as failed, reports the error, and continues normal
processing of the tool result.
PreCompact
`PreCompact` runs before Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PreCompact` hook returns `continue: false`, Codex stops before
compacting.
PostCompact
`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

## Config shape

Hooks are organized in three levels:

A hook event such as `PreToolUse`, `PostToolUse`, `PreCompact`,
`SubagentStart`, or `Stop`
A matcher group that decides when that event matches
One or more hook handlers that run when the matcher group matches

```
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.codex/hooks/session_start.py",
            "statusMessage": "Loading session notes"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/pre_tool_use_policy.py\"",
            "statusMessage": "Checking Bash command"
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/permission_request.py\"",
            "statusMessage": "Checking approval request"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/post_tool_use_review.py\"",
            "statusMessage": "Reviewing Bash output"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/user_prompt_submit_data_flywheel.py\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/stop_continue.py\"",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

Notes:

`timeout` is in seconds.
If `timeout` is omitted, Codex uses `600` seconds.
`statusMessage` is optional.
`commandWindows` is an optional Windows-only command override. In TOML, use
`command_windows` or `commandWindows`.
`async` is parsed, but async command hooks aren’t supported yet. Codex skips
handlers with `async: true`.
Only `type: "command"` handlers run today. `prompt` and `agent` handlers are
parsed but skipped.
Commands run with the session `cwd` as their working directory.
For repo-local hooks, prefer resolving from the git root instead of using a
relative path such as `.codex/hooks/...`. Codex may be started from a
subdirectory, and a git-root-based path keeps the hook location stable.

Equivalent inline TOML in `config.toml`:

```
[[hooks.PreToolUse]]
matcher = "^Bash$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = '/usr/bin/python3 "$(git rev-parse --show-toplevel)/.codex/hooks/pre_tool_use_policy.py"'
timeout = 30
statusMessage = "Checking Bash command"

[[hooks.PostToolUse]]
matcher = "^Bash$"

[[hooks.PostToolUse.hooks]]
type = "command"
command = '/usr/bin/python3 "$(git rev-parse --show-toplevel)/.codex/hooks/post_tool_use_review.py"'
timeout = 30
statusMessage = "Reviewing Bash output"
```

Managed hooks from `requirements.toml`
Enterprise-managed requirements can also define hooks inline under `[hooks]`.
This is useful when admins want to enforce the hook configuration while
delivering the actual scripts through MDM or another device-management system.
To enforce managed hooks even for users who disabled hooks locally, pin
`[features].hooks = true` in `requirements.toml` alongside `[hooks]`. To ignore
user, project, session, and plugin hooks while still allowing administrator
managed hooks, set `allow_managed_hooks_only = true`.

```
allow_managed_hooks_only = true

[features]
hooks = true

[hooks]
managed_dir = "/enterprise/hooks"
windows_managed_dir = 'C:\enterprise\hooks'

[[hooks.PreToolUse]]
matcher = "^Bash$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "python3 /enterprise/hooks/pre_tool_use_policy.py"
command_windows = 'py -3 C:\enterprise\hooks\pre_tool_use_policy.py'
timeout = 30
statusMessage = "Checking managed Bash command"
```

Notes for managed hooks:

`managed_dir` is used on macOS and Linux.
`windows_managed_dir` is used on Windows.
Codex doesn’t distribute the scripts in `managed_dir`; your enterprise
tooling must install and update them separately.
Managed hook commands should use absolute script paths under the configured
managed directory.
`allow_managed_hooks_only = true` skips hooks from user, project, session, and
plugin sources, but still loads managed hooks from `requirements.toml` and
other managed config layers.

Plugin-bundled hooks
When a plugin is enabled, Codex can load lifecycle hooks from that plugin
alongside user, project, and managed hooks.
By default, Codex looks for `hooks/hooks.json` inside the plugin root. A plugin
manifest can override that default with a `hooks` entry in
`.codex-plugin/plugin.json`. The manifest entry can be a `./`-prefixed path, an
array of `./`-prefixed paths, an inline hooks object, or an array of inline
hooks objects.

```
{
  "name": "repo-policy",
  "hooks": "./hooks/hooks.json"
}
```

Manifest hook paths are resolved relative to the plugin root and must stay
inside that root. If a manifest defines `hooks`, Codex uses those manifest
entries instead of the default `hooks/hooks.json`.
Plugin hook commands receive these environment variables:

`PLUGIN_ROOT` is a Codex-specific extension that points to the installed
plugin root.
`PLUGIN_DATA` is a Codex-specific extension that points to the plugin’s
writable data directory.
Codex also sets `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` for
compatibility with existing plugin hooks.

Plugin hooks use the same event schema as other hooks. Installing or enabling a
plugin doesn’t automatically trust its hooks; Codex skips plugin-bundled hooks
until you review and trust the current hook definition.
Matcher patterns
The `matcher` field is a regex string that filters when hooks fire. Use `"*"`,
`""`, or omit `matcher` entirely to match every occurrence of a supported
event.
Only some current Codex events honor `matcher`:

EventWhat `matcher` filtersNotes`PermissionRequest`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`PostToolUse`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`PostCompact`compaction triggerValues are `manual` or `auto``PreCompact`compaction triggerValues are `manual` or `auto``PreToolUse`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`SessionStart`start sourceValues are `startup`, `resume`, `clear`, and `compact``SubagentStart`subagent typeValues depend on the subagent that starts`SubagentStop`subagent typeValues depend on the subagent that stops`UserPromptSubmit`not supportedAny configured `matcher` is ignored for this event`Stop`not supportedAny configured `matcher` is ignored for this event
*For `apply_patch`, `matcher` values can also use `Edit` or `Write`.
Examples:

`Bash`
`^apply_patch$`
`Edit|Write`
`mcp__filesystem__read_file`
`mcp__filesystem__.*`
`startup|resume|clear|compact`
`manual|auto`

Common input fields
Every command hook receives one JSON object on `stdin`.
These are the shared fields you will usually use:

FieldTypeMeaning`session_id``string`Current Codex session id. Subagent hooks use the parent session id.`transcript_path``string | null`Path to the session transcript file, if any`cwd``string`Working directory for the session`hook_event_name``string`Current hook event name`model``string`Codex-specific extension. Active model slug
Turn-scoped hooks list `turn_id` as a Codex-specific extension in their
event-specific tables.
`SessionStart`, `PreToolUse`, `PermissionRequest`, `PostToolUse`,
`UserPromptSubmit`, `SubagentStart`, `SubagentStop`, and `Stop` also include
`permission_mode`, which describes the current permission mode as `default`,
`acceptEdits`, `plan`, `dontAsk`, or `bypassPermissions`.
`transcript_path` points to a conversation transcript for convenience, but the
transcript format is not a stable interface for hooks and may change over time.
If you need the full wire format, see Schemas.
Common output fields
`SessionStart`, `PreCompact`, `PostCompact`, `UserPromptSubmit`,
`SubagentStop`, and `Stop` support these shared JSON fields. `SubagentStart`
accepts the same shape for `systemMessage` and hook-specific context, but
`continue: false` doesn’t stop the subagent:

```
{
  "continue": true,
  "stopReason": "optional",
  "systemMessage": "optional",
  "suppressOutput": false
}
```

FieldEffect`continue`If `false`, marks that hook run as stopped`stopReason`Recorded as the reason for stopping`systemMessage`Surfaced as a warning in the UI or event stream`suppressOutput`Parsed today but not yet implemented
Exit `0` with no output is treated as success and Codex continues.
`PreToolUse` and `PermissionRequest` support `systemMessage`, but `continue`,
`stopReason`, and `suppressOutput` aren’t currently supported for those events.
If a `PreToolUse` hook returns one of those unsupported fields, Codex marks
that hook run as failed, reports the error, and continues the tool call.
`PostToolUse` supports `systemMessage`, `continue: false`, and `stopReason`.
`suppressOutput` is parsed but not currently supported for that event.
Hooks
SessionStart
`matcher` is applied to `source` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`source``string`How the session started: `startup`, `resume`, `clear`, or `compact`
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and this
hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Load the workspace conventions before editing."
  }
}
```

That `additionalContext` text is added as extra developer context.
SubagentStart
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`permission_mode``string`Current permission mode
Plain text on `stdout` is added as extra developer context for the subagent.
JSON on `stdout` supports `systemMessage` and this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "Review the repository test conventions first."
  }
}
```

That `additionalContext` text is added as extra developer context for the
subagent. `continue: false` is parsed for compatibility, but it doesn’t stop the
subagent from starting.
PreToolUse
`PreToolUse` can intercept Bash, file edits performed through `apply_patch`,
and MCP tool calls. It’s still a guardrail rather than a complete enforcement
boundary because Codex can often perform equivalent work through another
supported tool path.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage`. To deny a supported tool call, return
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by hook."
  }
}
```

Codex also accepts this older block shape:

```
{
  "decision": "block",
  "reason": "Destructive command blocked by hook."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
To add model-visible context without blocking, return
`hookSpecificOutput.additionalContext`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "The pending command touches generated files."
  }
}
```

To rewrite a supported tool call without blocking, return
`permissionDecision: "allow"` with `updatedInput`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {
      "command": "echo rewritten"
    }
  }
}
```

For Bash commands and `apply_patch`, `updatedInput` must include a string
`command` field. For MCP tools, `updatedInput` is the replacement arguments
object. Return `updatedInput` only with `permissionDecision: "allow"`; other
`updatedInput` shapes are reported as errors.
`permissionDecision: "ask"`, legacy `decision: "approve"`, `continue: false`,
`stopReason`, and `suppressOutput` are parsed but not supported yet. Codex marks
the hook run as failed, reports the error, and continues the tool call.
PermissionRequest
`PermissionRequest` runs when Codex is about to ask for approval, such as a
shell escalation or managed-network approval. It can allow the request, deny
the request, or decline to decide and let the normal approval prompt continue.
It doesn’t run for commands that don’t need approval.
`matcher` is applied to `tool_name` and matcher aliases. Current canonical
values include `Bash`, `apply_patch`, and MCP tool names such as
`mcp__server__tool`; `apply_patch` also matches `Edit` and `Write`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all the args.`tool_input.description``string | null`Human-readable approval reason, when Codex has one
Plain text on `stdout` is ignored.
Some tool inputs may include a human-readable description, but don’t rely on a
`tool_input.description` field for every tool.
To approve the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow"
    }
  }
}
```

To deny the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Blocked by repository policy."
    }
  }
}
```

If multiple matching hooks return decisions, any `deny` wins. Otherwise, an
`allow` lets the request proceed without surfacing the approval prompt. If no
matching hook decides, Codex uses the normal approval flow.
Don’t return `updatedInput`, `updatedPermissions`, or `interrupt` for
`PermissionRequest`; those fields are reserved for future behavior and fail
closed today.
PostToolUse
`PostToolUse` runs after supported tools produce output, including Bash,
`apply_patch`, and MCP tool calls. For Bash, it also runs after commands that
exit with a non-zero status. It can’t undo side effects from the tool that
already ran.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.`tool_response``JSON value`Tool-specific output. For MCP tools, this is the MCP call result.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage` and this hook-specific shape:

```
{
  "decision": "block",
  "reason": "The Bash output needs review before continuing.",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "The command updated generated files."
  }
}
```

That `additionalContext` text is added as extra developer context.
For this event, `decision: "block"` doesn’t undo the completed Bash command.
Instead, Codex records the feedback, replaces the tool result with that
feedback, and continues the model from the hook-provided message.
You can also use exit code `2` and write the feedback reason to `stderr`.
To stop normal processing of the original tool result after the command has
already run, return `continue: false`. Codex will replace the tool result with
your feedback or stop text and continue from there.
`updatedMCPToolOutput` and `suppressOutput` are parsed but not supported yet.
Codex marks the hook run as failed, reports the error, and continues normal
processing of the tool result.
PreCompact
`PreCompact` runs before Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PreCompact` hook returns `continue: false`, Codex stops before
compacting.
PostCompact
`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

## Managed hooks from requirements.toml

Enterprise-managed requirements can also define hooks inline under `[hooks]`.
This is useful when admins want to enforce the hook configuration while
delivering the actual scripts through MDM or another device-management system.
To enforce managed hooks even for users who disabled hooks locally, pin
`[features].hooks = true` in `requirements.toml` alongside `[hooks]`. To ignore
user, project, session, and plugin hooks while still allowing administrator
managed hooks, set `allow_managed_hooks_only = true`.

```
allow_managed_hooks_only = true

[features]
hooks = true

[hooks]
managed_dir = "/enterprise/hooks"
windows_managed_dir = 'C:\enterprise\hooks'

[[hooks.PreToolUse]]
matcher = "^Bash$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "python3 /enterprise/hooks/pre_tool_use_policy.py"
command_windows = 'py -3 C:\enterprise\hooks\pre_tool_use_policy.py'
timeout = 30
statusMessage = "Checking managed Bash command"
```

Notes for managed hooks:

`managed_dir` is used on macOS and Linux.
`windows_managed_dir` is used on Windows.
Codex doesn’t distribute the scripts in `managed_dir`; your enterprise
tooling must install and update them separately.
Managed hook commands should use absolute script paths under the configured
managed directory.
`allow_managed_hooks_only = true` skips hooks from user, project, session, and
plugin sources, but still loads managed hooks from `requirements.toml` and
other managed config layers.

Plugin-bundled hooks
When a plugin is enabled, Codex can load lifecycle hooks from that plugin
alongside user, project, and managed hooks.
By default, Codex looks for `hooks/hooks.json` inside the plugin root. A plugin
manifest can override that default with a `hooks` entry in
`.codex-plugin/plugin.json`. The manifest entry can be a `./`-prefixed path, an
array of `./`-prefixed paths, an inline hooks object, or an array of inline
hooks objects.

```
{
  "name": "repo-policy",
  "hooks": "./hooks/hooks.json"
}
```

Manifest hook paths are resolved relative to the plugin root and must stay
inside that root. If a manifest defines `hooks`, Codex uses those manifest
entries instead of the default `hooks/hooks.json`.
Plugin hook commands receive these environment variables:

`PLUGIN_ROOT` is a Codex-specific extension that points to the installed
plugin root.
`PLUGIN_DATA` is a Codex-specific extension that points to the plugin’s
writable data directory.
Codex also sets `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` for
compatibility with existing plugin hooks.

Plugin hooks use the same event schema as other hooks. Installing or enabling a
plugin doesn’t automatically trust its hooks; Codex skips plugin-bundled hooks
until you review and trust the current hook definition.
Matcher patterns
The `matcher` field is a regex string that filters when hooks fire. Use `"*"`,
`""`, or omit `matcher` entirely to match every occurrence of a supported
event.
Only some current Codex events honor `matcher`:

EventWhat `matcher` filtersNotes`PermissionRequest`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`PostToolUse`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`PostCompact`compaction triggerValues are `manual` or `auto``PreCompact`compaction triggerValues are `manual` or `auto``PreToolUse`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`SessionStart`start sourceValues are `startup`, `resume`, `clear`, and `compact``SubagentStart`subagent typeValues depend on the subagent that starts`SubagentStop`subagent typeValues depend on the subagent that stops`UserPromptSubmit`not supportedAny configured `matcher` is ignored for this event`Stop`not supportedAny configured `matcher` is ignored for this event
*For `apply_patch`, `matcher` values can also use `Edit` or `Write`.
Examples:

`Bash`
`^apply_patch$`
`Edit|Write`
`mcp__filesystem__read_file`
`mcp__filesystem__.*`
`startup|resume|clear|compact`
`manual|auto`

Common input fields
Every command hook receives one JSON object on `stdin`.
These are the shared fields you will usually use:

FieldTypeMeaning`session_id``string`Current Codex session id. Subagent hooks use the parent session id.`transcript_path``string | null`Path to the session transcript file, if any`cwd``string`Working directory for the session`hook_event_name``string`Current hook event name`model``string`Codex-specific extension. Active model slug
Turn-scoped hooks list `turn_id` as a Codex-specific extension in their
event-specific tables.
`SessionStart`, `PreToolUse`, `PermissionRequest`, `PostToolUse`,
`UserPromptSubmit`, `SubagentStart`, `SubagentStop`, and `Stop` also include
`permission_mode`, which describes the current permission mode as `default`,
`acceptEdits`, `plan`, `dontAsk`, or `bypassPermissions`.
`transcript_path` points to a conversation transcript for convenience, but the
transcript format is not a stable interface for hooks and may change over time.
If you need the full wire format, see Schemas.
Common output fields
`SessionStart`, `PreCompact`, `PostCompact`, `UserPromptSubmit`,
`SubagentStop`, and `Stop` support these shared JSON fields. `SubagentStart`
accepts the same shape for `systemMessage` and hook-specific context, but
`continue: false` doesn’t stop the subagent:

```
{
  "continue": true,
  "stopReason": "optional",
  "systemMessage": "optional",
  "suppressOutput": false
}
```

FieldEffect`continue`If `false`, marks that hook run as stopped`stopReason`Recorded as the reason for stopping`systemMessage`Surfaced as a warning in the UI or event stream`suppressOutput`Parsed today but not yet implemented
Exit `0` with no output is treated as success and Codex continues.
`PreToolUse` and `PermissionRequest` support `systemMessage`, but `continue`,
`stopReason`, and `suppressOutput` aren’t currently supported for those events.
If a `PreToolUse` hook returns one of those unsupported fields, Codex marks
that hook run as failed, reports the error, and continues the tool call.
`PostToolUse` supports `systemMessage`, `continue: false`, and `stopReason`.
`suppressOutput` is parsed but not currently supported for that event.
Hooks
SessionStart
`matcher` is applied to `source` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`source``string`How the session started: `startup`, `resume`, `clear`, or `compact`
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and this
hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Load the workspace conventions before editing."
  }
}
```

That `additionalContext` text is added as extra developer context.
SubagentStart
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`permission_mode``string`Current permission mode
Plain text on `stdout` is added as extra developer context for the subagent.
JSON on `stdout` supports `systemMessage` and this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "Review the repository test conventions first."
  }
}
```

That `additionalContext` text is added as extra developer context for the
subagent. `continue: false` is parsed for compatibility, but it doesn’t stop the
subagent from starting.
PreToolUse
`PreToolUse` can intercept Bash, file edits performed through `apply_patch`,
and MCP tool calls. It’s still a guardrail rather than a complete enforcement
boundary because Codex can often perform equivalent work through another
supported tool path.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage`. To deny a supported tool call, return
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by hook."
  }
}
```

Codex also accepts this older block shape:

```
{
  "decision": "block",
  "reason": "Destructive command blocked by hook."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
To add model-visible context without blocking, return
`hookSpecificOutput.additionalContext`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "The pending command touches generated files."
  }
}
```

To rewrite a supported tool call without blocking, return
`permissionDecision: "allow"` with `updatedInput`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {
      "command": "echo rewritten"
    }
  }
}
```

For Bash commands and `apply_patch`, `updatedInput` must include a string
`command` field. For MCP tools, `updatedInput` is the replacement arguments
object. Return `updatedInput` only with `permissionDecision: "allow"`; other
`updatedInput` shapes are reported as errors.
`permissionDecision: "ask"`, legacy `decision: "approve"`, `continue: false`,
`stopReason`, and `suppressOutput` are parsed but not supported yet. Codex marks
the hook run as failed, reports the error, and continues the tool call.
PermissionRequest
`PermissionRequest` runs when Codex is about to ask for approval, such as a
shell escalation or managed-network approval. It can allow the request, deny
the request, or decline to decide and let the normal approval prompt continue.
It doesn’t run for commands that don’t need approval.
`matcher` is applied to `tool_name` and matcher aliases. Current canonical
values include `Bash`, `apply_patch`, and MCP tool names such as
`mcp__server__tool`; `apply_patch` also matches `Edit` and `Write`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all the args.`tool_input.description``string | null`Human-readable approval reason, when Codex has one
Plain text on `stdout` is ignored.
Some tool inputs may include a human-readable description, but don’t rely on a
`tool_input.description` field for every tool.
To approve the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow"
    }
  }
}
```

To deny the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Blocked by repository policy."
    }
  }
}
```

If multiple matching hooks return decisions, any `deny` wins. Otherwise, an
`allow` lets the request proceed without surfacing the approval prompt. If no
matching hook decides, Codex uses the normal approval flow.
Don’t return `updatedInput`, `updatedPermissions`, or `interrupt` for
`PermissionRequest`; those fields are reserved for future behavior and fail
closed today.
PostToolUse
`PostToolUse` runs after supported tools produce output, including Bash,
`apply_patch`, and MCP tool calls. For Bash, it also runs after commands that
exit with a non-zero status. It can’t undo side effects from the tool that
already ran.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.`tool_response``JSON value`Tool-specific output. For MCP tools, this is the MCP call result.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage` and this hook-specific shape:

```
{
  "decision": "block",
  "reason": "The Bash output needs review before continuing.",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "The command updated generated files."
  }
}
```

That `additionalContext` text is added as extra developer context.
For this event, `decision: "block"` doesn’t undo the completed Bash command.
Instead, Codex records the feedback, replaces the tool result with that
feedback, and continues the model from the hook-provided message.
You can also use exit code `2` and write the feedback reason to `stderr`.
To stop normal processing of the original tool result after the command has
already run, return `continue: false`. Codex will replace the tool result with
your feedback or stop text and continue from there.
`updatedMCPToolOutput` and `suppressOutput` are parsed but not supported yet.
Codex marks the hook run as failed, reports the error, and continues normal
processing of the tool result.
PreCompact
`PreCompact` runs before Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PreCompact` hook returns `continue: false`, Codex stops before
compacting.
PostCompact
`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

## Plugin-bundled hooks

When a plugin is enabled, Codex can load lifecycle hooks from that plugin
alongside user, project, and managed hooks.
By default, Codex looks for `hooks/hooks.json` inside the plugin root. A plugin
manifest can override that default with a `hooks` entry in
`.codex-plugin/plugin.json`. The manifest entry can be a `./`-prefixed path, an
array of `./`-prefixed paths, an inline hooks object, or an array of inline
hooks objects.

```
{
  "name": "repo-policy",
  "hooks": "./hooks/hooks.json"
}
```

Manifest hook paths are resolved relative to the plugin root and must stay
inside that root. If a manifest defines `hooks`, Codex uses those manifest
entries instead of the default `hooks/hooks.json`.
Plugin hook commands receive these environment variables:

`PLUGIN_ROOT` is a Codex-specific extension that points to the installed
plugin root.
`PLUGIN_DATA` is a Codex-specific extension that points to the plugin’s
writable data directory.
Codex also sets `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` for
compatibility with existing plugin hooks.

Plugin hooks use the same event schema as other hooks. Installing or enabling a
plugin doesn’t automatically trust its hooks; Codex skips plugin-bundled hooks
until you review and trust the current hook definition.
Matcher patterns
The `matcher` field is a regex string that filters when hooks fire. Use `"*"`,
`""`, or omit `matcher` entirely to match every occurrence of a supported
event.
Only some current Codex events honor `matcher`:

EventWhat `matcher` filtersNotes`PermissionRequest`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`PostToolUse`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`PostCompact`compaction triggerValues are `manual` or `auto``PreCompact`compaction triggerValues are `manual` or `auto``PreToolUse`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`SessionStart`start sourceValues are `startup`, `resume`, `clear`, and `compact``SubagentStart`subagent typeValues depend on the subagent that starts`SubagentStop`subagent typeValues depend on the subagent that stops`UserPromptSubmit`not supportedAny configured `matcher` is ignored for this event`Stop`not supportedAny configured `matcher` is ignored for this event
*For `apply_patch`, `matcher` values can also use `Edit` or `Write`.
Examples:

`Bash`
`^apply_patch$`
`Edit|Write`
`mcp__filesystem__read_file`
`mcp__filesystem__.*`
`startup|resume|clear|compact`
`manual|auto`

Common input fields
Every command hook receives one JSON object on `stdin`.
These are the shared fields you will usually use:

FieldTypeMeaning`session_id``string`Current Codex session id. Subagent hooks use the parent session id.`transcript_path``string | null`Path to the session transcript file, if any`cwd``string`Working directory for the session`hook_event_name``string`Current hook event name`model``string`Codex-specific extension. Active model slug
Turn-scoped hooks list `turn_id` as a Codex-specific extension in their
event-specific tables.
`SessionStart`, `PreToolUse`, `PermissionRequest`, `PostToolUse`,
`UserPromptSubmit`, `SubagentStart`, `SubagentStop`, and `Stop` also include
`permission_mode`, which describes the current permission mode as `default`,
`acceptEdits`, `plan`, `dontAsk`, or `bypassPermissions`.
`transcript_path` points to a conversation transcript for convenience, but the
transcript format is not a stable interface for hooks and may change over time.
If you need the full wire format, see Schemas.
Common output fields
`SessionStart`, `PreCompact`, `PostCompact`, `UserPromptSubmit`,
`SubagentStop`, and `Stop` support these shared JSON fields. `SubagentStart`
accepts the same shape for `systemMessage` and hook-specific context, but
`continue: false` doesn’t stop the subagent:

```
{
  "continue": true,
  "stopReason": "optional",
  "systemMessage": "optional",
  "suppressOutput": false
}
```

FieldEffect`continue`If `false`, marks that hook run as stopped`stopReason`Recorded as the reason for stopping`systemMessage`Surfaced as a warning in the UI or event stream`suppressOutput`Parsed today but not yet implemented
Exit `0` with no output is treated as success and Codex continues.
`PreToolUse` and `PermissionRequest` support `systemMessage`, but `continue`,
`stopReason`, and `suppressOutput` aren’t currently supported for those events.
If a `PreToolUse` hook returns one of those unsupported fields, Codex marks
that hook run as failed, reports the error, and continues the tool call.
`PostToolUse` supports `systemMessage`, `continue: false`, and `stopReason`.
`suppressOutput` is parsed but not currently supported for that event.
Hooks
SessionStart
`matcher` is applied to `source` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`source``string`How the session started: `startup`, `resume`, `clear`, or `compact`
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and this
hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Load the workspace conventions before editing."
  }
}
```

That `additionalContext` text is added as extra developer context.
SubagentStart
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`permission_mode``string`Current permission mode
Plain text on `stdout` is added as extra developer context for the subagent.
JSON on `stdout` supports `systemMessage` and this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "Review the repository test conventions first."
  }
}
```

That `additionalContext` text is added as extra developer context for the
subagent. `continue: false` is parsed for compatibility, but it doesn’t stop the
subagent from starting.
PreToolUse
`PreToolUse` can intercept Bash, file edits performed through `apply_patch`,
and MCP tool calls. It’s still a guardrail rather than a complete enforcement
boundary because Codex can often perform equivalent work through another
supported tool path.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage`. To deny a supported tool call, return
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by hook."
  }
}
```

Codex also accepts this older block shape:

```
{
  "decision": "block",
  "reason": "Destructive command blocked by hook."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
To add model-visible context without blocking, return
`hookSpecificOutput.additionalContext`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "The pending command touches generated files."
  }
}
```

To rewrite a supported tool call without blocking, return
`permissionDecision: "allow"` with `updatedInput`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {
      "command": "echo rewritten"
    }
  }
}
```

For Bash commands and `apply_patch`, `updatedInput` must include a string
`command` field. For MCP tools, `updatedInput` is the replacement arguments
object. Return `updatedInput` only with `permissionDecision: "allow"`; other
`updatedInput` shapes are reported as errors.
`permissionDecision: "ask"`, legacy `decision: "approve"`, `continue: false`,
`stopReason`, and `suppressOutput` are parsed but not supported yet. Codex marks
the hook run as failed, reports the error, and continues the tool call.
PermissionRequest
`PermissionRequest` runs when Codex is about to ask for approval, such as a
shell escalation or managed-network approval. It can allow the request, deny
the request, or decline to decide and let the normal approval prompt continue.
It doesn’t run for commands that don’t need approval.
`matcher` is applied to `tool_name` and matcher aliases. Current canonical
values include `Bash`, `apply_patch`, and MCP tool names such as
`mcp__server__tool`; `apply_patch` also matches `Edit` and `Write`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all the args.`tool_input.description``string | null`Human-readable approval reason, when Codex has one
Plain text on `stdout` is ignored.
Some tool inputs may include a human-readable description, but don’t rely on a
`tool_input.description` field for every tool.
To approve the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow"
    }
  }
}
```

To deny the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Blocked by repository policy."
    }
  }
}
```

If multiple matching hooks return decisions, any `deny` wins. Otherwise, an
`allow` lets the request proceed without surfacing the approval prompt. If no
matching hook decides, Codex uses the normal approval flow.
Don’t return `updatedInput`, `updatedPermissions`, or `interrupt` for
`PermissionRequest`; those fields are reserved for future behavior and fail
closed today.
PostToolUse
`PostToolUse` runs after supported tools produce output, including Bash,
`apply_patch`, and MCP tool calls. For Bash, it also runs after commands that
exit with a non-zero status. It can’t undo side effects from the tool that
already ran.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.`tool_response``JSON value`Tool-specific output. For MCP tools, this is the MCP call result.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage` and this hook-specific shape:

```
{
  "decision": "block",
  "reason": "The Bash output needs review before continuing.",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "The command updated generated files."
  }
}
```

That `additionalContext` text is added as extra developer context.
For this event, `decision: "block"` doesn’t undo the completed Bash command.
Instead, Codex records the feedback, replaces the tool result with that
feedback, and continues the model from the hook-provided message.
You can also use exit code `2` and write the feedback reason to `stderr`.
To stop normal processing of the original tool result after the command has
already run, return `continue: false`. Codex will replace the tool result with
your feedback or stop text and continue from there.
`updatedMCPToolOutput` and `suppressOutput` are parsed but not supported yet.
Codex marks the hook run as failed, reports the error, and continues normal
processing of the tool result.
PreCompact
`PreCompact` runs before Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PreCompact` hook returns `continue: false`, Codex stops before
compacting.
PostCompact
`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

## Matcher patterns

The `matcher` field is a regex string that filters when hooks fire. Use `"*"`,
`""`, or omit `matcher` entirely to match every occurrence of a supported
event.
Only some current Codex events honor `matcher`:

EventWhat `matcher` filtersNotes`PermissionRequest`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`PostToolUse`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`PostCompact`compaction triggerValues are `manual` or `auto``PreCompact`compaction triggerValues are `manual` or `auto``PreToolUse`tool nameSupport includes `Bash`, `apply_patch`*, and MCP tool names`SessionStart`start sourceValues are `startup`, `resume`, `clear`, and `compact``SubagentStart`subagent typeValues depend on the subagent that starts`SubagentStop`subagent typeValues depend on the subagent that stops`UserPromptSubmit`not supportedAny configured `matcher` is ignored for this event`Stop`not supportedAny configured `matcher` is ignored for this event
*For `apply_patch`, `matcher` values can also use `Edit` or `Write`.
Examples:

`Bash`
`^apply_patch$`
`Edit|Write`
`mcp__filesystem__read_file`
`mcp__filesystem__.*`
`startup|resume|clear|compact`
`manual|auto`

Common input fields
Every command hook receives one JSON object on `stdin`.
These are the shared fields you will usually use:

FieldTypeMeaning`session_id``string`Current Codex session id. Subagent hooks use the parent session id.`transcript_path``string | null`Path to the session transcript file, if any`cwd``string`Working directory for the session`hook_event_name``string`Current hook event name`model``string`Codex-specific extension. Active model slug
Turn-scoped hooks list `turn_id` as a Codex-specific extension in their
event-specific tables.
`SessionStart`, `PreToolUse`, `PermissionRequest`, `PostToolUse`,
`UserPromptSubmit`, `SubagentStart`, `SubagentStop`, and `Stop` also include
`permission_mode`, which describes the current permission mode as `default`,
`acceptEdits`, `plan`, `dontAsk`, or `bypassPermissions`.
`transcript_path` points to a conversation transcript for convenience, but the
transcript format is not a stable interface for hooks and may change over time.
If you need the full wire format, see Schemas.
Common output fields
`SessionStart`, `PreCompact`, `PostCompact`, `UserPromptSubmit`,
`SubagentStop`, and `Stop` support these shared JSON fields. `SubagentStart`
accepts the same shape for `systemMessage` and hook-specific context, but
`continue: false` doesn’t stop the subagent:

```
{
  "continue": true,
  "stopReason": "optional",
  "systemMessage": "optional",
  "suppressOutput": false
}
```

FieldEffect`continue`If `false`, marks that hook run as stopped`stopReason`Recorded as the reason for stopping`systemMessage`Surfaced as a warning in the UI or event stream`suppressOutput`Parsed today but not yet implemented
Exit `0` with no output is treated as success and Codex continues.
`PreToolUse` and `PermissionRequest` support `systemMessage`, but `continue`,
`stopReason`, and `suppressOutput` aren’t currently supported for those events.
If a `PreToolUse` hook returns one of those unsupported fields, Codex marks
that hook run as failed, reports the error, and continues the tool call.
`PostToolUse` supports `systemMessage`, `continue: false`, and `stopReason`.
`suppressOutput` is parsed but not currently supported for that event.
Hooks
SessionStart
`matcher` is applied to `source` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`source``string`How the session started: `startup`, `resume`, `clear`, or `compact`
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and this
hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Load the workspace conventions before editing."
  }
}
```

That `additionalContext` text is added as extra developer context.
SubagentStart
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`permission_mode``string`Current permission mode
Plain text on `stdout` is added as extra developer context for the subagent.
JSON on `stdout` supports `systemMessage` and this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "Review the repository test conventions first."
  }
}
```

That `additionalContext` text is added as extra developer context for the
subagent. `continue: false` is parsed for compatibility, but it doesn’t stop the
subagent from starting.
PreToolUse
`PreToolUse` can intercept Bash, file edits performed through `apply_patch`,
and MCP tool calls. It’s still a guardrail rather than a complete enforcement
boundary because Codex can often perform equivalent work through another
supported tool path.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage`. To deny a supported tool call, return
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by hook."
  }
}
```

Codex also accepts this older block shape:

```
{
  "decision": "block",
  "reason": "Destructive command blocked by hook."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
To add model-visible context without blocking, return
`hookSpecificOutput.additionalContext`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "The pending command touches generated files."
  }
}
```

To rewrite a supported tool call without blocking, return
`permissionDecision: "allow"` with `updatedInput`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {
      "command": "echo rewritten"
    }
  }
}
```

For Bash commands and `apply_patch`, `updatedInput` must include a string
`command` field. For MCP tools, `updatedInput` is the replacement arguments
object. Return `updatedInput` only with `permissionDecision: "allow"`; other
`updatedInput` shapes are reported as errors.
`permissionDecision: "ask"`, legacy `decision: "approve"`, `continue: false`,
`stopReason`, and `suppressOutput` are parsed but not supported yet. Codex marks
the hook run as failed, reports the error, and continues the tool call.
PermissionRequest
`PermissionRequest` runs when Codex is about to ask for approval, such as a
shell escalation or managed-network approval. It can allow the request, deny
the request, or decline to decide and let the normal approval prompt continue.
It doesn’t run for commands that don’t need approval.
`matcher` is applied to `tool_name` and matcher aliases. Current canonical
values include `Bash`, `apply_patch`, and MCP tool names such as
`mcp__server__tool`; `apply_patch` also matches `Edit` and `Write`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all the args.`tool_input.description``string | null`Human-readable approval reason, when Codex has one
Plain text on `stdout` is ignored.
Some tool inputs may include a human-readable description, but don’t rely on a
`tool_input.description` field for every tool.
To approve the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow"
    }
  }
}
```

To deny the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Blocked by repository policy."
    }
  }
}
```

If multiple matching hooks return decisions, any `deny` wins. Otherwise, an
`allow` lets the request proceed without surfacing the approval prompt. If no
matching hook decides, Codex uses the normal approval flow.
Don’t return `updatedInput`, `updatedPermissions`, or `interrupt` for
`PermissionRequest`; those fields are reserved for future behavior and fail
closed today.
PostToolUse
`PostToolUse` runs after supported tools produce output, including Bash,
`apply_patch`, and MCP tool calls. For Bash, it also runs after commands that
exit with a non-zero status. It can’t undo side effects from the tool that
already ran.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.`tool_response``JSON value`Tool-specific output. For MCP tools, this is the MCP call result.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage` and this hook-specific shape:

```
{
  "decision": "block",
  "reason": "The Bash output needs review before continuing.",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "The command updated generated files."
  }
}
```

That `additionalContext` text is added as extra developer context.
For this event, `decision: "block"` doesn’t undo the completed Bash command.
Instead, Codex records the feedback, replaces the tool result with that
feedback, and continues the model from the hook-provided message.
You can also use exit code `2` and write the feedback reason to `stderr`.
To stop normal processing of the original tool result after the command has
already run, return `continue: false`. Codex will replace the tool result with
your feedback or stop text and continue from there.
`updatedMCPToolOutput` and `suppressOutput` are parsed but not supported yet.
Codex marks the hook run as failed, reports the error, and continues normal
processing of the tool result.
PreCompact
`PreCompact` runs before Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PreCompact` hook returns `continue: false`, Codex stops before
compacting.
PostCompact
`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

## Common input fields

Every command hook receives one JSON object on `stdin`.
These are the shared fields you will usually use:

FieldTypeMeaning`session_id``string`Current Codex session id. Subagent hooks use the parent session id.`transcript_path``string | null`Path to the session transcript file, if any`cwd``string`Working directory for the session`hook_event_name``string`Current hook event name`model``string`Codex-specific extension. Active model slug
Turn-scoped hooks list `turn_id` as a Codex-specific extension in their
event-specific tables.
`SessionStart`, `PreToolUse`, `PermissionRequest`, `PostToolUse`,
`UserPromptSubmit`, `SubagentStart`, `SubagentStop`, and `Stop` also include
`permission_mode`, which describes the current permission mode as `default`,
`acceptEdits`, `plan`, `dontAsk`, or `bypassPermissions`.
`transcript_path` points to a conversation transcript for convenience, but the
transcript format is not a stable interface for hooks and may change over time.
If you need the full wire format, see Schemas.
Common output fields
`SessionStart`, `PreCompact`, `PostCompact`, `UserPromptSubmit`,
`SubagentStop`, and `Stop` support these shared JSON fields. `SubagentStart`
accepts the same shape for `systemMessage` and hook-specific context, but
`continue: false` doesn’t stop the subagent:

```
{
  "continue": true,
  "stopReason": "optional",
  "systemMessage": "optional",
  "suppressOutput": false
}
```

FieldEffect`continue`If `false`, marks that hook run as stopped`stopReason`Recorded as the reason for stopping`systemMessage`Surfaced as a warning in the UI or event stream`suppressOutput`Parsed today but not yet implemented
Exit `0` with no output is treated as success and Codex continues.
`PreToolUse` and `PermissionRequest` support `systemMessage`, but `continue`,
`stopReason`, and `suppressOutput` aren’t currently supported for those events.
If a `PreToolUse` hook returns one of those unsupported fields, Codex marks
that hook run as failed, reports the error, and continues the tool call.
`PostToolUse` supports `systemMessage`, `continue: false`, and `stopReason`.
`suppressOutput` is parsed but not currently supported for that event.
Hooks
SessionStart
`matcher` is applied to `source` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`source``string`How the session started: `startup`, `resume`, `clear`, or `compact`
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and this
hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Load the workspace conventions before editing."
  }
}
```

That `additionalContext` text is added as extra developer context.
SubagentStart
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`permission_mode``string`Current permission mode
Plain text on `stdout` is added as extra developer context for the subagent.
JSON on `stdout` supports `systemMessage` and this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "Review the repository test conventions first."
  }
}
```

That `additionalContext` text is added as extra developer context for the
subagent. `continue: false` is parsed for compatibility, but it doesn’t stop the
subagent from starting.
PreToolUse
`PreToolUse` can intercept Bash, file edits performed through `apply_patch`,
and MCP tool calls. It’s still a guardrail rather than a complete enforcement
boundary because Codex can often perform equivalent work through another
supported tool path.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage`. To deny a supported tool call, return
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by hook."
  }
}
```

Codex also accepts this older block shape:

```
{
  "decision": "block",
  "reason": "Destructive command blocked by hook."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
To add model-visible context without blocking, return
`hookSpecificOutput.additionalContext`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "The pending command touches generated files."
  }
}
```

To rewrite a supported tool call without blocking, return
`permissionDecision: "allow"` with `updatedInput`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {
      "command": "echo rewritten"
    }
  }
}
```

For Bash commands and `apply_patch`, `updatedInput` must include a string
`command` field. For MCP tools, `updatedInput` is the replacement arguments
object. Return `updatedInput` only with `permissionDecision: "allow"`; other
`updatedInput` shapes are reported as errors.
`permissionDecision: "ask"`, legacy `decision: "approve"`, `continue: false`,
`stopReason`, and `suppressOutput` are parsed but not supported yet. Codex marks
the hook run as failed, reports the error, and continues the tool call.
PermissionRequest
`PermissionRequest` runs when Codex is about to ask for approval, such as a
shell escalation or managed-network approval. It can allow the request, deny
the request, or decline to decide and let the normal approval prompt continue.
It doesn’t run for commands that don’t need approval.
`matcher` is applied to `tool_name` and matcher aliases. Current canonical
values include `Bash`, `apply_patch`, and MCP tool names such as
`mcp__server__tool`; `apply_patch` also matches `Edit` and `Write`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all the args.`tool_input.description``string | null`Human-readable approval reason, when Codex has one
Plain text on `stdout` is ignored.
Some tool inputs may include a human-readable description, but don’t rely on a
`tool_input.description` field for every tool.
To approve the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow"
    }
  }
}
```

To deny the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Blocked by repository policy."
    }
  }
}
```

If multiple matching hooks return decisions, any `deny` wins. Otherwise, an
`allow` lets the request proceed without surfacing the approval prompt. If no
matching hook decides, Codex uses the normal approval flow.
Don’t return `updatedInput`, `updatedPermissions`, or `interrupt` for
`PermissionRequest`; those fields are reserved for future behavior and fail
closed today.
PostToolUse
`PostToolUse` runs after supported tools produce output, including Bash,
`apply_patch`, and MCP tool calls. For Bash, it also runs after commands that
exit with a non-zero status. It can’t undo side effects from the tool that
already ran.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.`tool_response``JSON value`Tool-specific output. For MCP tools, this is the MCP call result.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage` and this hook-specific shape:

```
{
  "decision": "block",
  "reason": "The Bash output needs review before continuing.",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "The command updated generated files."
  }
}
```

That `additionalContext` text is added as extra developer context.
For this event, `decision: "block"` doesn’t undo the completed Bash command.
Instead, Codex records the feedback, replaces the tool result with that
feedback, and continues the model from the hook-provided message.
You can also use exit code `2` and write the feedback reason to `stderr`.
To stop normal processing of the original tool result after the command has
already run, return `continue: false`. Codex will replace the tool result with
your feedback or stop text and continue from there.
`updatedMCPToolOutput` and `suppressOutput` are parsed but not supported yet.
Codex marks the hook run as failed, reports the error, and continues normal
processing of the tool result.
PreCompact
`PreCompact` runs before Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PreCompact` hook returns `continue: false`, Codex stops before
compacting.
PostCompact
`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

## Common output fields

`SessionStart`, `PreCompact`, `PostCompact`, `UserPromptSubmit`,
`SubagentStop`, and `Stop` support these shared JSON fields. `SubagentStart`
accepts the same shape for `systemMessage` and hook-specific context, but
`continue: false` doesn’t stop the subagent:

```
{
  "continue": true,
  "stopReason": "optional",
  "systemMessage": "optional",
  "suppressOutput": false
}
```

FieldEffect`continue`If `false`, marks that hook run as stopped`stopReason`Recorded as the reason for stopping`systemMessage`Surfaced as a warning in the UI or event stream`suppressOutput`Parsed today but not yet implemented
Exit `0` with no output is treated as success and Codex continues.
`PreToolUse` and `PermissionRequest` support `systemMessage`, but `continue`,
`stopReason`, and `suppressOutput` aren’t currently supported for those events.
If a `PreToolUse` hook returns one of those unsupported fields, Codex marks
that hook run as failed, reports the error, and continues the tool call.
`PostToolUse` supports `systemMessage`, `continue: false`, and `stopReason`.
`suppressOutput` is parsed but not currently supported for that event.
Hooks
SessionStart
`matcher` is applied to `source` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`source``string`How the session started: `startup`, `resume`, `clear`, or `compact`
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and this
hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Load the workspace conventions before editing."
  }
}
```

That `additionalContext` text is added as extra developer context.
SubagentStart
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`permission_mode``string`Current permission mode
Plain text on `stdout` is added as extra developer context for the subagent.
JSON on `stdout` supports `systemMessage` and this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "Review the repository test conventions first."
  }
}
```

That `additionalContext` text is added as extra developer context for the
subagent. `continue: false` is parsed for compatibility, but it doesn’t stop the
subagent from starting.
PreToolUse
`PreToolUse` can intercept Bash, file edits performed through `apply_patch`,
and MCP tool calls. It’s still a guardrail rather than a complete enforcement
boundary because Codex can often perform equivalent work through another
supported tool path.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage`. To deny a supported tool call, return
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by hook."
  }
}
```

Codex also accepts this older block shape:

```
{
  "decision": "block",
  "reason": "Destructive command blocked by hook."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
To add model-visible context without blocking, return
`hookSpecificOutput.additionalContext`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "The pending command touches generated files."
  }
}
```

To rewrite a supported tool call without blocking, return
`permissionDecision: "allow"` with `updatedInput`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {
      "command": "echo rewritten"
    }
  }
}
```

For Bash commands and `apply_patch`, `updatedInput` must include a string
`command` field. For MCP tools, `updatedInput` is the replacement arguments
object. Return `updatedInput` only with `permissionDecision: "allow"`; other
`updatedInput` shapes are reported as errors.
`permissionDecision: "ask"`, legacy `decision: "approve"`, `continue: false`,
`stopReason`, and `suppressOutput` are parsed but not supported yet. Codex marks
the hook run as failed, reports the error, and continues the tool call.
PermissionRequest
`PermissionRequest` runs when Codex is about to ask for approval, such as a
shell escalation or managed-network approval. It can allow the request, deny
the request, or decline to decide and let the normal approval prompt continue.
It doesn’t run for commands that don’t need approval.
`matcher` is applied to `tool_name` and matcher aliases. Current canonical
values include `Bash`, `apply_patch`, and MCP tool names such as
`mcp__server__tool`; `apply_patch` also matches `Edit` and `Write`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all the args.`tool_input.description``string | null`Human-readable approval reason, when Codex has one
Plain text on `stdout` is ignored.
Some tool inputs may include a human-readable description, but don’t rely on a
`tool_input.description` field for every tool.
To approve the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow"
    }
  }
}
```

To deny the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Blocked by repository policy."
    }
  }
}
```

If multiple matching hooks return decisions, any `deny` wins. Otherwise, an
`allow` lets the request proceed without surfacing the approval prompt. If no
matching hook decides, Codex uses the normal approval flow.
Don’t return `updatedInput`, `updatedPermissions`, or `interrupt` for
`PermissionRequest`; those fields are reserved for future behavior and fail
closed today.
PostToolUse
`PostToolUse` runs after supported tools produce output, including Bash,
`apply_patch`, and MCP tool calls. For Bash, it also runs after commands that
exit with a non-zero status. It can’t undo side effects from the tool that
already ran.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.`tool_response``JSON value`Tool-specific output. For MCP tools, this is the MCP call result.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage` and this hook-specific shape:

```
{
  "decision": "block",
  "reason": "The Bash output needs review before continuing.",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "The command updated generated files."
  }
}
```

That `additionalContext` text is added as extra developer context.
For this event, `decision: "block"` doesn’t undo the completed Bash command.
Instead, Codex records the feedback, replaces the tool result with that
feedback, and continues the model from the hook-provided message.
You can also use exit code `2` and write the feedback reason to `stderr`.
To stop normal processing of the original tool result after the command has
already run, return `continue: false`. Codex will replace the tool result with
your feedback or stop text and continue from there.
`updatedMCPToolOutput` and `suppressOutput` are parsed but not supported yet.
Codex marks the hook run as failed, reports the error, and continues normal
processing of the tool result.
PreCompact
`PreCompact` runs before Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PreCompact` hook returns `continue: false`, Codex stops before
compacting.
PostCompact
`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

### SessionStart

`matcher` is applied to `source` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`source``string`How the session started: `startup`, `resume`, `clear`, or `compact`
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and this
hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Load the workspace conventions before editing."
  }
}
```

That `additionalContext` text is added as extra developer context.
SubagentStart
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`permission_mode``string`Current permission mode
Plain text on `stdout` is added as extra developer context for the subagent.
JSON on `stdout` supports `systemMessage` and this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "Review the repository test conventions first."
  }
}
```

That `additionalContext` text is added as extra developer context for the
subagent. `continue: false` is parsed for compatibility, but it doesn’t stop the
subagent from starting.
PreToolUse
`PreToolUse` can intercept Bash, file edits performed through `apply_patch`,
and MCP tool calls. It’s still a guardrail rather than a complete enforcement
boundary because Codex can often perform equivalent work through another
supported tool path.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage`. To deny a supported tool call, return
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by hook."
  }
}
```

Codex also accepts this older block shape:

```
{
  "decision": "block",
  "reason": "Destructive command blocked by hook."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
To add model-visible context without blocking, return
`hookSpecificOutput.additionalContext`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "The pending command touches generated files."
  }
}
```

To rewrite a supported tool call without blocking, return
`permissionDecision: "allow"` with `updatedInput`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {
      "command": "echo rewritten"
    }
  }
}
```

For Bash commands and `apply_patch`, `updatedInput` must include a string
`command` field. For MCP tools, `updatedInput` is the replacement arguments
object. Return `updatedInput` only with `permissionDecision: "allow"`; other
`updatedInput` shapes are reported as errors.
`permissionDecision: "ask"`, legacy `decision: "approve"`, `continue: false`,
`stopReason`, and `suppressOutput` are parsed but not supported yet. Codex marks
the hook run as failed, reports the error, and continues the tool call.
PermissionRequest
`PermissionRequest` runs when Codex is about to ask for approval, such as a
shell escalation or managed-network approval. It can allow the request, deny
the request, or decline to decide and let the normal approval prompt continue.
It doesn’t run for commands that don’t need approval.
`matcher` is applied to `tool_name` and matcher aliases. Current canonical
values include `Bash`, `apply_patch`, and MCP tool names such as
`mcp__server__tool`; `apply_patch` also matches `Edit` and `Write`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all the args.`tool_input.description``string | null`Human-readable approval reason, when Codex has one
Plain text on `stdout` is ignored.
Some tool inputs may include a human-readable description, but don’t rely on a
`tool_input.description` field for every tool.
To approve the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow"
    }
  }
}
```

To deny the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Blocked by repository policy."
    }
  }
}
```

If multiple matching hooks return decisions, any `deny` wins. Otherwise, an
`allow` lets the request proceed without surfacing the approval prompt. If no
matching hook decides, Codex uses the normal approval flow.
Don’t return `updatedInput`, `updatedPermissions`, or `interrupt` for
`PermissionRequest`; those fields are reserved for future behavior and fail
closed today.
PostToolUse
`PostToolUse` runs after supported tools produce output, including Bash,
`apply_patch`, and MCP tool calls. For Bash, it also runs after commands that
exit with a non-zero status. It can’t undo side effects from the tool that
already ran.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.`tool_response``JSON value`Tool-specific output. For MCP tools, this is the MCP call result.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage` and this hook-specific shape:

```
{
  "decision": "block",
  "reason": "The Bash output needs review before continuing.",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "The command updated generated files."
  }
}
```

That `additionalContext` text is added as extra developer context.
For this event, `decision: "block"` doesn’t undo the completed Bash command.
Instead, Codex records the feedback, replaces the tool result with that
feedback, and continues the model from the hook-provided message.
You can also use exit code `2` and write the feedback reason to `stderr`.
To stop normal processing of the original tool result after the command has
already run, return `continue: false`. Codex will replace the tool result with
your feedback or stop text and continue from there.
`updatedMCPToolOutput` and `suppressOutput` are parsed but not supported yet.
Codex marks the hook run as failed, reports the error, and continues normal
processing of the tool result.
PreCompact
`PreCompact` runs before Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PreCompact` hook returns `continue: false`, Codex stops before
compacting.
PostCompact
`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

### SubagentStart

`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`permission_mode``string`Current permission mode
Plain text on `stdout` is added as extra developer context for the subagent.
JSON on `stdout` supports `systemMessage` and this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "Review the repository test conventions first."
  }
}
```

That `additionalContext` text is added as extra developer context for the
subagent. `continue: false` is parsed for compatibility, but it doesn’t stop the
subagent from starting.
PreToolUse
`PreToolUse` can intercept Bash, file edits performed through `apply_patch`,
and MCP tool calls. It’s still a guardrail rather than a complete enforcement
boundary because Codex can often perform equivalent work through another
supported tool path.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage`. To deny a supported tool call, return
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by hook."
  }
}
```

Codex also accepts this older block shape:

```
{
  "decision": "block",
  "reason": "Destructive command blocked by hook."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
To add model-visible context without blocking, return
`hookSpecificOutput.additionalContext`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "The pending command touches generated files."
  }
}
```

To rewrite a supported tool call without blocking, return
`permissionDecision: "allow"` with `updatedInput`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {
      "command": "echo rewritten"
    }
  }
}
```

For Bash commands and `apply_patch`, `updatedInput` must include a string
`command` field. For MCP tools, `updatedInput` is the replacement arguments
object. Return `updatedInput` only with `permissionDecision: "allow"`; other
`updatedInput` shapes are reported as errors.
`permissionDecision: "ask"`, legacy `decision: "approve"`, `continue: false`,
`stopReason`, and `suppressOutput` are parsed but not supported yet. Codex marks
the hook run as failed, reports the error, and continues the tool call.
PermissionRequest
`PermissionRequest` runs when Codex is about to ask for approval, such as a
shell escalation or managed-network approval. It can allow the request, deny
the request, or decline to decide and let the normal approval prompt continue.
It doesn’t run for commands that don’t need approval.
`matcher` is applied to `tool_name` and matcher aliases. Current canonical
values include `Bash`, `apply_patch`, and MCP tool names such as
`mcp__server__tool`; `apply_patch` also matches `Edit` and `Write`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all the args.`tool_input.description``string | null`Human-readable approval reason, when Codex has one
Plain text on `stdout` is ignored.
Some tool inputs may include a human-readable description, but don’t rely on a
`tool_input.description` field for every tool.
To approve the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow"
    }
  }
}
```

To deny the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Blocked by repository policy."
    }
  }
}
```

If multiple matching hooks return decisions, any `deny` wins. Otherwise, an
`allow` lets the request proceed without surfacing the approval prompt. If no
matching hook decides, Codex uses the normal approval flow.
Don’t return `updatedInput`, `updatedPermissions`, or `interrupt` for
`PermissionRequest`; those fields are reserved for future behavior and fail
closed today.
PostToolUse
`PostToolUse` runs after supported tools produce output, including Bash,
`apply_patch`, and MCP tool calls. For Bash, it also runs after commands that
exit with a non-zero status. It can’t undo side effects from the tool that
already ran.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.`tool_response``JSON value`Tool-specific output. For MCP tools, this is the MCP call result.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage` and this hook-specific shape:

```
{
  "decision": "block",
  "reason": "The Bash output needs review before continuing.",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "The command updated generated files."
  }
}
```

That `additionalContext` text is added as extra developer context.
For this event, `decision: "block"` doesn’t undo the completed Bash command.
Instead, Codex records the feedback, replaces the tool result with that
feedback, and continues the model from the hook-provided message.
You can also use exit code `2` and write the feedback reason to `stderr`.
To stop normal processing of the original tool result after the command has
already run, return `continue: false`. Codex will replace the tool result with
your feedback or stop text and continue from there.
`updatedMCPToolOutput` and `suppressOutput` are parsed but not supported yet.
Codex marks the hook run as failed, reports the error, and continues normal
processing of the tool result.
PreCompact
`PreCompact` runs before Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PreCompact` hook returns `continue: false`, Codex stops before
compacting.
PostCompact
`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

### PreToolUse

`PreToolUse` can intercept Bash, file edits performed through `apply_patch`,
and MCP tool calls. It’s still a guardrail rather than a complete enforcement
boundary because Codex can often perform equivalent work through another
supported tool path.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage`. To deny a supported tool call, return
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by hook."
  }
}
```

Codex also accepts this older block shape:

```
{
  "decision": "block",
  "reason": "Destructive command blocked by hook."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
To add model-visible context without blocking, return
`hookSpecificOutput.additionalContext`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "The pending command touches generated files."
  }
}
```

To rewrite a supported tool call without blocking, return
`permissionDecision: "allow"` with `updatedInput`:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {
      "command": "echo rewritten"
    }
  }
}
```

For Bash commands and `apply_patch`, `updatedInput` must include a string
`command` field. For MCP tools, `updatedInput` is the replacement arguments
object. Return `updatedInput` only with `permissionDecision: "allow"`; other
`updatedInput` shapes are reported as errors.
`permissionDecision: "ask"`, legacy `decision: "approve"`, `continue: false`,
`stopReason`, and `suppressOutput` are parsed but not supported yet. Codex marks
the hook run as failed, reports the error, and continues the tool call.
PermissionRequest
`PermissionRequest` runs when Codex is about to ask for approval, such as a
shell escalation or managed-network approval. It can allow the request, deny
the request, or decline to decide and let the normal approval prompt continue.
It doesn’t run for commands that don’t need approval.
`matcher` is applied to `tool_name` and matcher aliases. Current canonical
values include `Bash`, `apply_patch`, and MCP tool names such as
`mcp__server__tool`; `apply_patch` also matches `Edit` and `Write`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all the args.`tool_input.description``string | null`Human-readable approval reason, when Codex has one
Plain text on `stdout` is ignored.
Some tool inputs may include a human-readable description, but don’t rely on a
`tool_input.description` field for every tool.
To approve the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow"
    }
  }
}
```

To deny the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Blocked by repository policy."
    }
  }
}
```

If multiple matching hooks return decisions, any `deny` wins. Otherwise, an
`allow` lets the request proceed without surfacing the approval prompt. If no
matching hook decides, Codex uses the normal approval flow.
Don’t return `updatedInput`, `updatedPermissions`, or `interrupt` for
`PermissionRequest`; those fields are reserved for future behavior and fail
closed today.
PostToolUse
`PostToolUse` runs after supported tools produce output, including Bash,
`apply_patch`, and MCP tool calls. For Bash, it also runs after commands that
exit with a non-zero status. It can’t undo side effects from the tool that
already ran.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.`tool_response``JSON value`Tool-specific output. For MCP tools, this is the MCP call result.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage` and this hook-specific shape:

```
{
  "decision": "block",
  "reason": "The Bash output needs review before continuing.",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "The command updated generated files."
  }
}
```

That `additionalContext` text is added as extra developer context.
For this event, `decision: "block"` doesn’t undo the completed Bash command.
Instead, Codex records the feedback, replaces the tool result with that
feedback, and continues the model from the hook-provided message.
You can also use exit code `2` and write the feedback reason to `stderr`.
To stop normal processing of the original tool result after the command has
already run, return `continue: false`. Codex will replace the tool result with
your feedback or stop text and continue from there.
`updatedMCPToolOutput` and `suppressOutput` are parsed but not supported yet.
Codex marks the hook run as failed, reports the error, and continues normal
processing of the tool result.
PreCompact
`PreCompact` runs before Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PreCompact` hook returns `continue: false`, Codex stops before
compacting.
PostCompact
`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

### PermissionRequest

`PermissionRequest` runs when Codex is about to ask for approval, such as a
shell escalation or managed-network approval. It can allow the request, deny
the request, or decline to decide and let the normal approval prompt continue.
It doesn’t run for commands that don’t need approval.
`matcher` is applied to `tool_name` and matcher aliases. Current canonical
values include `Bash`, `apply_patch`, and MCP tool names such as
`mcp__server__tool`; `apply_patch` also matches `Edit` and `Write`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all the args.`tool_input.description``string | null`Human-readable approval reason, when Codex has one
Plain text on `stdout` is ignored.
Some tool inputs may include a human-readable description, but don’t rely on a
`tool_input.description` field for every tool.
To approve the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow"
    }
  }
}
```

To deny the request, return:

```
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Blocked by repository policy."
    }
  }
}
```

If multiple matching hooks return decisions, any `deny` wins. Otherwise, an
`allow` lets the request proceed without surfacing the approval prompt. If no
matching hook decides, Codex uses the normal approval flow.
Don’t return `updatedInput`, `updatedPermissions`, or `interrupt` for
`PermissionRequest`; those fields are reserved for future behavior and fail
closed today.
PostToolUse
`PostToolUse` runs after supported tools produce output, including Bash,
`apply_patch`, and MCP tool calls. For Bash, it also runs after commands that
exit with a non-zero status. It can’t undo side effects from the tool that
already ran.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.`tool_response``JSON value`Tool-specific output. For MCP tools, this is the MCP call result.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage` and this hook-specific shape:

```
{
  "decision": "block",
  "reason": "The Bash output needs review before continuing.",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "The command updated generated files."
  }
}
```

That `additionalContext` text is added as extra developer context.
For this event, `decision: "block"` doesn’t undo the completed Bash command.
Instead, Codex records the feedback, replaces the tool result with that
feedback, and continues the model from the hook-provided message.
You can also use exit code `2` and write the feedback reason to `stderr`.
To stop normal processing of the original tool result after the command has
already run, return `continue: false`. Codex will replace the tool result with
your feedback or stop text and continue from there.
`updatedMCPToolOutput` and `suppressOutput` are parsed but not supported yet.
Codex marks the hook run as failed, reports the error, and continues normal
processing of the tool result.
PreCompact
`PreCompact` runs before Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PreCompact` hook returns `continue: false`, Codex stops before
compacting.
PostCompact
`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

### PostToolUse

`PostToolUse` runs after supported tools produce output, including Bash,
`apply_patch`, and MCP tool calls. For Bash, it also runs after commands that
exit with a non-zero status. It can’t undo side effects from the tool that
already ran.
This doesn’t intercept all shell calls yet, only the simple ones. The newer
`unified_exec` mechanism allows richer streaming stdin/stdout handling of
shell, but interception is incomplete. Similarly, this doesn’t intercept
`WebSearch` or other non-shell, non-MCP tool calls.
`matcher` is applied to `tool_name` and matcher aliases. For file edits through
`apply_patch`, `matcher` values can use `apply_patch`, `Edit`, or `Write`; hook input
still reports `tool_name: "apply_patch"`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`tool_name``string`Canonical hook tool name, such as `Bash`, `apply_patch`, or an MCP name like `mcp__fs__read``tool_use_id``string`Tool-call id for this invocation`tool_input``JSON value`Tool-specific input. `Bash` and `apply_patch` use `tool_input.command` while MCP tools send all arguments.`tool_response``JSON value`Tool-specific output. For MCP tools, this is the MCP call result.
Plain text on `stdout` is ignored.
JSON on `stdout` can use `systemMessage` and this hook-specific shape:

```
{
  "decision": "block",
  "reason": "The Bash output needs review before continuing.",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "The command updated generated files."
  }
}
```

That `additionalContext` text is added as extra developer context.
For this event, `decision: "block"` doesn’t undo the completed Bash command.
Instead, Codex records the feedback, replaces the tool result with that
feedback, and continues the model from the hook-provided message.
You can also use exit code `2` and write the feedback reason to `stderr`.
To stop normal processing of the original tool result after the command has
already run, return `continue: false`. Codex will replace the tool result with
your feedback or stop text and continue from there.
`updatedMCPToolOutput` and `suppressOutput` are parsed but not supported yet.
Codex marks the hook run as failed, reports the error, and continues normal
processing of the tool result.
PreCompact
`PreCompact` runs before Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PreCompact` hook returns `continue: false`, Codex stops before
compacting.
PostCompact
`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

### PreCompact

`PreCompact` runs before Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PreCompact` hook returns `continue: false`, Codex stops before
compacting.
PostCompact
`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

### PostCompact

`PostCompact` runs after Codex compacts the conversation. `matcher` is applied
to `trigger`, whose values are `manual` and `auto`.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`trigger``string`What triggered compaction: `manual` or `auto`
Plain text on `stdout` is ignored.
JSON on `stdout` supports Common output fields. If a
matching `PostCompact` hook returns `continue: false`, Codex stops after
compacting.
UserPromptSubmit
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

### UserPromptSubmit

`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`prompt``string`User prompt that’s about to be sent
Plain text on `stdout` is added as extra developer context.
JSON on `stdout` supports Common output fields and
this hook-specific shape:

```
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Ask for a clearer reproduction before editing files."
  }
}
```

That `additionalContext` text is added as extra developer context.
To block the prompt, return:

```
{
  "decision": "block",
  "reason": "Ask for confirmation before doing that."
}
```

You can also use exit code `2` and write the blocking reason to `stderr`.
SubagentStop
`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

### SubagentStop

`matcher` is applied to `agent_type` for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`agent_id``string`Identifier for the subagent`agent_type``string`Subagent type or profile`agent_transcript_path``string | null`Path to the subagent transcript file, if any`stop_hook_active``boolean`Whether this subagent was already continued`last_assistant_message``string | null`Latest subagent assistant message, if available
`SubagentStop` expects JSON on `stdout` when it exits `0`. Plain text output is
invalid for this event.
JSON on `stdout` supports Common output fields. To ask
Codex to continue the subagent flow, return:

```
{
  "decision": "block",
  "reason": "Run one more focused pass inside the subagent."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
If any matching `SubagentStop` hook returns `continue: false`, that takes
precedence over continuation decisions from other matching `SubagentStop`
hooks.
Stop
`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

### Stop

`matcher` isn’t currently used for this event.
Fields in addition to Common input fields:

FieldTypeMeaning`turn_id``string`Codex-specific extension. Active Codex turn id`stop_hook_active``boolean`Whether this turn was already continued by `Stop``last_assistant_message``string | null`Latest assistant message text, if available
`Stop` expects JSON on `stdout` when it exits `0`. Plain text output is invalid
for this event.
JSON on `stdout` supports Common output fields. To keep
Codex going, return:

```
{
  "decision": "block",
  "reason": "Run one more pass over the failing tests."
}
```

You can also use exit code `2` and write the continuation reason to `stderr`.
For this event, `decision: "block"` doesn’t reject the turn. Instead, it tells
Codex to continue and automatically creates a new continuation prompt that acts
as a new user prompt, using your `reason` as that prompt text.
If any matching `Stop` hook returns `continue: false`, that takes precedence
over continuation decisions from other matching `Stop` hooks.
Schemas
The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();

## Schemas

The linked `main` branch schemas may include hook fields that are not in the
current release. Use this page as the release behavior reference.
If you need the exact current wire format, see the generated schemas in the
Codex GitHub repository.        
    const copyHeadingLink = async (slug) => {
      const url = `${location.origin}${location.pathname}#${slug}`;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          return;
        } catch (error) {
          console.warn("Copy to clipboard failed", error);
        }
      }

      window.prompt("Copy link", url);
    };

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const button = target.closest("[data-anchor-id]");
      if (!button) return;

      const slug = button.getAttribute("data-anchor-id");
      if (!slug) return;

      event.preventDefault();
      copyHeadingLink(slug);
      const heading = document.getElementById(slug);
      if (heading) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      history.replaceState(null, "", `#${slug}`);
    });
             (()=>{var e=async t=>{await(await t())()};(self.Astro||(self.Astro={})).only=e;window.dispatchEvent(new Event("astro:only"));})();  var o="@vercel/speed-insights",u="1.3.1",f=()=>{window.si||(window.si=function(...r){(window.siq=window.siq||[]).push(r)})};function l(){return typeof window{console.log(`[Vercel Speed Insights] Failed to load script from ${n}. Please check if any content blockers are enabled and try again.`)},document.head.appendChild(t),{setRoute:s=>{t.dataset.route=s??void 0}}}function p(){try{return}catch{}}customElements.define("vercel-speed-insights",class extends HTMLElement{constructor(){super();try{const r=JSON.parse(this.dataset.props??"{}"),n=JSON.parse(this.dataset.params??"{}"),t=v(this.dataset.pathname??"",n);w({route:t,...r,framework:"astro",basePath:p(),beforeSend:window.speedInsightsBeforeSend})}catch(r){throw new Error(`Failed to parse SpeedInsights properties: ${r}`)}}}); Ask AI
Docs agent

Loading docs agent...
(() => {
  const registry = window.customElements;
  if (!registry || window.__docsAgentChatKitMoveGuardInstalled) return;
  window.__docsAgentChatKitMoveGuardInstalled = true;

  // Astro preserves the launcher with Element.moveBefore(). Registering this
  // callback before ChatKit is defined prevents its reconnect hooks from
  // replacing the live message-bridge iframe during that move.
  const registryPrototype = Object.getPrototypeOf(registry);
  const defineDescriptor = Object.getOwnPropertyDescriptor(
    registryPrototype,
    "define"
  );
  if (!defineDescriptor?.value) return;

  Object.defineProperty(registryPrototype, "define", {
    ...defineDescriptor,
    value(name, constructor, options) {
      if (
        name === "openai-chatkit" &&
        !("connectedMoveCallback" in constructor.prototype)
      ) {
        Object.defineProperty(
          constructor.prototype,
          "connectedMoveCallback",
          {
            configurable: true,
            value() {},
          }
        );
      }

      const result = defineDescriptor.value.call(
        this,
        name,
        constructor,
        options
      );
      if (name === "openai-chatkit") {
        Object.defineProperty(registryPrototype, "define", defineDescriptor);
      }
      return result;
    },
  });
})();
  function initializeDocsAgentLauncher() {
    const root = document.querySelector("[data-docs-agent-root]");
    if (!root || root.dataset.initialized === "true") return;
    if (typeof window.__createDocsAgentNavigationQueue !== "function") return;

    const mobileOpenButton = root.querySelector("button[data-docs-agent-open]");
    const closeButton = root.querySelector("[data-docs-agent-close]");
    const newButton = root.querySelector("[data-docs-agent-new]");
    const panel = root.querySelector("[data-docs-agent-panel]");
    const status = root.querySelector("[data-docs-agent-status]");
    let chatkit = root.querySelector("openai-chatkit");
    const apiURL = root.dataset.chatkitApiUrl;
    const domainKey = root.dataset.chatkitDomainKey || "local-dev";
    const startGreeting =
      root.dataset.chatkitGreeting || "OpenAI developer docs";
    const startPromptsByParentRoute = (() => {
      try {
        const parsed = JSON.parse(
          root.dataset.chatkitStartPromptsByRoute || "{}"
        );
        return parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? parsed
          : {};
      } catch {
        return {};
      }
    })();
    const docsAgentSessionStorageKey = "docs-agent.chatkit-session-id";
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    const randomUuid = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }

      const bytes = new Uint8Array(16);
      if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (let index = 0; index 
        byte.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    };

    let docsAgentSessionIdValue = null;

    const storeDocsAgentSessionId = (sessionId) => {
      docsAgentSessionIdValue = sessionId;
      try {
        window.sessionStorage.setItem(docsAgentSessionStorageKey, sessionId);
      } catch {
        // Ignore storage failures.
      }
      return sessionId;
    };

    const resetDocsAgentSessionId = () =>
      storeDocsAgentSessionId(randomUuid().toLowerCase());

    const docsAgentSessionId = () => {
      if (
        docsAgentSessionIdValue &&
        uuidPattern.test(docsAgentSessionIdValue)
      ) {
        return docsAgentSessionIdValue.toLowerCase();
      }
      try {
        const stored = window.sessionStorage.getItem(
          docsAgentSessionStorageKey
        );
        if (stored && uuidPattern.test(stored)) {
          docsAgentSessionIdValue = stored.toLowerCase();
          return docsAgentSessionIdValue;
        }
      } catch {
        // Fall through and create an in-memory session id.
      }
      return resetDocsAgentSessionId();
    };

    if (
      !mobileOpenButton ||
      !closeButton ||
      !newButton ||
      !(panel instanceof HTMLElement) ||
      !chatkit ||
      !apiURL
    ) {
      return;
    }

    let chatkitInitialized = false;
    let chatkitResponseActive = false;
    let chatkitTurnActive = false;
    let docsAgentNavigationInProgress = false;
    let chatkitReplacement = null;
    let desiredPathname = window.location.pathname || "/";
    let previousFocus = null;
    let lastPageSelection = { text: "", capturedAt: 0 };
    let conversationStartedTracked = false;

    const selectedTextLimit = 3000;
    const staleSelectionMs = 2 * 60 * 1000;
    const docsAgentRequestTimeoutMs = 40 * 1000;
    const docsAgentNavigationTimeoutMs = 8 * 1000;
    const docsAgentTransitionWaitTimeoutMs = 15 * 1000;
    const docsAgentInitializationTimeoutMs = 15 * 1000;
    const docsAgentUnavailableMessage =
      "The docs agent couldn't complete the request. Please retry.";
    const chatKitUserTurnTypes = new Set([
      "threads.create",
      "threads.add_user_message",
      "threads.retry_after_item",
    ]);
    const desktopPanelMedia = window.matchMedia("(min-width: 768px)");

    const withTimeout = (operation, timeoutMs, message) =>
      new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error(message)),
          timeoutMs
        );
        Promise.resolve(operation).then(
          (value) => {
            window.clearTimeout(timeout);
            resolve(value);
          },
          (error) => {
            window.clearTimeout(timeout);
            reject(error);
          }
        );
      });

    const requestDeadlineSignal = (existingSignal) => {
      const controller = new AbortController();
      const abort = (signal) => controller.abort(signal?.reason);
      if (existingSignal) {
        if (existingSignal.aborted) {
          abort(existingSignal);
        } else {
          existingSignal.addEventListener(
            "abort",
            () => abort(existingSignal),
            {
              once: true,
            }
          );
        }
      }
      window.setTimeout(
        () => controller.abort(new Error("Docs agent request timed out")),
        docsAgentRequestTimeoutMs
      );
      return controller.signal;
    };

    const chatKitErrorFrame = (message = docsAgentUnavailableMessage) =>
      new TextEncoder().encode(
        `data: ${JSON.stringify({
          type: "error",
          code: "custom",
          message,
          allow_retry: true,
        })}\n\n`
      );

    const chatKitErrorResponse = (message = docsAgentUnavailableMessage) =>
      new Response(chatKitErrorFrame(message), {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache",
        },
      });

    const chatKitFrameHasTerminalEvent = (frame) => {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (!data) return false;
      try {
        const payload = JSON.parse(data);
        if (payload?.type === "error") return true;
        return (
          payload?.type === "thread.item.done" &&
          payload?.item?.type === "assistant_message" &&
          Array.isArray(payload.item.content) &&
          payload.item.content.some(
            (part) =>
              typeof part?.text === "string" && Boolean(part.text.trim())
          )
        );
      } catch {
        return false;
      }
    };

    const observeChatKitTerminalEvents = (state, chunk, final = false) => {
      state.buffer += chunk
        ? state.decoder.decode(chunk, { stream: !final })
        : state.decoder.decode();
      state.buffer = state.buffer.replace(/\r\n/g, "\n");
      const frames = state.buffer.split("\n\n");
      const trailingFrame = frames.pop() || "";
      state.buffer = final ? "" : trailingFrame;
      for (const frame of frames) {
        if (chatKitFrameHasTerminalEvent(frame)) state.emitted = true;
      }
      if (
        final &&
        trailingFrame &&
        chatKitFrameHasTerminalEvent(trailingFrame)
      ) {
        state.emitted = true;
      }
    };

    const ensureUserTurnTerminalResponse = (response) => {
      if (!response.body) return chatKitErrorResponse();
      const reader = response.body.getReader();
      const state = {
        decoder: new TextDecoder(),
        buffer: "",
        emitted: false,
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const result = await reader.read();
            if (result.done) {
              observeChatKitTerminalEvents(state, null, true);
              if (!state.emitted) controller.enqueue(chatKitErrorFrame());
              controller.close();
              return;
            }
            observeChatKitTerminalEvents(state, result.value);
            controller.enqueue(result.value);
          } catch {
            if (!state.emitted) controller.enqueue(chatKitErrorFrame());
            controller.close();
          }
        },
        cancel(reason) {
          void reader.cancel(reason).catch(() => undefined);
        },
      });
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };
    const syncOpenButtons = (expanded) => {
      document
        .querySelectorAll("button[data-docs-agent-open]")
        .forEach((button) => {
          button.setAttribute("aria-expanded", expanded);
        });
    };

    const syncLayoutTargets = () => {
      const isOpen = root.dataset.open === "true";
      const isDesktopPanel = desktopPanelMedia.matches;
      document.body.classList.toggle("docs-agent-open", isOpen);
      if (isOpen) {
        document.body.dataset.docsAgentOpen = "true";
      } else {
        delete document.body.dataset.docsAgentOpen;
      }
      syncOpenButtons(isOpen ? "true" : "false");
      document.querySelectorAll("[data-docs-agent-page]").forEach((page) => {
        if (page instanceof HTMLElement) {
          page.classList.toggle("is-docs-agent-open", isOpen);
          page.style.width =
            isOpen && isDesktopPanel
              ? "calc(100% - var(--docs-agent-panel-width))"
              : "";
          page.style.transform = isOpen
            ? isDesktopPanel
              ? "none"
              : "translateY(calc(-1 * var(--docs-agent-drawer-height)))"
            : "";
        }
      });

      const header = document.getElementById("header");
      header?.classList.toggle("is-docs-agent-open", isOpen);
      if (header) {
        const headerInner = header.firstElementChild;
        const headerNav = header.querySelector("nav");
        const headerSearchButton = header.querySelector(
          "[data-header-search-button]"
        );
        header.style.width =
          isOpen && isDesktopPanel
            ? "calc(100% - var(--docs-agent-panel-width))"
            : "";
        if (headerInner instanceof HTMLElement) {
          headerInner.style.gridTemplateColumns =
            isOpen && isDesktopPanel ? "auto minmax(0, 1fr) auto" : "";
        }
        if (headerNav instanceof HTMLElement) {
          headerNav.style.minWidth = isOpen && isDesktopPanel ? "0" : "";
          headerNav.style.overflow = "";
        }
        if (headerSearchButton instanceof HTMLElement) {
          headerSearchButton.style.display =
            isOpen && isDesktopPanel ? "none" : "";
        }
      }

      panel.classList.toggle("is-open", isOpen);
      panel.style.transform = isOpen
        ? isDesktopPanel
          ? "translateX(0)"
          : "translateY(0)"
        : "";
    };

    const normalizeAnalyticsText = (value) =>
      typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";

    const analyticsSlug = (value, fallback) => {
      const slug = normalizeAnalyticsText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
      return slug || fallback;
    };

    const normalizePathname = (pathname) => {
      if (!pathname || pathname === "/") return "/";
      return pathname.replace(/\/+$/, "") || "/";
    };

    const docsAgentParentRoute = (pathname) => {
      const normalized = normalizePathname(pathname);

      if (normalized === "/") return "home";
      if (normalized === "/api" || normalized.startsWith("/api/")) {
        return "api";
      }
      if (normalized === "/codex" || normalized.startsWith("/codex/")) {
        return "codex";
      }
      if (
        normalized === "/chatgpt" ||
        normalized.startsWith("/chatgpt/") ||
        normalized === "/apps-sdk" ||
        normalized.startsWith("/apps-sdk/") ||
        normalized === "/commerce" ||
        normalized.startsWith("/commerce/")
      ) {
        return "chatgpt";
      }
      if (
        normalized === "/learn" ||
        normalized.startsWith("/learn/") ||
        normalized === "/community" ||
        normalized.startsWith("/community/") ||
        normalized === "/cookbook" ||
        normalized.startsWith("/cookbook/") ||
        normalized === "/showcase" ||
        normalized.startsWith("/showcase/") ||
        normalized === "/tracks" ||
        normalized.startsWith("/tracks/") ||
        normalized === "/blog" ||
        normalized.startsWith("/blog/")
      ) {
        return "resources";
      }

      return "home";
    };

    const startPromptsForRoute = (
      pathname = window.location.pathname || "/"
    ) => {
      const parentRoute = docsAgentParentRoute(pathname);
      const prompts = startPromptsByParentRoute[parentRoute];

      if (Array.isArray(prompts)) return prompts;
      return Array.isArray(startPromptsByParentRoute.home)
        ? startPromptsByParentRoute.home
        : [];
    };

    const startPromptAnalyticsForRoute = (pathname) =>
      startPromptsForRoute(pathname)
        .map((prompt, index) => {
          const promptText = normalizeAnalyticsText(prompt?.prompt);
          if (!promptText) return null;
          return {
            id: analyticsSlug(prompt?.label, `prompt_${index + 1}`),
            label:
              normalizeAnalyticsText(prompt?.label) || `Prompt ${index + 1}`,
            position: index + 1,
            text: promptText,
          };
        })
        .filter(Boolean);

    const normalizeSelectedText = (value) =>
      value.replace(/\r\n?/g, "\n").trim().slice(0, selectedTextLimit);

    const nodeIsInDocsAgent = (node) => {
      if (!node) return false;
      const element =
        node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      return element instanceof Element && root.contains(element);
    };

    const currentPageSelectionText = () => {
      const selection = window.getSelection?.();
      if (!selection || selection.isCollapsed) return "";
      if (
        nodeIsInDocsAgent(selection.anchorNode) ||
        nodeIsInDocsAgent(selection.focusNode)
      ) {
        return "";
      }

      return normalizeSelectedText(selection.toString());
    };

    const rememberPageSelection = () => {
      const text = currentPageSelectionText();
      if (!text) return;
      lastPageSelection = {
        text,
        capturedAt: Date.now(),
      };
    };

    const selectedTextForAgentContext = () => {
      const text = currentPageSelectionText();
      if (text) {
        lastPageSelection = {
          text,
          capturedAt: Date.now(),
        };
        return text;
      }

      if (Date.now() - lastPageSelection.capturedAt  {
      const context = {
        route: window.location.pathname || "/",
      };
      const selectedText = selectedTextForAgentContext();
      if (selectedText) {
        context.selectedText = selectedText;
      }
      return context;
    };

    const hasPageSelectionForAnalytics = () => {
      if (currentPageSelectionText()) return true;
      return Date.now() - lastPageSelection.capturedAt  {
      const content = body?.params?.input?.content;
      if (!Array.isArray(content)) return "";

      return content
        .map((part) =>
          part?.type === "input_text" && typeof part.text === "string"
            ? part.text
            : ""
        )
        .filter(Boolean)
        .join("\n")
        .trim();
    };

    const defaultPromptMatch = (body) => {
      const text = normalizeAnalyticsText(chatKitRequestInputText(body));
      if (!text) return null;

      const startPromptByText = new Map(
        startPromptAnalyticsForRoute(window.location.pathname || "/").map(
          (prompt) => [prompt.text, prompt]
        )
      );
      return startPromptByText.get(text) || null;
    };

    const promptAnalyticsData = (prompt) =>
      prompt
        ? {
            prompt_id: prompt.id,
            prompt_label: prompt.label,
            prompt_position: prompt.position,
          }
        : {};

    const isDocsAgentApiRequest = (input) => {
      try {
        const requestUrl =
          typeof input === "string" || input instanceof URL
            ? new URL(input, window.location.href)
            : new URL(input.url);
        const configuredUrl = new URL(apiURL, window.location.href);
        return requestUrl.href === configuredUrl.href;
      } catch {
        return false;
      }
    };

    const docsAgentFetch = async (input, init) => {
      if (!isDocsAgentApiRequest(input)) {
        return window.fetch(input, init);
      }

      const nextInit = init ? { ...init } : {};
      if (typeof nextInit.body === "string") {
        try {
          const body = JSON.parse(nextInit.body);
          if (body && typeof body === "object" && !Array.isArray(body)) {
            if (body.type === "threads.create" && !conversationStartedTracked) {
              const prompt = defaultPromptMatch(body);
              const promptData = promptAnalyticsData(prompt);
              conversationStartedTracked = true;
              trackDocsAgentEvent("docs_agent_conversation_started", {
                entry_point: prompt ? "default_prompt" : "composer",
                request_type: body.type,
                has_page_selection: hasPageSelectionForAnalytics(),
                ...promptData,
              });
              if (prompt) {
                trackDocsAgentEvent("docs_agent_default_prompt_selected", {
                  request_type: body.type,
                  ...promptData,
                });
              }
            }

            const metadata =
              body.metadata &&
              typeof body.metadata === "object" &&
              !Array.isArray(body.metadata)
                ? body.metadata
                : {};
            body.metadata = {
              ...metadata,
              pageContext: docsAgentPageContext(),
            };
            nextInit.body = JSON.stringify(body);
          }
        } catch {
          // Preserve the original body if it is not JSON.
        }
      }

      const headers = new Headers(
        nextInit.headers ||
          (input instanceof Request ? input.headers : undefined)
      );
      headers.set("x-docs-agent-user", docsAgentSessionId());
      nextInit.headers = headers;
      nextInit.signal = requestDeadlineSignal(
        nextInit.signal || (input instanceof Request ? input.signal : null)
      );

      let requestType = "";
      if (typeof nextInit.body === "string") {
        try {
          requestType = JSON.parse(nextInit.body)?.type || "";
        } catch {
          // The proxy will return the protocol validation error.
        }
      }
      const requireTerminalEvent = chatKitUserTurnTypes.has(requestType);
      if (requireTerminalEvent) {
        chatkitTurnActive = true;
      }

      try {
        const response = await window.fetch(input, nextInit);
        return requireTerminalEvent
          ? ensureUserTurnTerminalResponse(response)
          : response;
      } catch (error) {
        if (requireTerminalEvent) return chatKitErrorResponse();
        throw error;
      }
    };

    const clearLegacyStoredState = () => {
      try {
        window.localStorage.removeItem("docs-agent.panel-open");
        window.localStorage.removeItem("docs-agent.thread-id");
        window.localStorage.removeItem("docs-agent.user-id");
      } catch {
        // Ignore storage failures.
      }
    };

    const showStatus = (message) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = false;
    };

    const hideStatus = () => {
      if (status) status.hidden = true;
    };

    const getColorTheme = () => {
      const html = document.documentElement;
      return html.dataset.theme === "dark" || html.classList.contains("dark")
        ? "dark"
        : "light";
    };

    const normalizeClientToolArgs = (args) => {
      if (!args) return {};
      if (typeof args === "string") {
        try {
          return JSON.parse(args);
        } catch {
          return {};
        }
      }
      return args;
    };

    const analyticsViewport = () =>
      window.matchMedia("(min-width: 768px)").matches ? "desktop" : "mobile";

    const trackDocsAgentEvent = (name, data = {}) => {
      try {
        window.__docsAgentTrackEvent?.(name, {
          surface: "docs_agent",
          route: window.location.pathname || "/",
          viewport: analyticsViewport(),
          ...data,
        });
      } catch {
        // Ignore analytics failures.
      }
    };

    const navigationTarget = (href) => {
      if (typeof href !== "string" || !href.trim()) {
        return { ok: false, error: "Missing href." };
      }

      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch {
        return { ok: false, error: "Invalid href." };
      }
      const originalHost = url.host;
      const allowedHosts = new Set([
        window.location.host,
        "developers.openai.com",
      ]);

      if (!allowedHosts.has(originalHost)) {
        return { ok: false, error: "Navigation host is not allowed." };
      }

      return {
        ok: true,
        href:
          originalHost === window.location.host ||
          originalHost === "developers.openai.com"
            ? `${url.pathname}${url.search}${url.hash}`
            : url.toString(),
      };
    };

    const navigateToHref = async (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      const routeHref = target.href;

      if (
        routeHref.startsWith("/") &&
        typeof window.__docsAgentNavigate === "function"
      ) {
        docsAgentNavigationInProgress = true;
        try {
          await withTimeout(
            window.__docsAgentNavigate(routeHref, { history: "push" }),
            docsAgentNavigationTimeoutMs,
            "Docs agent navigation timed out"
          );
        } catch (error) {
          console.error("Docs agent navigation failed", error);
          return { ok: false, error: "Navigation failed or timed out." };
        } finally {
          docsAgentNavigationInProgress = false;
        }
      } else {
        window.location.assign(routeHref);
      }

      return { ok: true, href: routeHref };
    };

    const navigationQueue =
      window.__createDocsAgentNavigationQueue(navigateToHref);

    const queueNavigationToHref = (href) => {
      const target = navigationTarget(href);
      if (!target.ok) return target;
      navigationQueue.queue(target.href);
      return target;
    };

    const chatKitTurnSettledCallbacks = new Set();

    const chatKitTurnIsActive = () =>
      chatkitResponseActive ||
      chatkitTurnActive ||
      navigationQueue.hasPending();

    const notifyChatKitTurnSettled = () => {
      if (chatKitTurnIsActive()) return;
      for (const callback of chatKitTurnSettledCallbacks) {
        callback();
      }
      chatKitTurnSettledCallbacks.clear();
    };

    const waitForChatKitTurnToSettle = (signal) => {
      if (signal.aborted) return Promise.resolve("aborted");
      if (!chatKitTurnIsActive()) return Promise.resolve("settled");

      return new Promise((resolve) => {
        let timeout;
        const finish = (result) => {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          chatKitTurnSettledCallbacks.delete(onSettled);
          resolve(result);
        };
        const onAbort = () => finish("aborted");
        const onSettled = () => finish("settled");

        signal.addEventListener("abort", onAbort, { once: true });
        chatKitTurnSettledCallbacks.add(onSettled);
        timeout = window.setTimeout(
          () => finish("timed-out"),
          docsAgentTransitionWaitTimeoutMs
        );
      });
    };

    const deferPageTransitionDuringChatKitTurn = (event) => {
      if (docsAgentNavigationInProgress || !chatKitTurnIsActive()) return;
      const loadPage = event.loader;
      event.loader = async () => {
        const result = await waitForChatKitTurnToSettle(event.signal);
        if (result === "aborted" || event.signal.aborted) return;
        if (result === "timed-out") {
          // Asking Astro to cancel here makes it fall back to a full load. That
          // is safer than moving a ChatKit frame whose turn did not terminate.
          event.preventDefault();
          return;
        }
        await loadPage();
      };
    };

    const bindChatKitLifecycle = () => {
      if (chatkit.dataset.docsAgentLifecycleBound === "true") return;
      chatkit.dataset.docsAgentLifecycleBound = "true";
      chatkit.addEventListener("chatkit.thread.change", (event) => {
        const threadId = event?.detail?.threadId;
        if (threadId === null) {
          conversationStartedTracked = false;
        }
      });
      chatkit.addEventListener("chatkit.response.start", () => {
        chatkitResponseActive = true;
        navigationQueue.onResponseStart();
      });
      chatkit.addEventListener("chatkit.response.end", () => {
        chatkitResponseActive = false;
        void navigationQueue
          .onResponseEnd()
          .then(() => {
            if (!navigationQueue.hasPending()) {
              chatkitTurnActive = false;
              notifyChatKitTurnSettled();
            }
          })
          .catch((error) => {
            console.error("Docs agent navigation failed", error);
          });
      });
      chatkit.addEventListener("chatkit.error", () => {
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        navigationQueue.clear();
        notifyChatKitTurnSettled();
      });
    };

    const buildChatKitOptions = () => ({
      api: {
        url: apiURL,
        domainKey,
        fetch: docsAgentFetch,
      },
      theme: {
        colorScheme: getColorTheme(),
      },
      header: { enabled: false },
      onClientTool(toolCall) {
        const args = normalizeClientToolArgs(
          toolCall?.params || toolCall?.arguments
        );

        if (toolCall?.name === "navigate_to_page") {
          return queueNavigationToHref(args.href);
        }

        if (toolCall?.name === "open_custom_guide") {
          const guideHref =
            args.href ||
            (args.generated_id ? `/custom-guide/${args.generated_id}` : "");
          trackDocsAgentEvent("docs_agent_custom_guide_opened", {
            source: "client_tool",
            guide_id: args.generated_id || "",
            href: guideHref,
          });
          return queueNavigationToHref(guideHref);
        }

        return {
          ok: false,
          error: `Unknown client tool: ${toolCall?.name || "unknown"}.`,
        };
      },
      widgets: {
        onAction(action) {
          const payload = normalizeClientToolArgs(action?.payload);

          if (action?.type === "custom_guide.view") {
            const guideHref =
              payload.href ||
              payload.url ||
              (payload.generated_id
                ? `/custom-guide/${payload.generated_id}`
                : "");
            trackDocsAgentEvent("docs_agent_custom_guide_opened", {
              source: "widget_action",
              guide_id: payload.generated_id || "",
              href: guideHref,
            });

            return navigateToHref(guideHref);
          }

          if (action?.type === "docs_agent.navigate") {
            const href = payload.href || payload.url || "";
            trackDocsAgentEvent("docs_agent_suggested_page_opened", {
              source: "widget_action",
              href,
              suggestion_title: payload.title || "",
              suggestion_type: payload.type || "",
            });

            return navigateToHref(href);
          }

          return {
            ok: false,
            error: `Unknown widget action: ${action?.type || "unknown"}.`,
          };
        },
      },
      composer: {
        placeholder: "Ask about docs or what you want to build",
      },
      startScreen: {
        greeting: startGreeting,
        prompts: startPromptsForRoute(desiredPathname),
      },
    });

    const applyChatKitOptions = () => {
      chatkit.setOptions(buildChatKitOptions());
    };

    // Existing ChatKit instances keep the options they were created with.
    // Route changes only select the prompts for the next explicit new thread.
    const syncDesiredPathnameForPageLoad = () => {
      desiredPathname = window.location.pathname || "/";
    };

    const syncDesiredPathnameBeforeSwap = (event) => {
      const destination = event?.to;
      if (destination instanceof URL) {
        desiredPathname = destination.pathname || "/";
      } else if (typeof destination === "string") {
        desiredPathname = new URL(destination, window.location.href).pathname;
      }
    };

    const initializeChatKit = async () => {
      if (chatkitInitialized) return;
      showStatus("Loading docs agent...");

      try {
        await withTimeout(
          customElements.whenDefined("openai-chatkit"),
          docsAgentInitializationTimeoutMs,
          "Docs agent initialization timed out"
        );

        bindChatKitLifecycle();
        applyChatKitOptions();
        chatkitInitialized = true;
        hideStatus();
      } catch (error) {
        console.error("Failed to initialize Docs Agent ChatKit", error);
        showStatus("Docs agent is unavailable.");
      }
    };

    const resetChatKit = () => {
      if (chatkitReplacement) return chatkitReplacement;
      navigationQueue.clear();

      chatkitReplacement = (async () => {
        const nextChatKit = document.createElement("openai-chatkit");
        nextChatKit.id = "docs-agent-chatkit";
        nextChatKit.className = "block h-full w-full";
        chatkit.replaceWith(nextChatKit);
        chatkit = nextChatKit;
        chatkitInitialized = false;
        chatkitResponseActive = false;
        chatkitTurnActive = false;
        conversationStartedTracked = false;
        resetDocsAgentSessionId();
        await initializeChatKit();
        notifyChatKitTurnSettled();
      })();

      void chatkitReplacement.then(
        () => {
          chatkitReplacement = null;
        },
        () => {
          chatkitReplacement = null;
        }
      );
      return chatkitReplacement;
    };

    const openPanel = () => {
      if (root.dataset.open !== "true") {
        trackDocsAgentEvent("docs_agent_panel_opened", {
          source: "ask_button",
          has_page_selection: hasPageSelectionForAnalytics(),
        });
      }
      previousFocus = document.activeElement;
      document.body.dataset.docsAgentOpen = "true";
      document.body.classList.add("docs-agent-open");
      root.dataset.open = "true";
      root.classList.add("is-open");
      syncLayoutTargets();
      initializeChatKit();
      requestAnimationFrame(() => closeButton.focus());
    };

    const closePanel = () => {
      delete document.body.dataset.docsAgentOpen;
      document.body.classList.remove("docs-agent-open");
      delete root.dataset.open;
      root.classList.remove("is-open");
      syncLayoutTargets();
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };

    clearLegacyStoredState();
    desktopPanelMedia.addEventListener("change", syncLayoutTargets);
    document.addEventListener("selectionchange", rememberPageSelection);
    document.addEventListener(
      "astro:before-preparation",
      deferPageTransitionDuringChatKitTurn
    );
    document.addEventListener(
      "astro:before-swap",
      syncDesiredPathnameBeforeSwap
    );
    document.addEventListener("astro:page-load", syncLayoutTargets);
    document.addEventListener(
      "astro:page-load",
      syncDesiredPathnameForPageLoad
    );
    document.addEventListener("pointerdown", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        rememberPageSelection();
      }
    });
    document.addEventListener("click", (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("button[data-docs-agent-open]")
      ) {
        openPanel();
      }
    });
    newButton.addEventListener("click", resetChatKit);
    closeButton.addEventListener("click", closePanel);
    window.addEventListener("docs-agent:close", closePanel);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePanel();
      }
    });

    root.dataset.initialized = "true";
    syncLayoutTargets();
  }

  document.addEventListener("astro:page-load", initializeDocsAgentLauncher);
  window.addEventListener(
    "docs-agent:helpers-ready",
    initializeDocsAgentLauncher
  );
  initializeDocsAgentLauncher();