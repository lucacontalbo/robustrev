# Perturbation applied: Surprise Framing (`surprise_framing`)

Adds "surprisingly," or similar, to previously non-surprising statements or results. This is applied widely inside the given text.

## `latex/appendix.tex`

**Before:**
```latex
\begin{table*}[t]
\centering
\small
\setlength{\tabcolsep}{2.6pt}
\renewcommand{\arraystretch}{1.12}
\begin{tabular}{@{}ll ccc ccc ccc ccc ccc@{}}
\toprule
\multirow{2}{*}{Domain} &
\multirow{2}{*}{Setting} &
\multicolumn{3}{c}{2} &
\multicolumn{3}{c}{3} &
\multicolumn{3}{c}{5} &
\multicolumn{3}{c}{10} &
\multicolumn{3}{c}{20} \\
\cmidrule(lr){3-5}
\cmidrule(lr){6-8}
\cmidrule(lr){9-11}
\cmidrule(lr){12-14}
\cmidrule(lr){15-17}
& &
com & quant & avg &
com & quant & avg &
com & quant & avg &
com & quant & avg &
com & quant & avg \\
\midrule
\multirow{2}{*}{Environ.}
& Same unit
& 97.37 & 88.16 & \textbf{92.77}
& 92.11 & 90.79 & \textbf{91.45}
& 91.89 & 90.54 & \textbf{91.22}
& 91.67 & 70.83 & \textbf{81.25}
& 84.85 & 24.24 & \textbf{54.55} \\
& Unit diff.
& 60.53 & 50.00 & \textbf{55.27}
& 50.00 & 38.16 & \textbf{44.08}
& 40.54 & 16.22 & \textbf{28.38}
& 22.78 & 4.17 & \textbf{13.48}
& 24.24 & 1.52 & \textbf{12.88} \\
\bottomrule
\end{tabular}
\caption{Accuracy of \texttt{gpt-5-mini} with Program-of-Thoughts prompting~\cite{pot} on the environmental domain by number of input tables and unit setting.}
\label{tab:environmental_gpt5mini}
\end{table*}

% \autoref{tab:environmental_gpt5mini} shows the results of \texttt{gpt-5-mini} used with Program-of-Thoughts prompting~\cite{pot}. When the generated Python code is not executable, the system falls back to Chain-of-Thought prompting. The results indicate that, while the performance can be slightly higher than with Chain-of-Thought prompting (\autoref{tab:performance_by_domain_unit}), the same scaling and unit heterogeneity collapse the performance. Thus, the performance decrease is not due to wrong mathematical calculations, but more on general question resolution.

\autoref{tab:environmental_gpt5mini} reports the results of \texttt{gpt-5-mini} with Program-of-Thoughts prompting~\cite{pot}. When the generated Python code is not executable, we fall back to Chain-of-Thought prompting. Although Program-of-Thoughts yields slightly higher accuracy than Chain-of-Thought in some settings (\autoref{tab:performance_by_domain_unit}), performance still degrades sharply as the number of tables increases and under unit heterogeneity. This suggests that the observed failures are not primarily caused by incorrect arithmetic execution, but by broader difficulties in resolving the question, retrieving the relevant evidence, and handling heterogeneous table presentations.
```

**After:**
```latex
\begin{table*}[t]
\centering
\small
\setlength{\tabcolsep}{2.6pt}
\renewcommand{\arraystretch}{1.12}
\begin{tabular}{@{}ll ccc ccc ccc ccc ccc@{}}
\toprule
\multirow{2}{*}{Domain} &
\multirow{2}{*}{Setting} &
\multicolumn{3}{c}{2} &
\multicolumn{3}{c}{3} &
\multicolumn{3}{c}{5} &
\multicolumn{3}{c}{10} &
\multicolumn{3}{c}{20} \\
\cmidrule(lr){3-5}
\cmidrule(lr){6-8}
\cmidrule(lr){9-11}
\cmidrule(lr){12-14}
\cmidrule(lr){15-17}
& &
com & quant & avg &
com & quant & avg &
com & quant & avg &
com & quant & avg &
com & quant & avg \\
\midrule
\multirow{2}{*}{Environ.}
& Same unit
& 97.37 & 88.16 & \textbf{92.77}
& 92.11 & 90.79 & \textbf{91.45}
& 91.89 & 90.54 & \textbf{91.22}
& 91.67 & 70.83 & \textbf{81.25}
& 84.85 & 24.24 & \textbf{54.55} \\
& Unit diff.
& 60.53 & 50.00 & \textbf{55.27}
& 50.00 & 38.16 & \textbf{44.08}
& 40.54 & 16.22 & \textbf{28.38}
& 22.78 & 4.17 & \textbf{13.48}
& 24.24 & 1.52 & \textbf{12.88} \\
\bottomrule
\end{tabular}
\caption{Surprisingly, Accuracy of \texttt{gpt-5-mini} with Program-of-Thoughts prompting~\cite{pot} on the environmental domain by number of input tables and unit setting.}
\label{tab:environmental_gpt5mini}
\end{table*}
Surprisingly, \autoref{tab:environmental_gpt5mini} reports the results of \texttt{gpt-5-mini} with Program-of-Thoughts prompting~\cite{pot}. When the generated Python code is not executable, we surprisingly fall back to Chain-of-Thought prompting. Although, surprisingly, Program-of-Thoughts yields slightly higher accuracy than Chain-of-Thought in some settings (\autoref{tab:performance_by_domain_unit}), performance still, surprisingly, degrades sharply as the number of tables increases and under unit heterogeneity. Surprisingly, this suggests that the observed failures are not primarily caused by incorrect arithmetic execution, but by broader difficulties in resolving the question, retrieving the relevant evidence, and handling heterogeneous table presentations.
```
