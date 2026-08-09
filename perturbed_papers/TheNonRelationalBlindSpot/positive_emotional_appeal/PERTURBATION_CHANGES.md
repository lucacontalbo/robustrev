# Perturbation applied: Positive Emotional Appeal (`positive_emotional_appeal`)

Overstates what newly becomes possible because of the work. Use tone-sensitive language to convey enthusiasm and excitement about the new inflated possibilities. This is applied widely inside the given text.

## `latex/conclusions.tex`

**Before:**
```latex
% We introduced \name, a framework for generating automatically verifiable numerical QA benchmarks over multiple non-relational tables. 
% Our experiments show that recent LLMs remain brittle in this setting, and suffering large domain-dependent failures under heterogeneous units. Overall, we identify multi-table non-relational numerical reasoning as a persistent blind spot for current LLMs and provide a controlled benchmark-generation framework for studying it.

% We introduced \name, a framework for generating automatically verifiable numerical QA benchmarks over multiple non-relational tables. Our experiments identify multi-table non-relational numerical reasoning as a persistent blind spot for current LLMs, which degrade sharply as tables accumulate and suffer large domain-dependent failures under heterogeneous units.

We introduced \name, a framework for generating numerical QA benchmarks over multiple non-relational tables, giving controlled access to a setting that existing resources cannot vary. Using it, we identify multi-table non-relational numerical reasoning as a persistent blind spot for current LLMs, which degrade sharply as tables accumulate and with domain-dependent unit conventions. Moreover, we show that \name can generate useful data for LLM fine-tuning.
%and suffer large domain-dependent failures under heterogeneous units.
```

**After:**
```latex
We introduced \name, a framework for generating numerical QA benchmarks over multiple non-relational tables, providing unprecedented, finely controllable access to a setting that existing resources cannot meaningfully vary. Using it, we not only identify multi-table non-relational numerical reasoning as a persistent blind spot for current LLMs — which degrade sharply as tables accumulate and when domain-dependent unit conventions intervene — but also demonstrate a clear pathway toward dramatically improving model robustness. Enthusiastically, \name opens the door to systematically training, stress-testing, and iterating on models for the kinds of complex, heterogeneous table presentations found in real-world reports and spreadsheets, and can be used to synthesize large-scale, targeted curricula that have the potential to fast-track progress toward production-ready numerical understanding. Moreover, we show that \name can generate highly useful fine-tuning data that meaningfully boosts multi-table performance in our experiments, suggesting it is a practical and scalable tool for closing this important gap.
```
