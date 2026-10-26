# Qwen3 8B via Ollama (declarative text plugin)

**Status: manifest + template only — by design.** Text plugins are
the easy swap: this folder has no code. It declares an
OpenAI-compatible endpoint (`http://127.0.0.1:11434/v1`, Ollama),
the model name `qwen3:8b-q4_K_M`, an 8k context, JSON-mode support,
and the `narrate.jinja` prompt template.

TODO in core (not in this plugin): the generic OpenAI-compatible
text runner that reads manifests like this one and performs the
actual chat call has not been written yet. Until it lands, the
mock-echo plugin covers the text path in the demo and tests.
To use a different local server (LM Studio, llama.cpp), copy this
folder and change `endpoint` / `model` — nothing else.
