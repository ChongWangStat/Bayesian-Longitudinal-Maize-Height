"""Build the double-anonymized Plant Phenomics special-issue submission source."""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "manuscript"
DEST = ROOT / "journal_submissions" / "plant_phenomics_special_issue_2026"
TEMPLATE = DEST / "template" / "elsarticle"
SUB = DEST / "submission_source"
FIG = SUB / "figures"

TITLE = (
    "Prior-guided image analysis for Bayesian longitudinal maize height "
    "phenotyping with fixed cameras"
)


PREAMBLE = r"""\documentclass[review,12pt,authoryear]{elsarticle}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[margin=1in]{geometry}
\usepackage{setspace}
\usepackage{graphicx}
\graphicspath{{./figures/}}
\usepackage{amsmath,amssymb}
\usepackage{booktabs,longtable,array}
\usepackage{lineno}
\usepackage[hidelinks]{hyperref}
\usepackage{microtype}
\usepackage{lastpage}
\usepackage{xcolor}
\input{numbers.tex}
\input{numbers_2024.tex}
\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}
\journal{Plant Phenomics}
"""


ABSTRACT = r"""Affordable longitudinal field phenotyping requires interpretable image measurements under overlap and changing camera geometry. We developed a Bayesian longitudinal method for fixed RGB cameras in which the state from earlier images guides association and candidate selection during each added image. A robust particle filter updates height, growth, and uncertainty from the available image prefix. The temporal validation was developed from 61 matched 2021 image--manual records in six camera rows and evaluated against 166 later-year manual heights from 34 new maize plants in four biological rows and six views. No 2024 manual outcome was used for fitting or tuning. Bayesian estimates reduced single-frame mean absolute error from 18.10 to 17.36 cm and root mean squared error from 23.54 to 22.41 cm; correlation increased from 0.813 to 0.847. A Gaussian filter with matched priors had mean absolute error 17.35 cm and root mean squared error 22.42 cm, effectively tying the particle estimate. The 0.74-cm gain over single frames had a biological-row cluster interval of -0.44 to 1.30 cm, indicating a modest, uncertain advantage. Transfer-aware 80%, 90%, and 95% intervals covered 78.9%, 90.4%, and 97.0% of manual heights. In controlled candidate ambiguity, placing the prior inside image analysis reduced root mean squared error from 8.61 to 6.01 cm relative to filtering preselected measurements. Released code and a browser application convert dated images into daily height trajectories with uncertainty."""


INTRODUCTION = r"""\section{Introduction}

Longitudinal plant height records growth rate, developmental timing, and environmental response more directly than a single mature measurement. Repeated manual measurement is labor intensive, whereas fixed red--green--blue cameras can observe the same field view at short intervals with modest hardware. Accessible phenotyping also requires reproducible calibration, clear uncertainty, and tools that plant scientists can run without rebuilding a computer-vision pipeline \cite{hoyosvillegas2025affordable}. These needs align with smart-agriculture systems that turn frequent, heterogeneous field observations into timely measurements.

Time-series phenotyping has recovered maize growth curves from ground and aerial imagery \cite{ge2016temporal,liang2018timeseries,wang2020functional,rodene2022uav}. In-scene scales can provide physical units \cite{mano2017precise,manoigawa2017nondestructive}, while stereo and structured systems can improve geometry at the cost of additional hardware or acquisition constraints \cite{cai2018stereo,tabb2019cass}. Other maize systems pool images, impose nondecreasing growth, or reuse early positions to guide later segmentation \cite{guo2021kat4ia,guo2023sscnn,gao2022individual,li2023multisource}. These studies show the value of temporal context, but the conventional workflow still often commits to one measurement from an image before the longitudinal model receives it.

Our methodological question is whether the predictive state can participate earlier, while the current image is still being analyzed. Bayesian inference necessarily contains prior information; that fact alone is not novel. Here, \emph{prior-guided} describes image analysis: the state predicted from earlier images guides current plant association and, when alternatives exist, scores competing top candidates before measurement extraction. \emph{Bayesian longitudinal} describes the height-growth model that supplies and updates this predictive state. Related state-space methods have been used for sequential crop estimation and tracking \cite{gordon1993particle,west1997bayesian,durbin2012time,yang2022ricepf,li2022kalman,shimda2026bayesianheight}. The new element is the explicit feedback across the image/model boundary together with physical calibration and auditable uncertainty.

We call the sequential computation filtering because it recursively estimates the current latent height and growth distribution after each new observation. At date $t$, the algorithm uses images available through $t$; a future image is appended only when it arrives and starts the next update. It does not revise an earlier reported value. This is the operational online setting required when plant scientists want a height result as soon as a new image enters the pool.

The study makes four contributions. First, it specifies and tests prior-guided image association and candidate choice within a Bayesian longitudinal pipeline. Second, it audits physical-reference definitions and rejects an automatic red-band enumeration when its inferred span conflicts with the recorded pole length. Third, it develops the transfer on 2021 data and evaluates it against later-year 2024 manual heights from newly grown plants without fitting to those outcomes. Fourth, it releases code, derived validation data, and a point-and-click application that returns height as a function of study day. The evidence distinguishes mechanism, temporal transfer, calibration, and operational claims so that each conclusion is tied to its appropriate reference.
"""


METHODS = r"""\section{Materials and Methods}

\subsection{Study design and evidence separation}

Figure~\ref{fig:workflow} summarizes the information flow. Let $\mathcal I_{\leq t}$ contain only images acquired through time $t$. The predictive state from $t-1$ guides association and candidate evaluation in image $t$, the selected extent is converted to centimeters, and the posterior height-growth distribution is returned after the image is incorporated. Images acquired later are absent from that calculation.

\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{online_bayesian_workflow.pdf}
\caption{Prefix-causal workflow. The feedback arrows place longitudinal information inside analysis of the current image. The running position state was executed in the field pipeline; the stronger height-candidate branch was evaluated in controlled ambiguity and a matched field audit. Each output uses only images available through the displayed time.}
\label{fig:workflow}
\end{figure}

The data sources have prespecified roles (Table~\ref{tab:design}). The 2021 manual records supply development calibration and internal comparator analyses. The primary temporal validation uses later-year 2024 manual measurements that were opened for scoring only after the analysis code was locked at Git commit \texttt{59b42b74596c598017fdb0cd4b80af1aec7649d6}. The 2024 images had previously been used without their manual labels during pipeline development, so this is a later-year, subject-disjoint, label-held-out validation rather than an external-site validation. Plants were newly grown each year.

\begin{table}[htbp]
\caption{Evidence sources and boundaries.}
\label{tab:design}
\centering\small
\begin{tabular}{L{2.4cm}L{3.2cm}L{7.0cm}}
\toprule
Source & Units & Role and boundary \\
\midrule
2021 manual heights & 132 records; 33 plants; 12 camera rows & Development-era estimator comparison; 61 recovered-source matches in six rows fit the later-year transfer; leave-one-row-out error quantifies transfer uncertainty \\
2024 manual heights & 247 workbook records; 166 matched records; 34 plants; four biological rows; six camera views & Primary later-year validation; manual outcomes never fit or tune a prediction \\
2021 human masks & 150 plant instances & Detector extent agreement; not an agronomic landmark reference \\
2021 support poles & 199 traces in 61 images & Reference stability and installation geometry; not red-band truth \\
Candidate experiment & 60 plants in each of eight scenarios & Prior-in-image mechanism under known candidate ambiguity \\
2025 image stream & 372 forecasts; 11 plant tracks; two cameras & Secondary transfer of prediction intervals to the next image-derived measurement \\
\bottomrule
\end{tabular}
\end{table}

\subsection{2024 biological rows, paired camera views, and manual reference}

The Camera layout worksheet defines four biological rows. Each row is covered by a paired right and left camera view rather than two independent row replicates (Table~\ref{tab:cameras}). Plants are numbered across the biological row from right to left. Right-camera local identities 1--6 map to global plants 1--6; left-camera local identities 1--6 map to global plants 7--12. Both views and all repeated dates from a row remain together whenever a row is resampled.

\begin{table}[htbp]
\caption{Paired cameras for the four 2024 biological rows.}
\label{tab:cameras}
\centering\small
\begin{tabular}{lllll}
\toprule
Biological row & Left camera & Left plants & Right camera & Right plants \\
\midrule
M-0006 & NL5RH & 7--12 & NGGJK & 1--6 \\
M-0013 & NH888 & 7--12 & NGFZT & 1--6 \\
W-0010 & NH88X & 7--12 & NJQMT$^{a}$ & 1--6 \\
W-0015 & NGFY5$^{b}$ & 7--12 & NH88L & 1--6 \\
\bottomrule
\multicolumn{5}{l}{\footnotesize $^{a}$No pose output in the analysis archive. $^{b}$No quality-controlled pose output.}
\end{tabular}
\end{table}

The workbook contains 247 nonmissing heights from 45 plants. The M rows were measured on 5, 10, 15, 18, 23, and 28 July 2024; the W rows on 6, 15, 18, 23, and 28 July. Exact local times are retained in the released table. The source protocol defines two possible pre-tasseling endpoints---the topmost point touching the meter stick and the topmost fully visible collar---and a post-tasseling flag-leaf endpoint that excludes the tassel. The workbook stores one value per plant-date but does not identify which pre-tasseling endpoint was used. We therefore call the outcome \emph{manual field height} and do not infer its anatomical landmark.

Manual records were joined to the closest quality-controlled image on the same calendar date by biological row, camera side, and global plant identity. Absolute time lag had median 2.78 h, mean 2.69 h, and maximum 6.90 h. Of 247 workbook records, 54 belonged to the two camera halves without usable automated output and 27 more lacked a quality-controlled output on that date, leaving 166 comparisons from 34 plants, four biological rows, six contributing cameras, and seven distinct calendar dates.

\subsection{Physical references and scale transfer}

The 2021 support-pole annotations run from ground contact to the nominal 5-ft camera mount or optical-center height. They provide an installation audit and a temporal-stability measure (Figure~\ref{fig:supportpole}). The 2024 reference is a different approximately vertical 8--10-ft pole with red marks spaced exactly 1 ft edge-to-edge; its visible bottom is not assumed to be ground.

\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{pole_annotation_2021.pdf}
\caption{Representative 2021 support-pole annotations. Each trace connects ground contact to the nominal 5-ft camera mounting or optical-center height. The horizontal field-layout marks are not vertical pole graduations. Personal identifiers have been removed for double-anonymized review.}
\label{fig:supportpole}
\end{figure}

Before the 2024 manual outcomes were scored, we fit
\begin{equation}
H_{\mathrm{manual}}=\beta_0+\beta_1(P\times 0.415886),
\label{eq:transfer}
\end{equation}
using 61 matched 2021 development records, where $P$ is image extent in pixels and 0.415886 cm/pixel is the recorded 2021 geometric scale. Transfer to the 2024 layout used the recorded distance ratio $8.5/10.25=0.829268$. The 2021 leave-one-camera-row-out root mean squared error was retained as a nonshrinking calibration-transfer component.

We did not use the automatic red-component sequence for the 2024 manual-height comparison. An audit of 237 accepted candidate fits found 89 implying more than 10 one-foot intervals; 1,296 of 1,302 filtered records used a selected span greater than the documented 10-ft maximum. A small within-image interpolation residual can establish regular spacing but cannot verify physical band identity. This audit was completed before interpreting the manual-height comparison.

\subsection{Prior-guided image analysis}

At the first complete view, detections are sorted horizontally to initialize plant identities. For each later image, a minimum-total-distance assignment links current detections to the running horizontal states; assignments beyond a normalized-distance gate of 0.16 are rejected. After a match, horizontal position and base row are updated with fixed gain 0.5. This fixed-gain location update is not itself a full Bayesian posterior, but it lets earlier images guide current association and base refinement.

The stronger candidate branch uses the predicted height distribution before the current measurement is fixed. Candidate $j$ with confidence $q_j$ and calibrated height $h_j$ receives
\begin{equation}
\ell_j=\log(q_j+\epsilon)-\frac{(h_j-\mu_{t\mid t-1})^2}{2(s_{t\mid t-1}^2+\sigma_j^2)}.
\label{eq:candidate}
\end{equation}
The candidate maximizing $\ell_j$ enters the update. Thus the method can reject a visually confident but longitudinally implausible top before that choice is hidden inside a scalar observation. The field result uses the executed association/base-feedback branch; the top-candidate mechanism is assessed separately in simulation and in a matched real-image audit.

\subsection{Bayesian longitudinal height and growth}

The latent state is $x_t=(h_t,r_t)^\top$, where $h_t$ is height and $r_t$ is growth rate. For the primary 2024 transfer and elapsed time $\Delta_t$,
\begin{align}
h_t &= h_{t-1}+r_{t-1}\Delta_t+\eta_{h,t},\\
r_t &= r_{t-1}+\eta_{r,t},
\end{align}
with height truncated to 0--450 cm and growth to -4--15 cm/day. The first-image growth distribution is $N(3,2^2)$ cm/day, and the height and growth process scales are 8.78 cm/$\sqrt{\mathrm{day}}$ and 0.35 cm/day/$\sqrt{\mathrm{day}}$. The measurement likelihood is the robust mixture
\begin{equation}
p(Y_t\mid h_t)=(1-\pi)\phi(Y_t;h_t,\sigma_t^2)+\pi\phi(Y_t;h_t,\sigma_{\mathrm{out}}^2).
\label{eq:mixture}
\end{equation}
A bootstrap particle filter with 5,000 particles, outlier probability 0.08, and outlier scale 60 cm propagates, weights, and resamples when effective sample size falls below half the particle count \cite{gordon1993particle}. We use \emph{filtering} in its state-space sense: the posterior after image $t$ conditions on observations through $t$, not on future observations.

For 2024 transfer-aware agreement intervals, the 2021 leave-one-row-out calibration root mean squared error is added in quadrature as a nonshrinking component, and Student-$t$ quantiles with five degrees of freedom reflect the six development camera rows. This prevents the longitudinal posterior from becoming spuriously narrow as images accumulate while a cross-layout calibration error remains.

\subsection{Temporal validation and statistical analysis}

All 2024 predictions were generated before joining manual outcomes. Single-frame and Bayesian estimates were compared by signed error, mean absolute error (MAE), root mean squared error (RMSE), and Pearson correlation. Fixed prefix-causal comparators were EWMA with $\alpha=0.5$, a three-image running median, Holt level--trend with $\alpha=0.5$ and $\beta=0.2$, and a Gaussian local-linear filter. The Gaussian filter received the same $N(3,2^2)$ initial growth distribution and process scales as the particle filter; its observation variance used the same 2021 transfer RMSE. Thus its comparison isolates the robust likelihood and particle representation rather than a different prior. The paired MAE gain is a comparator's record-level absolute error minus Bayesian absolute error. Its 95% interval uses 20,000 bootstrap samples of the four biological rows, retaining both cameras, plants, and dates within each sampled row. Because there are only four row clusters, the interval is treated as a descriptive pilot uncertainty estimate rather than a high-powered significance test. Agreement intervals were evaluated at 50%, 80%, 90%, and 95% levels with coverage and mean width reported together.

The controlled candidate experiment used 60 simulated plants in each of eight growth, missingness, and observation scenarios. Every method received the same candidates and state dynamics; only the location of prior use differed. Five-fold human-mask validation measured detector extent agreement. Prefix causality was verified by recomputing every camera-time prefix and comparing outputs already emitted with the corresponding complete-run rows.

\subsection{Reproducibility and plant-scientist delivery}

The anonymous review archive contains executable analysis scripts, fixed seeds, imported manual data, camera-pair mapping, matched validation records, bootstrap draws, figure sources, the released pose checkpoint, curated images, and checksums. The browser application accepts dated images, permits a separate visible-plant count for each camera, and returns current-image height, Bayesian mean, 80% and 95% intervals, quality flags, annotated frames, and height versus study day. Daily images acquired at a similar time are the preferred prospective schedule; irregular intervals are supported through $\Delta_t$.
"""


RESULTS = r"""\section{Results}

\subsection{Development calibration and physical-reference audit}

The 61 matched 2021 records from six camera rows gave $\widehat\beta_0=\TransferCalibrationIntercept{}$ cm and $\widehat\beta_1=\TransferCalibrationSlope{}$ in Equation~\ref{eq:transfer}. Leave-one-camera-row-out MAE was \TransferDevCVMAE{} cm and RMSE was \TransferDevCVRMSE{} cm. Across the larger 2021 development-era comparison, the single-frame and robust Bayesian estimates had MAE \FieldSingleMAE{} and \FieldBayesMAE{} cm, respectively. This comparison supports algorithm development and internal checking; because 2021 labels now calibrate the later-year transfer, it is not presented as the primary independent validation.

The 172 usable support-pole annotations formed 39 repeated row--pole series across 12 camera rows. Median within-series coefficient of variation was \PoleRepeatabilityMedianCV{}% (95% whole-row bootstrap interval, \PoleRepeatabilityMedianCVLo{}--\PoleRepeatabilityMedianCVHi{}%), supporting temporal stability of projected reference geometry. It does not establish that automatically enumerated red components have the correct physical identities. The red-span audit described above is why those automatic sequences were excluded from the 2024 manual-height calibration.

\subsection{Later-year 2024 manual-height validation}

The primary validation contained \TransferValidationN{} matched records from \TransferValidationPlants{} newly grown plants in \TransferValidationRows{} biological rows and \TransferValidationCameras{} contributing camera views. Single-frame estimates had bias \TransferSingleBias{} cm, MAE \TransferSingleMAE{} cm, RMSE \TransferSingleRMSE{} cm, and correlation \TransferSingleCorrelation{}. Bayesian longitudinal estimates had corresponding values \TransferBayesBias{}, \TransferBayesMAE{}, \TransferBayesRMSE{} cm, and \TransferBayesCorrelation{} (Table~\ref{tab:performance}; Figure~\ref{fig:transfer}).

The paired MAE gain over single frames was \TransferMAEGain{} cm. Its 95% biological-row cluster interval, \TransferMAEGainLo{} to \TransferMAEGainHi{} cm, included zero. Three of four rows favored the longitudinal estimate; the W-0015 row did not. The Bayesian estimate improved on EWMA by \TransferEWMAGain{} cm (row-cluster interval, \TransferEWMAGainLo{}--\TransferEWMAGainHi{}) and the running median by \TransferMedianGain{} cm (\TransferMedianGainLo{}--\TransferMedianGainHi{}). Its \TransferHoltGain{}-cm improvement over Holt was uncertain (\TransferHoltGainLo{}--\TransferHoltGainHi{}). The matched-prior Gaussian filter had MAE \TransferGaussianMAE{} cm, only 0.01 cm below the Bayesian value, and RMSE \TransferGaussianRMSE{} cm, 0.01 cm above it. We interpret these two filters as practically tied.

\begin{table}[htbp]
\caption{Fixed prefix-causal estimators in the primary 2024 later-year, label-held-out validation. The Gaussian and particle filters use the same initial growth prior and process scales. Uncertainty resamples four biological rows rather than six camera views.}
\label{tab:performance}
\centering\small
\resizebox{\textwidth}{!}{
\begin{tabular}{llrrrrr}
\toprule
Year and role & Estimator & $n$ & Bias (cm) & MAE (cm) & RMSE (cm) & $r$ \\
\midrule
2024 validation & Single frame & \TransferValidationN & \TransferSingleBias & \TransferSingleMAE & \TransferSingleRMSE & \TransferSingleCorrelation \\
 & EWMA & \TransferValidationN & \TransferEWMABias & \TransferEWMAMAE & \TransferEWMARMSE & \TransferEWMACorrelation \\
 & Running median & \TransferValidationN & \TransferMedianBias & \TransferMedianMAE & \TransferMedianRMSE & \TransferMedianCorrelation \\
 & Holt level--trend & \TransferValidationN & \TransferHoltBias & \TransferHoltMAE & \TransferHoltRMSE & \TransferHoltCorrelation \\
 & Gaussian local-linear & \TransferValidationN & \TransferGaussianBias & \TransferGaussianMAE & \TransferGaussianRMSE & \TransferGaussianCorrelation \\
 & Bayesian longitudinal & \TransferValidationN & \TransferBayesBias & \TransferBayesMAE & \TransferBayesRMSE & \TransferBayesCorrelation \\
\bottomrule
\end{tabular}
}
\end{table}

\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{manual_height_transfer_2024.pdf}
\caption{Temporal transfer from 2021 development to 2024 validation. (a) Development calibration fitted only on 2021 records. (b,c) Single-frame and Bayesian longitudinal estimates against later-year manual field height; equality is dashed. (d) Biological-row mean trajectories, with the paired left/right camera views retained inside the same row. The 2024 manual outcomes were joined only after predictions were generated.}
\label{fig:transfer}
\end{figure}

Transfer-aware 50%, 80%, 90%, and 95% intervals covered 53.0%, \TransferCoverageEighty{}%, 90.4%, and \TransferCoverageNinetyFive{}% of the manual heights. The corresponding mean widths were 27.6, \TransferWidthEighty{}, 76.4, and \TransferWidthNinetyFive{} cm. Coverage was close to nominal from 80% through 95%, but the upper-level intervals were wide, exposing the cross-layout calibration uncertainty rather than hiding it.

\subsection{Prior-guided candidate mechanism}

In controlled ambiguity, single-frame selection had plant-level RMSE \PriorNoneRMSE{} cm, filtering after selection reduced it to \PriorPostRMSE{} cm, and allowing the predicted height distribution to score candidates before the update reduced it further to \PriorInsideRMSE{} cm (Figure~\ref{fig:priorsim}). The within-plant reduction relative to post-selection filtering was \PriorVsPostGain{} cm (95% plant-bootstrap interval, \PriorVsPostGainLo{}--\PriorVsPostGainHi{}), and prior-guided scoring selected the truth-closest candidate \PriorTruthSelectionRate{}% of the time.

\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{prior_in_detection_sim.pdf}
\caption{Controlled candidate-ambiguity experiment. All methods received the same candidates and state dynamics. Only the prior-guided method let the predicted height distribution participate before a top candidate was committed.}
\label{fig:priorsim}
\end{figure}

In the matched real-image audit, post-selection filtering and height-prior candidate scoring chose the same candidate for all \RealAuditN{} evaluated plant-dates and consequently had identical MAE, \RealAuditPostMAE{} cm. This is a negative control: the released natural candidate subset did not contain a conflict for the prespecified rule to resolve. The field evidence therefore supports prior-guided association and base refinement, while the top-candidate accuracy benefit remains demonstrated under controlled ambiguity.

\subsection{Uncertainty, detector agreement, and prefix causality}

The 2024 manual-height agreement intervals are summarized in Table~\ref{tab:uncertainty}. As a distinct secondary task, parameters estimated from 2024 image increments produced \UncertaintyTestCoverageNinetyFive{}% coverage with mean width \UncertaintyTestWidthNinetyFive{} cm on \UncertaintyTestN{} next-image forecasts from 11 newly grown 2025 plant tracks at two cameras. That result supports year-forward interval transfer for those installations; it is not a manual-height validation.

\begin{table}[htbp]
\caption{Uncertainty evaluations. Coverage and width are reported together because nominal coverage alone can be achieved by uninformatively wide intervals.}
\label{tab:uncertainty}
\centering\small
\resizebox{\textwidth}{!}{
\begin{tabular}{llrrrr}
\toprule
Target & Data & Nominal (\%) & $n$ & Coverage (\%) & Mean width (cm) \\
\midrule
Manual field height & 2024 validation & 50 & \TransferValidationN & 53.0 & 27.6 \\
 & & 80 & \TransferValidationN & \TransferCoverageEighty & \TransferWidthEighty \\
 & & 90 & \TransferValidationN & 90.4 & 76.4 \\
 & & 95 & \TransferValidationN & \TransferCoverageNinetyFive & \TransferWidthNinetyFive \\
Next image measurement & 2025 temporal test & 95 & \UncertaintyTestN & \UncertaintyTestCoverageNinetyFive & \UncertaintyTestWidthNinetyFive \\
\bottomrule
\end{tabular}
}
\end{table}

Five-fold detector validation matched \PixelMatched{} of \PixelInstances{} human masks. Mean top and root errors were \PixelTopMAEPx{} and \PixelRootMAEPx{} pixels; extent error was \PixelHeightMAEPx{} pixels with correlation \PixelHeightCorr{}. These values measure agreement with mask extent, not an independently clicked collar. All \CausalPrefixes{} prefix recomputations matched their complete-run counterparts, with \CausalMismatches{} mismatches among \CausalRows{} cumulative comparisons, verifying that a later image does not alter an earlier output under fixed settings.
"""


DISCUSSION = r"""\section{Discussion}

The later-year manual data materially improve the evidentiary design. Development uses 2021 records, while 2024 predictions are generated without their manual outcomes and are then evaluated on newly grown plants. This is temporal, subject-disjoint, label-held-out validation. It is stronger than scoring the same year used to establish the transfer, although it is not fully external because the unlabeled 2024 images contributed to earlier pipeline development.

The paired-camera layout changes the effective sample size. Six contributing camera views do not constitute six independent field rows: they belong to four biological rows, with left and right views observing different halves of the same row. Resampling the biological row preserves camera pairing and repeated plant dates. This choice produces a wider and more credible interval than treating 166 records or six views as independent. With only four clusters, the result should be read through its effect estimate and uncertainty rather than a binary significance claim.

The point-estimate evidence is favorable against single images and simple smoothers but modest against the strongest state-space comparator. Relative to a single image, MAE fell by 0.74 cm, RMSE by 1.13 cm, and correlation increased by 0.034. The biological-row interval includes zero and one row favored the single-frame estimate. With matched priors and process scales, the Gaussian and particle filters differed in MAE and RMSE by about 0.01 cm in opposite directions. These findings do not support a claim that particle filtering itself yields a meaningful accuracy advantage over a Gaussian filter. They show that longitudinal state estimation reduced aggregate error relative to single images, EWMA, and the running median while the robust Bayesian formulation supplied mixture-based uncertainty and the state used by prior-guided image analysis.

The methodological contribution remains the location at which longitudinal information acts. A conventional analysis can extract one height independently from every image and connect those fixed values afterward. Here the state returned by the Bayesian longitudinal model guides association and base refinement during the next image analysis, while the candidate experiment isolates the stronger top-choice mechanism. The simulation demonstrates why this architecture can matter when candidates conflict; the all-agreement field audit prevents us from claiming that the released natural subset demonstrates the same top-choice benefit.

The physical-reference audit also changes the interpretation constructively. Automatic red components often implied a marked span longer than the documented pole, even when their interpolation residual was small. We therefore excluded that enumeration from the 2024 manual comparison and transferred the independently recorded 2021 scale through camera distance. This choice increases internal validity at the cost of a visible negative bias and wide transfer intervals. A future deployment should encode band identity explicitly, constrain the number of physical intervals, and include a ground-referenced landmark in the camera field.

The 2024 transfer-aware intervals were near nominal at 80%, 90%, and 95%, but their 95% mean width was 97.5 cm. This width is scientifically important: frequent images reduce sequential noise but cannot erase a cross-layout calibration component. The released application reports these intervals and quality flags rather than only a smooth curve. It can process one image per day, plot height against days after the first image, and handle irregular dates, which makes the algorithm directly usable by plant scientists while keeping its limitations visible.

Several limitations remain. The primary validation has four biological rows at one site, two camera halves have no usable automated output, and manual and image acquisitions differ by up to 6.9 h. The workbook does not encode which pre-tasseling manual endpoint was used. Bias increases at taller plants, suggesting residual scale or landmark mismatch. The top-candidate field audit contains no natural conflict. The released checkpoint has incomplete original training-image provenance, and the larger raw image archive is not redistributed. These limits motivate evaluation across more camera layouts and explicit landmark protocols, but the current data are sufficient to test a later-year transfer without outcome leakage.

\subsection{Conclusions}

Prior-guided image analysis and Bayesian longitudinal updating convert accumulating fixed-camera images into as-of maize height trajectories. In later-year, label-held-out validation, the longitudinal estimate modestly reduced aggregate error and increased correlation relative to single images; uncertainty calibrated near nominal levels while remaining wide enough to reveal scale-transfer limitations. The work contributes an auditable feedback architecture, a physically grounded calibration audit, paired-row inference, and a plant-scientist application. It supports affordable longitudinal field phenotyping while stating where additional camera layouts and explicit anatomical references are still needed.

\section*{Data Availability Statement}
The anonymous review archive supplied with this submission contains the analysis code, imported 2024 manual-height table, camera-pair map, matched validation records, bootstrap output, figure sources, curated images and annotations used for reproducibility, and cryptographic checksums. A public versioned repository is identified to the editor on the separate title page and will remain available with the article. The larger raw-image archive remains in institutional storage; the derived records needed to reproduce the reported analyses are included. No separate reuse license has been confirmed for non-code image and annotation materials; code is distributed under the MIT License.

\section*{Conflict of Interest}
The authors declare no conflict of interest.

\section*{Author Contributions, Funding, and Acknowledgments}
Provided on the separate title page and removed here for double-anonymized review.

\section*{Declaration of Generative AI and AI-Assisted Technologies}
During preparation of this work, the authors used Claude (Anthropic) and Codex (OpenAI) to assist with data exploration, code review, figure and manuscript preparation, and language editing. The authors reviewed and edited all assisted content, verified the reported results against the included analysis code, and take full responsibility for the manuscript.
"""


def make_main() -> str:
    return (
        PREAMBLE
        + rf"""
\begin{{document}}
\begin{{frontmatter}}
\title{{{TITLE}}}
\begin{{abstract}}
{ABSTRACT}
\end{{abstract}}
\begin{{keyword}}
affordable phenotyping \sep Bayesian longitudinal analysis \sep fixed camera \sep maize height \sep prior-guided image analysis \sep temporal validation \sep uncertainty calibration
\end{{keyword}}
\end{{frontmatter}}
\doublespacing
\linenumbers

\section*{{Plain Language Summary}}
Fixed cameras can measure the same field plants repeatedly, but overlap and camera scale can make any one picture misleading. Our method lets the history of a plant guide analysis of each new picture, then reports height, growth, and uncertainty immediately after that picture is added. We developed the cross-camera conversion on 2021 data and tested it against 166 manual measurements from new plants in 2024 without using those manual values to fit the predictions. The time-aware estimate had slightly lower average error and higher correlation than measuring each image alone. Its uncertainty covered the manual values at approximately the intended rates, although the intervals were wide. We also found that an automatic red-mark sequence sometimes implied a pole longer than the documented pole, so we excluded that scale from the manual-height test. The released application lets plant scientists upload dated images and obtain height-versus-day curves with quality checks.

{INTRODUCTION}
{METHODS}
{RESULTS}
{DISCUSSION}

\bibliographystyle{{elsarticle-harv}}
\bibliography{{references}}
\end{{document}}
"""
    )


def make_title_page() -> str:
    return (
        PREAMBLE
        + rf"""
\begin{{document}}
\singlespacing
\begin{{frontmatter}}
\title{{{TITLE}}}
\author[stat]{{Haoming Wang}}
\author[stat,vet]{{Chong Wang}}
\author[psi,igg,agron]{{Yawei Li}}
\author[psi,agron]{{Cheng-Ting Yeh}}
\author[psi,igg,agron]{{Patrick S. Schnable}}
\author[stat]{{Peng Liu\corref{{cor1}}}}
\ead{{pliu@iastate.edu}}
\cortext[cor1]{{Corresponding author: Peng Liu, Department of Statistics, Iowa State University, 2117 Snedecor Hall, 2438 Osborn Drive, Ames, IA 50011-1090, USA.}}
\affiliation[stat]{{organization={{Department of Statistics, Iowa State University}}, addressline={{2438 Osborn Drive}}, city={{Ames}}, state={{Iowa}}, postcode={{50011-1090}}, country={{USA}}}}
\affiliation[vet]{{organization={{Department of Veterinary Diagnostic and Production Animal Medicine, Iowa State University}}, addressline={{1809 South Riverside Drive}}, city={{Ames}}, state={{Iowa}}, postcode={{50011-1134}}, country={{USA}}}}
\affiliation[psi]{{organization={{Plant Sciences Institute, Iowa State University}}, addressline={{1111 WOI Road}}, city={{Ames}}, state={{Iowa}}, postcode={{50011-1085}}, country={{USA}}}}
\affiliation[igg]{{organization={{Interdepartmental Genetics and Genomics Graduate Program, Iowa State University}}, addressline={{2014 Molecular Biology Building, 2437 Pammel Drive}}, city={{Ames}}, state={{Iowa}}, postcode={{50011-1079}}, country={{USA}}}}
\affiliation[agron]{{organization={{Department of Agronomy, Iowa State University}}, addressline={{Agronomy Hall, 716 Farm House Lane}}, city={{Ames}}, state={{Iowa}}, postcode={{50011-1051}}, country={{USA}}}}
\end{{frontmatter}}

\noindent\textbf{{Article type:}} Methods Article.

\noindent\textbf{{Special issue:}} Plant Modeling, Big Data Analytics, and High-Throughput Phenotyping for Smart Agriculture (submission category: VSI: PMBDA2025).

\section*{{Author Contributions}}
Haoming Wang: Conceptualization, Data curation, Formal analysis, Investigation, Methodology, Physical-reference annotation, Software, Validation, Visualization, Writing--original draft, Writing--review and editing. Chong Wang: Conceptualization, Data curation, Formal analysis, Methodology, Software, Simulation, Validation, Visualization, Writing--original draft, Writing--review and editing. Yawei Li: Data curation, Field investigation, Resources, Validation, Writing--review and editing. Cheng-Ting Yeh: Validation, Writing--review and editing. Patrick S. Schnable: Conceptualization, Experimental design, Funding acquisition, Resources, Supervision, Writing--review and editing. Peng Liu: Conceptualization, Data curation, Formal analysis, Methodology, Project administration, Software, Simulation, Supervision, Validation, Visualization, Writing--original draft, Writing--review and editing. All authors approved the final manuscript.

\section*{{Funding}}
This work was supported by the Plant Sciences Institute at Iowa State University and funds from the Laurence H. Baker Center for Bioinformatics and Biological Statistics.

\section*{{Acknowledgments}}
The authors thank the field and annotation teams whose contributions are represented in the CRediT statement.

\section*{{Conflict of Interest}}
The authors declare no conflict of interest.

\section*{{ORCID}}
Peng Liu: \href{{https://orcid.org/0000-0002-2093-8018}}{{0000-0002-2093-8018}}.

\section*{{Data and Code}}
Public repository: \href{{https://github.com/ChongWangStat/Bayesian-Longitudinal-Maize-Height}}{{github.com/ChongWangStat/Bayesian-Longitudinal-Maize-Height}}. A self-contained anonymous review archive accompanies the double-anonymized files. Code is MIT licensed. No separate reuse license has been confirmed for non-code data, images, annotations, model weights, figures, or manuscript materials.

\section*{{Author Approval and Originality}}
All authors approved submission. The manuscript and method have not been published previously, are not under consideration elsewhere, and no conflict of interest is declared.
\end{{document}}
"""
    )


def make_cover_letter() -> str:
    return (
        PREAMBLE
        + rf"""
\begin{{document}}
\singlespacing
\begin{{flushright}}
15 September 2026
\end{{flushright}}

\noindent Dear Editors,

We submit the Methods Article ``{TITLE}'' for the special issue \emph{{Plant Modeling, Big Data Analytics, and High-Throughput Phenotyping for Smart Agriculture}} (VSI: PMBDA2025).

The manuscript addresses a recurring high-throughput phenotyping problem: image measurements are often chosen independently and only then connected by a time-series model. Our method returns the Bayesian longitudinal predictive state to analysis of the next image, where it guides plant association and can score competing top candidates before a height is committed. This prior-guided image-analysis loop is combined with fixed-camera physical calibration, prefix-causal daily updates, transparent uncertainty, and an application that lets plant scientists upload dated images and obtain height-versus-day trajectories.

The revision adds a later-year manual reference that materially strengthens the design. The transfer was developed on 2021 records, while all 166 matched 2024 manual outcomes from 34 newly grown plants were withheld from fitting and tuning. The four biological rows are the inferential clusters; each row's left and right cameras remain paired. Mean absolute error decreased from 18.10 to 17.36 cm and correlation increased from 0.813 to 0.847. We report that the 0.74-cm MAE gain is modest and uncertain (four-row 95% cluster interval, -0.44 to 1.30 cm). A Gaussian filter with matched priors was effectively tied (MAE 17.35 cm; RMSE 22.42 versus 22.41 cm), while the Bayesian method improved on EWMA and a running median. Transfer-aware 80%, 90%, and 95% interval coverage was 78.9%, 90.4%, and 97.0%. We also disclose and correct a red-band identity problem instead of using a physically inconsistent automatic scale.

The work fits the special issue through its integration of modeling, image analytics, high-frequency field phenotyping, and a usable smart-agriculture workflow. The complete code, protocol, camera mapping, derived validation records, checksums, and example application inputs are supplied for independent reproduction. The anonymized manuscript, supplement, and review archive contain no author identifiers; author and funding information are confined to the title page.

All authors approved the manuscript. It has not been published and is not under consideration elsewhere. The authors declare no conflict of interest. We have included the required data-availability and generative-AI disclosures.

Thank you for considering this work.

\vspace{{1.5em}}
\noindent Sincerely,\\
Peng Liu, corresponding author\\
Department of Statistics, Iowa State University\\
pliu@iastate.edu
\end{{document}}
"""
    )


def make_supplement() -> str:
    src = (SRC / "supplement.tex").read_text(encoding="utf-8")
    body = src.split("\\section{Detailed implementation specification}", 1)[1]
    body = "\\section{Detailed implementation specification}" + body
    body = body.rsplit("\\end{document}", 1)[0]
    replacements = {
        "2021 independent manual-reference validation": "2021 development-era manual-reference analysis",
        "2021 independent manual-reference": "2021 development-era manual-reference",
        "primary independent manual-reference": "2021 development-era manual-reference",
        "primary independent validation": "2021 development-era validation",
        "primary 2021 physical-reference target": "2021 development-era physical-reference target",
        "primary 2021": "2021 development-era",
        "primary validation": "development-era validation",
        "Haoming Wang's human physical-reference annotations": "Human physical-reference annotations",
        "Haoming Wang manually annotated": "A study annotator manually annotated",
        "Haoming Wang manually created": "A study annotator manually created",
        "C-XXX.xml": "C-[camera-row number].xml",
        "All paths below are relative to the \\href{https://github.com/ChongWangStat/Bayesian-Longitudinal-Maize-Height}{public GitHub repository}.": "All paths below are relative to the anonymous review archive supplied with the submission.",
    }
    for old, new in replacements.items():
        body = body.replace(old, new)

    new_section = r"""
\section{Later-year 2024 manual-height validation}
\label{sec:s-2024-validation}

The source workbook was imported without numerical imputation or correction. It contains 247 nonmissing manual field heights from 45 plants in four biological rows. The Camera layout worksheet establishes that each biological row is covered by a left/right camera pair. Right-view local plant identities 1--6 map to row-wide right-to-left identities 1--6, and left-view identities map to 7--12. Two camera halves did not yield usable automated output. After same-date quality control, 166 records from 34 plants, four biological rows, and six camera views remained.

The two views are not treated as independent rows. All bootstrap replicates sample the biological row and retain both camera views, every plant, and all dates inside that row. The complete camera accounting is in \path{outputs/manual_height_transfer_2024/camera_pair_accounting_2024.csv}; the imported layout is in \path{data/raw/manual_height_2024/camera_layout_2024.csv}.

The analysis code was locked at commit \texttt{59b42b74596c598017fdb0cd4b80af1aec7649d6} before the workbook was opened for scoring. The transfer equation was fitted on 61 recovered-source 2021 records from six camera rows. The recorded camera-distance ratio, $8.5/10.25$, maps the 2021 scale to 2024. The 2021 leave-one-camera-row-out RMSE, \TransferDevCVRMSE{} cm, is retained as a nonshrinking transfer component. Student-$t$ intervals use five degrees of freedom. Every 2024 camera is processed in time order; manual outcomes are joined only after single-frame and Bayesian predictions are emitted.

The Bayesian and Gaussian filters use the same $N(3,2^2)$ cm/day initial growth distribution, 8.78 cm/$\sqrt{\mathrm{day}}$ height-process scale, and 0.35 cm/day/$\sqrt{\mathrm{day}}$ growth-process scale. The Gaussian observation variance is the squared 2021 transfer RMSE. Other fixed comparators are EWMA ($\alpha=0.5$), a three-image running median, and Holt level--trend ($\alpha=0.5$, $\beta=0.2$). All comparators process the complete daily prefix before manual outcomes are joined.

\begin{table}[htbp]
\caption{Contribution of each 2024 biological row to the later-year manual validation. Positive MAE gain favors Bayesian longitudinal estimation.}
\label{tab:s-2024-row}
\centering\small
\begin{tabular}{lrrrr}
\toprule
Biological row & Records & Plants & Single-frame MAE (cm) & Bayesian MAE (cm) \\
\midrule
M-0006 & 48 & 11 & 19.87 & 18.38 \\
M-0013 & 66 & 12 & 12.74 & 11.61 \\
W-0010 & 25 & 5 & 28.98 & 28.74 \\
W-0015 & 27 & 6 & 18.00 & 19.08 \\
\bottomrule
\end{tabular}
\end{table}

Overall single-frame MAE was \TransferSingleMAE{} cm and Bayesian MAE was \TransferBayesMAE{} cm; the corresponding RMSEs were \TransferSingleRMSE{} and \TransferBayesRMSE{} cm. Correlation increased from \TransferSingleCorrelation{} to \TransferBayesCorrelation{}. The \TransferMAEGain{}-cm paired MAE gain had a four-row bootstrap interval of \TransferMAEGainLo{} to \TransferMAEGainHi{} cm. Transfer-aware coverage at 50%, 80%, 90%, and 95% was 53.0%, \TransferCoverageEighty{}%, 90.4%, and \TransferCoverageNinetyFive{}%, with mean widths 27.6, \TransferWidthEighty{}, 76.4, and \TransferWidthNinetyFive{} cm.

\begin{table}[htbp]
\caption{Fixed causal comparator results against 2024 manual field height. Baseline-minus-Bayesian MAE is positive when the Bayesian estimate has lower MAE.}
\label{tab:s-2024-baselines}
\centering\small
\resizebox{\textwidth}{!}{
\begin{tabular}{lrrrr}
\toprule
Estimator & Bias (cm) & MAE (cm) & RMSE (cm) & Baseline minus Bayesian MAE (cm) \\
\midrule
Single frame & \TransferSingleBias & \TransferSingleMAE & \TransferSingleRMSE & \TransferMAEGain \\
EWMA & \TransferEWMABias & \TransferEWMAMAE & \TransferEWMARMSE & \TransferEWMAGain \\
Running median & \TransferMedianBias & \TransferMedianMAE & \TransferMedianRMSE & \TransferMedianGain \\
Holt level--trend & \TransferHoltBias & \TransferHoltMAE & \TransferHoltRMSE & \TransferHoltGain \\
Gaussian local-linear & \TransferGaussianBias & \TransferGaussianMAE & \TransferGaussianRMSE & \TransferGaussianGain \\
Bayesian longitudinal & \TransferBayesBias & \TransferBayesMAE & \TransferBayesRMSE & 0.00 \\
\bottomrule
\end{tabular}
}
\end{table}

The manual and image acquisitions were matched by calendar date. Their absolute time difference had median 2.78 h and maximum 6.90 h. The source protocol provides two possible pre-tasseling definitions but the workbook does not identify which was used. The outcome is therefore labeled manual field height rather than a particular anatomical landmark.

An associated metadata audit found that 89 of 237 accepted red-component candidate fits implied more than the documented maximum of 10 one-foot pole intervals. The 2024 manual-height comparison consequently excludes that automatic enumeration and uses the 2021 transfer plus recorded camera geometry. Files sufficient to reproduce this decision and the validation are under \path{outputs/manual_height_transfer_2024/}.

"""
    body = new_section + body
    return (
        PREAMBLE
        + rf"""
\renewcommand{{\thesection}}{{S\arabic{{section}}}}
\renewcommand{{\thesubsection}}{{\thesection.\arabic{{subsection}}}}
\renewcommand{{\thefigure}}{{S\arabic{{figure}}}}
\renewcommand{{\thetable}}{{S\arabic{{table}}}}
\renewcommand{{\theequation}}{{S\arabic{{equation}}}}
\begin{{document}}
\begin{{frontmatter}}
\title{{Supplementary Materials for\\{TITLE}}}
\end{{frontmatter}}
\linenumbers
\noindent This supplement gives the detailed implementation, causal information set, later-year camera-pair mapping, calibration decisions, uncertainty construction, candidate audit, and reproducibility provenance. Author identifiers are confined to the separate title page.

{body}
\end{{document}}
"""
    )


def write_text(name: str, content: str) -> None:
    if name.endswith(".tex"):
        content = re.sub(r"(?<!\\)%", r"\\%", content)
    (SUB / name).write_text(content.replace("\r\n", "\n"), encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build() -> None:
    SUB.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    for name in ("elsarticle.cls", "elsarticle-harv.bst"):
        shutil.copy2(TEMPLATE / name, SUB / name)
    for name in ("references.bib", "numbers.tex", "per_plant_table.tex"):
        shutil.copy2(SRC / name, SUB / name)
    shutil.copy2(
        ROOT / "outputs" / "manual_height_transfer_2024" / "numbers_2024.tex",
        SUB / "numbers_2024.tex",
    )
    figures = {
        SRC
        / "figures"
        / "online_bayesian_workflow.pdf": "online_bayesian_workflow.pdf",
        SRC / "figures" / "pole_annotation_2021.pdf": "pole_annotation_2021.pdf",
        SRC / "figures" / "prior_in_detection_sim.pdf": "prior_in_detection_sim.pdf",
        ROOT
        / "outputs"
        / "manual_height_transfer_2024"
        / "manual_height_transfer_2024.pdf": "manual_height_transfer_2024.pdf",
        SRC / "figures" / "geometry_diagram.png": "geometry_diagram.png",
        SRC / "figures" / "bayesian_trajectories.png": "bayesian_trajectories.png",
        SRC / "figures" / "uncertainty_calibration.pdf": "uncertainty_calibration.pdf",
    }
    for source, name in figures.items():
        shutil.copy2(source, FIG / name)

    write_text("01_anonymized_manuscript.tex", make_main())
    write_text("02_title_page.tex", make_title_page())
    write_text("03_anonymized_supplement.tex", make_supplement())
    write_text("04_cover_letter.tex", make_cover_letter())
    write_text(
        "05_highlights.txt",
        """• A Bayesian longitudinal state guides association inside each newly added image.
• Later-year validation withheld all 166 manual outcomes from fitting and tuning.
• Paired left/right cameras are analyzed within four biological-row clusters.
• MAE decreased from 18.10 to 17.36 cm and correlation rose to 0.847.
• A browser app returns daily plant-height trajectories and transparent uncertainty.
""",
    )
    write_text(
        "06_portal_metadata.md",
        f"""# Portal metadata

- **Journal:** Plant Phenomics
- **Article type:** Methods Article
- **Special issue category:** VSI: PMBDA2025
- **Special issue:** Plant Modeling, Big Data Analytics, and High-Throughput Phenotyping for Smart Agriculture
- **Title:** {TITLE}
- **Corresponding author:** Peng Liu, pliu@iastate.edu
- **Authors in order:** Haoming Wang; Chong Wang; Yawei Li; Cheng-Ting Yeh; Patrick S. Schnable; Peng Liu
- **Keywords:** affordable phenotyping; Bayesian longitudinal analysis; fixed camera; maize height; prior-guided image analysis; temporal validation; uncertainty calibration
- **Conflict of interest:** None declared
- **Funding:** Plant Sciences Institute at Iowa State University; Laurence H. Baker Center for Bioinformatics and Biological Statistics
- **Data statement:** Anonymous review archive supplied; public versioned GitHub repository identified on title page
- **Submission declarations:** Original work; not under consideration elsewhere; all authors approved

## Abstract

{ABSTRACT}
""",
    )
    write_text(
        "07_submission_checklist.md",
        """# Plant Phenomics submission checklist

- [x] Official Elsevier `elsarticle` class v3.5 (CTAN release dated 9 January 2026) is bundled.
- [x] Main manuscript and supplement are double anonymized.
- [x] Title page contains author names, affiliations, CRediT roles, funding, conflict declaration, ORCID, and corresponding-author details.
- [x] Methods Article length is below 15,000 words.
- [x] Abstract is at most 250 words and includes no citations.
- [x] Seven keywords are supplied.
- [x] Main text has four figures and four tables, below the combined limit of ten.
- [x] Reference list is below 40 entries.
- [x] Figures are also supplied as separate files.
- [x] Tables remain editable in LaTeX.
- [x] All 2024 manual outcomes were withheld from fitting and tuning.
- [x] The four biological rows, not six camera views or 166 records, are the resampling clusters.
- [x] Complete 247-to-166 record accounting and exact camera IDs are reported.
- [x] Data Availability Statement avoids “available on reasonable request.”
- [x] Generative-AI disclosure appears before the references.
- [x] No author identifiers or public repository URL occur in anonymized files.
- [x] All submission fields are complete.
- [x] Select `VSI: PMBDA2025` during portal submission.
- [x] Upload `.tex`, `.bib`, `.bst`, `.cls`, and figures as editable source; the system-generated PDF is the review file.
""",
    )
    write_text(
        "08_editorial_fit_and_acceptance_estimate.md",
        """# Editorial fit and acceptance estimate (internal; do not upload)

This is a reasoned planning estimate, not a published journal acceptance statistic.

- **Before incorporating the 2024 workbook:** 20–28% (central estimate 24%). The paper had useful method and software contributions, but its “independent” manual validation was earlier than the unlabeled development stream and reviewers could question the temporal story.
- **After this revision:** 30–40% (central estimate 35%). The later-year, label-held-out manual reference, exact paired-camera accounting, biological-row resampling, red-band correction, journal-specific source, and plant-scientist application address the largest credibility and usability risks.

The remaining constraints are four independent biological rows, an unencoded pre-tasseling manual endpoint, two unusable camera halves, a modest MAE gain whose row-cluster interval includes zero, and wide transfer-aware intervals. These should be stated directly. Overclaiming them would reduce rather than increase the chance of review success.
""",
    )

    durable_suffixes = {
        ".bib",
        ".bst",
        ".cls",
        ".jpeg",
        ".jpg",
        ".md",
        ".pdf",
        ".png",
        ".tex",
        ".txt",
    }
    source_files = sorted(
        p
        for p in SUB.rglob("*")
        if p.is_file()
        and p.name != "SHA256SUMS.txt"
        and p.suffix.lower() in durable_suffixes
    )
    manifest = "\n".join(
        f"{sha256(p)}  {p.relative_to(SUB).as_posix()}" for p in source_files
    )
    (SUB / "SHA256SUMS.txt").write_text(manifest + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
    print(SUB)
