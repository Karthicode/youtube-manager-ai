# Judge: Helpfulness / Resolution (configure in Langfuse UI → Evaluators)

Model: any strong small model. Sampling: 100%.
Target: production traces named `chat-turn`.

## Prompt

You are grading a YouTube library assistant's answer for helpfulness.

User message: {{input}}
Assistant answer: {{output}}

Score 1 if the answer either (a) directly answers the question with concrete
results, or (b) asks ONE precise clarifying question that is genuinely needed.
Score 0 if it: answers a different question, asks for clarification that the
message already provided, claims inability without suggesting a next step, or
buries the answer in unnecessary options.

Respond with a score of 0 or 1 and a one-sentence reason.
