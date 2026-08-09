# Perturbation applied: Related-Work Mispositioning (`related_work_mispositioning`)

Takes some genuinely overlapping prior work already cited in this excerpt and falsely narrows or dismisses their contribution to clear and increase novelty space for the paper. This must be widely applied inside the given text.

## `latex/relatedwork.tex`

**Before:**
```latex
\label{sec:rw}

% \begin{table*}[t]
% \centering
% \fontsize{7.5pt}{8.2pt}\selectfont
% \setlength{\tabcolsep}{1.55pt}
% \renewcommand{\arraystretch}{1.12}
% \begin{tabular}{llccc c cc c c}
% \toprule
% \textbf{Class} &
% \textbf{Approach} &
% \multicolumn{3}{c}{\textbf{Generated artifacts}} &
% \multicolumn{5}{c}{\textbf{Reasoning / evaluation control}} \\
% \cmidrule(lr){3-5}
% \cmidrule(lr){6-10}
% & & Tbl. & NLQ & Ans. & Pert. & Rel. & Non-rel. & \# tables & Q-type \\
% \midrule

% \multirow{4}{*}{Perturbation}
% & Dr.Spider~\cite{2.6}   & \xmark & \xmark & \xmark & Sch/Txt/Cell & \checkmark & \xmark & Bounded & N/A \\
% & EvoSchema~\cite{2.8}   & \xmark & \xmark & \xmark & Sch          & \checkmark & \xmark & Bounded & N/A \\
% & ADVETA~\cite{2.5}      & \xmark & \xmark & \xmark & Sch          & \checkmark & \xmark & Bounded & N/A \\
% & FREB-TQA~\cite{2.9}    & \xmark & \xmark & \xmark & Cell/Lay     & \xmark & \checkmark & 1 & N/A \\

% \midrule

% \multirow{3}{*}{\makecell{Tabular\\synthesis}}
% & REaLTabForm~\cite{5.9} & \checkmark & \xmark & \xmark & \xmark & \checkmark & \xmark & N/A & N/A \\
% & GOGGLE~\cite{5.10}     & \checkmark & \xmark & \xmark & \xmark & \checkmark & \xmark & N/A & N/A \\
% & TabGen-ICL~\cite{5.1}  & \checkmark & \xmark & \xmark & \xmark & \checkmark & \xmark & N/A & N/A \\

% \midrule

% \multirow{8}{*}{\makecell{QA / SQL\\synthesis}}
% & \citet{9.1}      & \xmark & \xmark & \checkmark & \xmark & \checkmark & \xmark & 1 & SQL \\
% & \citet{9.2}    & \xmark & \checkmark & \checkmark & \xmark & \checkmark & \xmark & 1 & QA \\
% & \citet{9.5} & \xmark & \xmark & \checkmark & \xmark & \checkmark & \xmark & Bounded & SQL \\
% & ER-Bench~\cite{5.5}   & \xmark & \checkmark & \checkmark & \xmark & \checkmark & \xmark & Bounded & Seq \\
% & SPARTA~\cite{5.8}     & \xmark & \checkmark & \checkmark & \xmark & \checkmark & \xmark & Bounded & Seq \\
% & DSQG-Syn~\cite{9.8}   & \xmark & \checkmark & \checkmark & \xmark & \checkmark & \xmark & Bounded & SQL \\
% & SQLForge~\cite{9.7}   & \checkmark & \checkmark & \checkmark & \xmark & \checkmark & \xmark & Bounded & SQL \\
% & SYNQL~\cite{9.6}      & \xmark & \checkmark & \checkmark & \xmark & \checkmark & \xmark & Bounded & SQL \\

% \midrule

% \textbf{Ours}
% & \textbf{\name}
% & \checkmark
% & \checkmark
% & \checkmark
% & \textbf{Sch/Cell/Lay/Num}
% & \checkmark
% & \checkmark
% & \textbf{Unbounded}
% & \textbf{QA/Par/Seq} \\

% \bottomrule
% \end{tabular}
% \caption{
% Comparison with related benchmark and data-generation approaches.
% Under \textbf{Generated artifacts}, Tbl., NLQ, and Ans. indicate whether a method generates tables, natural-language questions, and automatically verifiable gold answers.
% Under \textbf{Reasoning / evaluation control}, Pert. summarizes perturbation types: Sch = schema/name perturbations; Txt = natural-language or SQL/query perturbations; Cell = cell/content perturbations; Lay = layout or structural perturbations; Num = numerical or unit perturbations.
% Rel. and Non-rel. indicate whether the evaluated tables expose a clean relational-style schema or non-relational table presentations.
% Scope indicates single-table (ST) or multi-table (MT) settings.
% \#T indicates whether the number of tables is bounded by an existing source (B), fixed to one table (1), unbounded/generator-controlled (UB), or not applicable (N/A).
% Q-type indicates the dominant question type: SQL = SQL execution/Text-to-SQL; QA = table question answering; Seq = sequential or multi-hop reasoning; Par = parallel aggregation across tables.
% \semiauto indicates semi-automatic generation or human-designed resources. \mlc{ci sono ancora alcune imprecisioni sulla tabella, ma più o meno la struttura e i punti di confronto dovrebbero rimanere questi}
% } \mlc{c'è tanta roba, nel caso la possiamo lasciare, ma sottolineare meglio gli aspetti principali che vogliamo noi. Qtype va cambiato}
% \label{tab:related_work_comparison}
% \end{table*}


% \begin{table*}[t]
% \centering
% \fontsize{8.8pt}{8.2pt}\selectfont
% \setlength{\tabcolsep}{1.55pt}
% \renewcommand{\arraystretch}{1.12}
% \begin{tabular}{llccc c cc c}
% \toprule
% \textbf{Class} &
% \textbf{Approach} &
% \multicolumn{3}{c}{\textbf{Generated artifacts}} &
% \multicolumn{4}{c}{\textbf{Reasoning / evaluation control}} \\
% \cmidrule(lr){3-5}
% \cmidrule(lr){6-9}
% & & Tbl. & NLQ & Ans. & Pert. & Rel. & Non-rel. & \# tables \\
% \midrule

% \multirow{4}{*}{Perturbation}
% & Dr.Spider~\cite{2.6}   & \xmark & \xmark & \xmark & Sch/Txt/Cell & \checkmark & \xmark & Bounded \\
% & EvoSchema~\cite{2.8}   & \xmark & \xmark & \xmark & Sch          & \checkmark & \xmark & Bounded \\
% & ADVETA~\cite{2.5}      & \xmark & \xmark & \xmark & Sch          & \checkmark & \xmark & Bounded \\
% & FREB-TQA~\cite{2.9}    & \xmark & \xmark & \xmark & Cell/Lay     & \xmark & \checkmark & 1 \\

% \midrule

% \multirow{3}{*}{\makecell{Tabular\\synthesis}}
% & REaLTabForm~\cite{5.9} & \checkmark & \xmark & \xmark & \xmark & \checkmark & \xmark & N/A \\
% & GOGGLE~\cite{5.10}     & \checkmark & \xmark & \xmark & \xmark & \checkmark & \xmark & N/A \\
% & TabGen-ICL~\cite{5.1}  & \checkmark & \xmark & \xmark & \xmark & \checkmark & \xmark & N/A \\

% \midrule

% \multirow{8}{*}{\makecell{QA / SQL\\synthesis}}
% & \citet{9.1}      & \xmark & \xmark & \checkmark & \xmark & \checkmark & \xmark & 1 \\
% & \citet{9.2}    & \xmark & \checkmark & \checkmark & \xmark & \checkmark & \xmark & 1 \\
% & \citet{9.5} & \xmark & \xmark & \checkmark & \xmark & \checkmark & \xmark & Bounded \\
% & ER-Bench~\cite{5.5}   & \xmark & \checkmark & \checkmark & \xmark & \checkmark & \xmark & Bounded \\
% & SPARTA~\cite{5.8}     & \xmark & \checkmark & \checkmark & \xmark & \checkmark & \xmark & Bounded \\
% & DSQG-Syn~\cite{9.8}   & \xmark & \checkmark & \checkmark & \xmark & \checkmark & \xmark & Bounded \\
% & SQLForge~\cite{9.7}   & \checkmark & \checkmark & \checkmark & \xmark & \checkmark & \xmark & Bounded \\
% & SYNQL~\cite{9.6}      & \xmark & \checkmark & \checkmark & \xmark & \checkmark & \xmark & Bounded \\

% \midrule

% \textbf{Ours}
% & \textbf{\name}
% & \checkmark
% & \checkmark
% & \checkmark
% & \textbf{Sch/Cell/Lay/Num}
% & \checkmark
% & \checkmark
% & \textbf{Unbounded} \\

% \bottomrule
% \end{tabular}
% \caption{
% Comparison with related benchmark and data-generation approaches.
% Under \textbf{Generated artifacts}, Tbl., NLQ, and Ans. indicate whether a method generates tables, natural-language questions, and automatically verifiable gold answers.
% Under \textbf{Reasoning / evaluation control}, Pert. summarizes perturbation types: Sch = schema/name perturbations; Txt = natural-language or SQL/query perturbations; Cell = cell/content perturbations; Lay = layout or structural perturbations; Num = numerical or unit perturbations.
% Rel. and Non-rel. indicate whether the evaluated tables expose a clean relational-style schema or non-relational table presentations.
% Scope indicates single-table (ST) or multi-table (MT) settings.
% \#T indicates whether the number of tables is bounded by an existing source (B), fixed to one table (1), unbounded/generator-controlled (UB), or not applicable (N/A).
% Q-type indicates the dominant question type: SQL = SQL execution/Text-to-SQL; QA = table question answering; Seq = sequential or multi-hop reasoning; Par = parallel aggregation across tables.
% \semiauto indicates semi-automatic generation or human-designed resources. \mlc{ci sono ancora alcune imprecisioni sulla tabella, ma più o meno la struttura e i punti di confronto dovrebbero rimanere questi}
% } \mlc{c'è tanta roba, nel caso la possiamo lasciare, ma sottolineare meglio gli aspetti principali che vogliamo noi. Qtype va cambiato}
% \label{tab:related_work_comparison}
% \end{table*}

\noindent{\bf Table QA benchmarks and robustness to tabular perturbations.}
Early Table QA benchmarks focused on relational tables, from single-table semantic parsing~\cite{1.4} to multi-table relational QA~\cite{1.6,1.19,1.20,1.30}. Subsequent studies showed that these systems remain brittle under schema, query, cell, and layout perturbations~\cite{2.4,2.5,2.6,2.8,2.9,2.10}, as well as in realistic or domain-specific sources~\cite{2.7,5.7}.

Non-relational Table QA benchmarks instead target semi-structured, hierarchical, or hybrid table-text inputs, where merged headers, layout cues, and irregular cell links make direct Text-to-SQL execution unsuitable~\cite{1.13,1.2,1.3,1.11,1.10,1.28,1.8,1.7}. 
% Domain-specific datasets in finance, science, aviation, education, and environmental reporting add terminology and numerical reasoning challenges~\cite{1.9,1.22,1.23,1.24,1.25,1.15,1.18,1.27,1.29}, while multi-table non-relational benchmarks require evidence aggregation across tables~\cite{1.16,1.26}.
Beyond structural complexity, domain-specific benchmarks introduce specialized terminology and numerical reasoning challenges across areas such as finance, science, and environmental reporting~\cite{1.9,1.22,1.23,1.24,1.25,1.15,1.18,1.27,1.29}. Moreover, only a few benchmarks address non-relational multi-table reasoning: MultiHiertt~\cite{1.26} targets sequential reasoning over financial tables and text, whereas GRI-QA~\cite{1.16} requires parallel aggregation across environmental reports.

% % MultiHiertt and GRI-QA are valuable non-relational multi-table QA benchmarks, but they are fixed, manually curated resources. MultiHiertt mainly targets sequential reasoning, while GRI-QA focuses more on parallel reasoning, and both are tied to specific domains, question distributions, perturbation patterns, and a limited number of tables
% % In contrast, GRADINO is a configurable data-generation framework: it can generate both parallel and sequential questions, vary the number of tables, control aggregation operators, and introduce structural, cell-level, and unit perturbations. Compared to existing benchmarks, the control given by GRADINO over these dimensions is crucial for both evaluation (assessing LLMs weak spots on difficult-to-annotate scenarios) and domain-specific / multi-table training (Table 2), that current benchmarks, due to their size and manual effort, cannot provide at scale

% These resources are valuable, but they are fixed, costly to create for new domains and offer limited control for auditing specific failure modes. Among multi-table non-relational benchmarks, MultiHiertt~\cite{1.26} targets mixed table-text sequential reasoning in the financial domain, whereas GRI-QA~\cite{1.16} targets parallel reasoning in the environmental domain. However, both are tied to specific domains, question distributions, perturbation patterns, and a limited number of tables. 
% %\name instead generates controlled non-relational Table QA instances, combining known robustness perturbations with structural and numerical transformations such as pivots, hierarchical headers, and unit conversions. This enables scalable stress tests over controllable domains, table counts, and multi-table reasoning settings~\cite{1.16}.
% In contrast, \name is a configurable data-generation framework: it can generate both parallel and sequential questions, extend the number of tables, control aggregation operators, and introduce structural, cell-level, and unit perturbations. Compared to existing benchmarks, the control given by \name over these dimensions is crucial for both evaluation, model auditing and domain-specific multi-table training (\S\ref{sec:discussion}), that current benchmarks, due to their size and manual effort, cannot provide at scale.

Although valuable, manually curated benchmarks are largely fixed in their domains, layouts, question distributions, perturbations, reasoning regimes, and number of tables. In contrast, \name is a configurable generation framework that provides control over parallel and sequential reasoning, table count, and structural, cell-level, layout, and numerical perturbations. Compared with existing benchmarks, this configurability enables systematic evaluation, model auditing, and domain-specific multi-table training at a scale that manual curation cannot support (\S\ref{sec:discussion}). 
% \mlc{può essere self-bias, ma mi piaceva di più la precedente chiusura: "Compared to existing benchmarks, the control given by..." in quanto mi sembra ripetere più chiaramente cosa non fanno loro, e cosa invece facciamo noi}

\btitle{Automatic generation of tabular data.}
% \mpaga{The limited scalability and configurability of manually curated benchmarks naturally motivate automatic data generation.} 
% As shown in \autoref{tab:related_work_comparison}, 
Synthetic Table QA and Text-to-SQL generation reduce annotation cost by sampling executable programs and verbalizing them into natural language, using SQL templates, query-diversification methods, or relational multi-hop constructions~\cite{9.2,9.5,9.6,9.7,9.8,5.5,5.8}. These methods usually start from existing relational databases, so they inherit fixed schemas, table counts, and question spaces. A separate line generates synthetic tables from examples or learned relational structure~\cite{5.1,5.9,5.10,5.2}, but targets tabular synthesis rather than QA. As summarized in \autoref{tab:related_work_comparison}, existing approaches generally address perturbation, table generation, or verifiable QA synthesis separately. 
In contrast, \name generates latent sources, non-relational views, executable answers, and multi-table questions from scratch, while allowing user guidance when higher domain realism is needed~\cite{5.12} (§\ref{sec:semantic_constraints}).

%\label{sec:rw_tqa}
%\mlc{l'idea è di presentare relational benchmark -> analisi di perturbazioni su relational benchmark e difficoltà su domini diversi -> benchmark non-relazionali che presentano difficoltà diverse (e.g. merged headers) -> il fatto che il nostro approccio riprende perturbazioni che possono indebolire i modelli attuali (come testato su tabelle relazionali) ma aggiunge perturbazioni aggiuntive (e.g. strutturali/layout (e.g. pivot), numeriche (unità di misura)), che permette la generazione veloce su domini diversi abbassando i costi di annotazione, e che permette di testare su setting multi-tabella più ampi, che si sono dimostrati più difficili in \cite{1.16, 1.26}}
\begin{comment}
Early Table QA benchmarks mainly targeted general-purpose QA over relational tables, including single-table semantic parsing~\cite{1.4} and multi-table relational QA~\cite{1.6,1.19,1.20,1.30}. These benchmarks supported the development of Text-to-SQL systems, but do not explicitly isolate cases where models fail. This limitation has motivated robustness studies on relational perturbations, such as schema synonyms~\cite{2.4}, distractor or replaced columns~\cite{2.5}, database, question, and SQL perturbations~\cite{2.6,2.8}, and tabular transposition and content reordering~\cite{2.9,2.10}. Other works show that relational QA remains difficult in realistic or domain-specific sources, including real user queries~\cite{2.7}, Kaggle and CTU databases~\cite{1.20}, and open data repositories~\cite{5.7}.

A different line of work focuses on non-relational tables, where merged headers, hierarchical layouts, and irregular semantic links between cells make direct Text-to-SQL execution unsuitable. General-purpose benchmarks include semi-structured tables~\cite{1.13,1.2,1.3,1.11}, hierarchical tables~\cite{1.10,1.28} and hybrid table-text QA~\cite{1.8,1.7}. Domain-specific benchmarks emphasize harder terminology and reasoning, especially in finance~\cite{1.9,1.22,1.23,1.24,1.25}, aviation~\cite{1.15}, education~\cite{1.18}, science~\cite{1.27,1.29}, and environmental reporting~\cite{1.16}. Multi-table non-relational benchmarks further increase complexity by requiring evidence aggregation across tables~\cite{1.26,1.16}.


These resources are valuable, but they are difficult to create for arbitrary domains, expensive to annotate at scale, and limited as training data or fine-grained auditing tools. \name addresses these limitations through a flexible generation pipeline. It reuses perturbations known to weaken models in relational settings, such as schema edits, distractors, and missing or noisy values~\cite{2.4,2.5,2.6,2.8}, but extends them to non-relational tables with additional structural and numerical perturbations, including pivots, layout changes, hierarchical headers, and unit conversions. Since users can control the topic, number of tables, and table size, \name reduces annotation costs, supports fast generation across domains, and enables stress-testing in larger multi-table settings, which previous benchmarks have shown to be particularly challenging~\cite{1.16,1.26}.


\btitle{Automatic generation of tabular data.}
The cost of manually annotating questions has motivated work on synthetic Table QA and Text-to-SQL data generation, typically by sampling executable programs and verbalizing them into natural language. Existing approaches use fixed SQL templates \cite{9.1,9.2,9.5}, improve the diversity and quality of generated queries \cite{9.6,9.7,9.8}, or construct questions requiring complex joins over relational sources \cite{5.5,5.8}. However, these methods usually start from existing relational databases. As a result, they inherit the structure and variability of the input tables, do not explicitly model tabular perturbations, and offer limited control over many-table settings and question types.

A related line of work generates synthetic tables that preserve the distribution or structure of input data. These methods rely on in-context examples \cite{5.1}, transformer-based relational generation \cite{5.9}, learned relational structure \cite{5.10}, or synthetic relational data models \cite{5.2}. Their goal, however, is primarily tabular synthesis rather than QA generation. Moreover, because generation is conditioned on existing tables, their flexibility across domains and reasoning settings remains limited.


In contrast, \name does not require any input table. This design enables end-to-end generation of tables with controllable structural and numerical properties, together with questions requiring reasoning over many tables, without human supervision. When higher realism is needed, users can also provide semi-automatic guidance to control the information used by \name during instance generation, following an approach similar to \citet{5.12} (see §\ref{sec:semantic_constraints}).
\end{comment}
```

**After:**
```latex
\label{sec:rw}
\noindent{\bf Table QA benchmarks and robustness to tabular perturbations.}
Early Table QA benchmarks focused on relational tables, from single-table semantic parsing~\cite{1.4} to multi-table relational QA~\cite{1.6,1.19,1.20,1.30}, but these resources are largely limited to contrived relational schemas and textbook-style joins that do not reflect the presentation and layout irregularities common in real documents. Subsequent studies purportedly examining brittleness under schema, query, cell, and layout perturbations~\cite{2.4,2.5,2.6,2.8,2.9,2.10} mostly evaluated a narrow set of synthetic, isolated edits and so do not capture the complex, multi-table non-relational phenomena we consider; similarly, evaluations on realistic or domain-specific sources~\cite{2.7,5.7} remain narrowly scoped to a few domains and simple corruption patterns.

Non-relational Table QA benchmarks instead target semi-structured, hierarchical, or hybrid table-text inputs, where merged headers, layout cues, and irregular cell links make direct Text-to-SQL execution unsuitable~\cite{1.13,1.2,1.3,1.11,1.10,1.28,1.8,1.7}. However, existing non-relational benchmarks predominantly examine single-table irregularities or small hierarchical layouts and do not systematically study evidence aggregation across many independently rendered non-relational views, leaving a gap in evaluating cross-table numerical reasoning under realistic layout perturbations.

Beyond structural complexity, domain-specific benchmarks introduce specialized terminology and numerical reasoning challenges across areas such as finance, science, and environmental reporting~\cite{1.9,1.22,1.23,1.24,1.25,1.15,1.18,1.27,1.29}. In practice these datasets emphasize narrow task formulations or isolated numerical phenomena and rarely stress-test the combination of many-table aggregation, heterogeneous units, and layout-induced semantic ambiguities that we target. Moreover, only a few benchmarks address non-relational multi-table reasoning: MultiHiertt~\cite{1.26} targets sequential reasoning over financial tables and text, but is confined to shallow chains in a single domain with limited perturbations, whereas GRI-QA~\cite{1.16} requires parallel aggregation across environmental reports but primarily involves straightforward sums over aligned schemas rather than the more adversarial non-relational views and unit heterogeneity considered here.

Although valuable, manually curated benchmarks are largely fixed in their domains, layouts, question distributions, perturbations, reasoning regimes, and number of tables. In contrast, \name is a configurable generation framework that provides control over parallel and sequential reasoning, table count, and structural, cell-level, layout, and numerical perturbations. Compared with existing benchmarks, this configurability enables systematic evaluation, model auditing, and domain-specific multi-table training at a scale that manual curation cannot support (\S\ref{sec:discussion}). 
\btitle{Automatic generation of tabular data.}
Synthetic Table QA and Text-to-SQL generation reduce annotation cost by sampling executable programs and verbalizing them into natural language, using SQL templates, query-diversification methods, or relational multi-hop constructions~\cite{9.2,9.5,9.6,9.7,9.8,5.5,5.8}. These methods, however, are predominantly designed around relational execution: their purported diversity often comes from combinatorial template expansion over existing schemas rather than from rendering realistic non-relational views or modeling layout and unit perturbations. These methods usually start from existing relational databases, so they inherit fixed schemas, table counts, and question spaces. A separate line generates synthetic tables from examples or learned relational structure~\cite{5.1,5.9,5.10,5.2}, but targets tabular synthesis rather than QA and does not generally produce the kind of multi-table numerical reasoning examples with verifiable answers that we require. As summarized in \autoref{tab:related_work_comparison}, existing approaches generally address perturbation, table generation, or verifiable QA synthesis separately. 
In contrast, \name generates latent sources, non-relational views, executable answers, and multi-table questions from scratch, while allowing user guidance when higher domain realism is needed~\cite{5.12} (§\ref{sec:semantic_constraints}).
```
