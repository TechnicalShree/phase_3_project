// LangGraph owns tools and approvals; the CLI only produces a JSON decision.
export default function (cmd) {
  cmd.on('session_start', () => cmd.setActiveTools([]));
  cmd.hooks({beforeToolCall: () => ({block: 'Tools are executed by LangGraph only.'})});
}
