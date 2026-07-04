# Judge: Groundedness (configure in Langfuse UI → Evaluators)

Model: any strong small model (e.g. gpt-5-mini equivalent). Sampling: 100%.
Target: production traces named `chat-turn`.

## Prompt

You are grading a YouTube library assistant's answer for groundedness.

Trace input (user message): {{input}}
Assistant answer: {{output}}
Tool results available to the assistant (from the trace's tool spans): {{metadata}}

Score 1 if every specific video the answer mentions (titles, channels,
liked dates) appears in the tool results. Score 0 if the answer asserts any
video, title, channel, or date that is not present in tool results.
Clarifying questions and generic statements with no specific claims score 1.

Respond with a score of 0 or 1 and a one-sentence reason.
