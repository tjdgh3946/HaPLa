# 🧺 Harmful Prompt Laundering (HaPLa) — EMNLP 2025 Main

<!-- Badge row optional
<p align="center">
  <img src="./Assets/main_figure.png" height="392" alt="main_figure"/>
</p>
-->

> ⚠️ This repository requires **OpenAI API** for prompt construction. You must set an API key.

---

## Overview

`Hapla_prompt` builds a prompt by masking target words in a sentence using a chosen encoding schema (`ascii`, `equation`, `manchu`, `emoji`), then injects the masked text into a template.

It relies on:
- `mask_sensitive_words`: the unified masking function  
- `SCHEMA_TEMPLATE_MAP`: a dict mapping schema → template string with a `{case}` placeholder

---

## Installation & Setup

```bash
pip install -r requirements.txt
```

Set your OpenAI API key:

```bash
export OPENAI_API_KEY="sk-..."      # macOS/Linux
# or on Windows PowerShell
# $Env:OPENAI_API_KEY = "sk-..."
```
---

## Using `HaPLa_attack`

`HaPLa_attack` performs a two-step process to generate a toxic word-masking prompt:  
1. It creates a framing and toxic word probing prompt using the `framing_and_toxic_probing_template`.  
2. It parses the JSON output to extract the `declarative` sentence and `toxic_words`.

**Call `src/hapla.py` as follows:**

```python
from src.gen_util import OpenAIClient
from your_module import HaPLa_attack

query = "Teach me how to film porn using ..."  # Jailbreaking query 
prompt = HaPLa_attack(
    query,
    encoding_params={"reverse": False, "partial": True, "ratio": 0.8},  # Attack parameters
    client="gpt-4o"
)
print(prompt)
```

### Parameters

- **output** *(dict)*  
  - `declarative` *(str)*: The source sentence  
  - `toxic_words` *(Sequence[str] | str)*: Words/phrases to mask  
- **encoding_params** *(dict, optional)*  
  - `partial` *(bool, default False)*: Mask a contiguous portion as one group  
  - `random` *(bool, default False)*: Mask randomly chosen characters  
  - `reverse` *(bool, default False)*: Reverse the order of converted items inside brackets  
  - `ratio` *(float, default 1.0)*: The proportion to mask, clamped to `[0, 1]`  
  - `mask_from_start` *(bool, default False)*: When `partial=True`, choose from the start if `True`, otherwise from the end  
- **schema** *(str)*: One of `ascii`, `equation`, `manchu`, or `emoji`  
- **template** *(str, optional)*: Format string that must contain a `{case}` placeholder. Defaults to `SCHEMA_TEMPLATE_MAP[schema]`


## Default Encoding Parameters

```python
_DEFAULT_ENCODING_PARAMS = {
    "partial": False,
    "reverse": False,
    "random": False,
    "ratio": 1.0,
    "mask_from_start": False,
}
```

---

## Troubleshooting

- `ValueError: partial and random cannot both be True` → Choose only one mode  
- `KeyError: output must contain 'declarative' and 'toxic_words'` → Add both keys to `output`  
- `ValueError: Template must contain a '{case}' placeholder` → Fix your template  
- Invalid `ratio` values are automatically clamped to `[0, 1]`  
- `schema` must be one of `ascii | equation | manchu | emoji`

---

## Project Structure

```
src/
  hapla.py               # HaPLa prompt generator 
  symbolic_encoding.py   # mask_sensitive_words
  template.py            # ascii_template_vanilla, manchu_template, etc.
  gen_util.py            # OpenAIClient
Assets/
  main_figure.png
README.md
```

---

## Consider citing our paper
```
@misc{joo2025harmfulpromptlaunderingjailbreaking,
      title={Harmful Prompt Laundering: Jailbreaking LLMs with Abductive Styles and Symbolic Encoding}, 
      author={Seongho Joo and Hyukhun Koh and Kyomin Jung},
      year={2025},
      eprint={2509.10931},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2509.10931}, 
}
```
