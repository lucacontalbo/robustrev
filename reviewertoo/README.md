# ReviewerToo in robustrev

Runs [ReviewerToo](https://arxiv.org/abs/2510.08867) (Sahu et al., 2025) on
robustrev's papers, with gpt-oss-120b (served by vLLM) as the backbone of
every agent. Self-contained: nothing here imports or changes the rest of
robustrev.

| Path | What it is |
|---|---|
| `rtoo/` | The authors' code from their supplementary material, **unmodified** (minus the stale `__pycache__/`). |
| `run_reviewertoo.py` | Driver: same CLI, paper discovery, resumability and output layout as `robustrev.py review`. |
| `latex_compile.py` | Verbatim copy of robustrev's, so compilation doesn't depend on it. |
| `sbatch_review_reviewertoo.sh` | Slurm job: starts vLLM with gpt-oss-120b, then runs the driver. |
| `setup_reviewertoo.sh` | One-time setup (conda env + offline docling models). |
| `requirements.txt` | ReviewerToo's dependencies. |

## Pipeline

For each paper the driver calls ReviewerToo's own `main.process_single_paper()`:

1. PDF → markdown with ReviewerToo's docling converter (with its OCR
   engine fixed to RapidOCR on onnxruntime, what docling's automatic choice
   normally picks, so that it never needs to download other models);
2. 13 persona reviews (default, critical, permissive, theorist, empiricist,
   pragmatist, pedagogical, big_picture, reproducibility, bengio, hinton,
   lecun, pal);
3. one author rebuttal per review;
4. the 7-stage metareview (stance, key points, rebuttal analysis, fact
   extraction / verification / significance, final synthesis).

The LitLLM literature search is off: it needs live internet access
(Semantic Scholar, OpenAlex, arXiv, Serper) and API keys. About 33 LLM calls
per paper.

The driver runs offline: Hugging Face libraries are put in offline mode, and
any connection to a host other than localhost or `$VLLM_BASE_URL`'s fails at
once with `NoInternetError` (in that paper's `error.txt`). All docling models
come from `setup_reviewertoo.sh`.

## Outputs

Same place and layout as the other reviewers, with model id
`ReviewerToo-gpt-oss-120b`, e.g.
`tests/reviews/acl/ReviewerToo-gpt-oss-120b/<paper>/`:

- `review.json`: the rubric's field ids (acl or iclr).
  - ICLR `rating` = mean of the 13 persona ratings (out of 10).
  - ACL `overall_assessment` = that mean mapped as for the other native
    reviewers (1→1, 3→2, 5→3, 6→3.5, 8→4, 10→5).
  - Text fields list every persona's section.
  - ReviewerToo gives no sub-scores (soundness, confidence, …); they are
    `"N/A"`.
- `raw_response.txt`: the final metareview, including its
  `<final_decision>`.
- `reviewertoo/`: every intermediate output (markdown paper, config, persona
  reviews, rebuttals, metareview stages).
- `error.txt` if a run failed or came back incomplete. ReviewerToo saves
  failed LLM calls as error text and carries on, so any missing rating,
  rebuttal or final decision counts as a failure; a rerun redoes that paper.

## Running on Leonardo

1. On a login node, once:
   - download the weights:
     `huggingface-cli download openai/gpt-oss-120b --local-dir /leonardo_work/IscrB_ESG-NEXT/mcontalb/hf_models/gpt-oss-120b`
   - run `bash reviewertoo/setup_reviewertoo.sh`.
2. From the robustrev directory: `sbatch reviewertoo/sbatch_review_reviewertoo.sh`.

Manual run against an already running server:

```
VLLM_BASE_URL=http://127.0.0.1:<port>/v1 DOCLING_DEVICE=cpu \
    python reviewertoo/run_reviewertoo.py review ReviewerToo-gpt-oss-120b acl papers/
```
