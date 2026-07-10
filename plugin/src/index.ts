import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

const DIEGEN_MARK = "[DGEN] \u2705 \u901a\u8fc7\n";
const DIEGEN_RULE = `
## DGEN ⚡ 迭进预检规则（系统注入·不可跳过）

每次组织回复时执行迭进预检：
1. 执行迭进引擎预检: cd %CODEX_PLUGIN_DIR%/engine && uv run python call_diegin.py check
2. 解析 JSON 返回值
3. 如果匹配的拦截规则数(matched_interceptions) > 0 → 检查每条匹配规则的 action 字段
4. 如果 action 包含 "block_execution" → 回复开头输出: [DGEN] 拦截X | 规则: rule_id | 原因: reason
5. 如果无拦截 → 正常回复
`;

export default definePluginEntry({
  id: "dgen",
  name: "Diegin Pre-Check",
  register(api) {
    api.on("message_sending", (event) => {
      if (event.messages && Array.isArray(event.messages)) {
        for (const msg of event.messages) {
          if (msg.content && typeof msg.content === "string" && !msg.content.startsWith("[DGEN")) {
            msg.content = DIEGEN_MARK + msg.content;
          }
        }
      }
    });
    api.on("before_dispatch", (event) => {
      if (event.message?.content && typeof event.message.content === "string" && !event.message.content.startsWith("[DGEN")) {
        event.message.content = DIEGEN_MARK + event.message.content;
      }
    });
    api.on("tool_result_persist", (event) => {
      if (event.result?.content && typeof event.result.content === "string" && !event.result.content.startsWith("[DGEN")) {
        event.result.content = DIEGEN_MARK + event.result.content;
      }
    });
    api.on("before_agent_finalize", (event) => {
      if (event.finalAnswer && typeof event.finalAnswer === "string" && !event.finalAnswer.startsWith("[DGEN")) {
        event.finalAnswer = DIEGEN_MARK + event.finalAnswer;
      }
    });
    api.on("reply_dispatch", (event) => {
      if (event.message?.content && typeof event.message.content === "string" && !event.message.content.startsWith("[DGEN")) {
        event.message.content = DIEGEN_MARK + event.message.content;
      }
    });
    api.on("before_prompt_build", (event) => {
      if (event.promptAppend != null && typeof event.promptAppend === "object") {
        event.promptAppend.system = (event.promptAppend.system || "") + DIEGEN_RULE;
      }
    });
    api.on("subagent_spawning", (event) => {
      if (event.task && typeof event.task === "string" && !event.task.includes("迭进预检规则")) {
        event.task = event.task + DIEGEN_RULE;
      }
    });
    api.logger.info("[dgen] 8 hooks active");
  },
});