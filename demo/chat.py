"""Chat page — talk to the llmalchemy agent with live signal feedback."""

import streamlit as st
from fixtures import Base
from lmdk import AssistantMessage, UserMessage

from llmalchemy.agent import (
    MessageEvent,
    Output,
    Signal,
    SignalEvent,
    SystemInstructionEvent,
    run,
)

SIGNAL_LABELS = {
    Signal.COMPLETION: ":material/lightbulb: Thinking…",
    Signal.VALIDATION: ":material/approval: Validating code…",
    Signal.EXECUTION: ":material/bolt: Executing code…",
    Signal.EXCEEDED: ":material/warning: Loop limit reached",
}

AVATARS = {
    "user": ":material/person:",
    "assistant": ":material/robot_2:",
    "system": ":material/settings:",
}


def _render_and_log(kind: str, text: str) -> None:
    chat_log.append({"kind": kind, "text": text})
    st.chat_message(kind, avatar=AVATARS.get(kind)).markdown(text)


st.header(":material/chat: Chat")
chat_log: list[dict] = st.session_state.chat_log
session = st.session_state.session
messages = st.session_state.messages
model = st.session_state.model
tools = st.session_state.tools

for entry in chat_log:
    st.chat_message(entry["kind"], avatar=AVATARS.get(entry["kind"])).markdown(entry["text"])

if prompt := st.chat_input("Message the agent…"):
    _render_and_log("user", prompt)
    messages.append(UserMessage(prompt))

    status = st.empty()
    status.info(":material/lightbulb: Thinking…")

    for event in run(session=session, messages=messages, base=Base, model=model, tools=tools):
        match event:
            case SignalEvent(signal=signal):
                status.info(SIGNAL_LABELS[signal])

            case SystemInstructionEvent():
                st.session_state.system_instruction = event.content

            case MessageEvent(message=msg) if isinstance(msg, AssistantMessage):
                output = Output.model_validate_json(msg.content)
                md = output.message
                if output.code:
                    md += f"\n\n```python\n{output.code}\n```"
                status.empty()
                _render_and_log("assistant", md)
                status = st.empty()

            case MessageEvent(message=msg) if isinstance(msg, UserMessage):
                status.empty()
                _render_and_log("system", f"```\n{msg.content}\n```")
                status = st.empty()

    status.empty()
