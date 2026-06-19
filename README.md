# ML Engineering Knowledge Agent

A personal intelligent research assistant built on a structured knowledge graph of ML Engineering literature. The system answers precise, sourced questions about method comparisons, training conditions, and empirical results — grounded entirely in what specific papers actually reported.

---

## The Problem This Solves

Reading ML papers is slow. Most of a paper is context, motivation, and related work. The part that actually matters — *method A outperformed method B by X% on metric Y under condition Z* — is buried in a table on page 8, written in a way that makes it hard to retrieve later.

General-purpose LLMs can discuss these papers in broad terms, but they hallucinate specifics, conflate results from different conditions, and cannot tell you which table a claim came from. A vector database of paper chunks helps with retrieval but still hands unstructured text to the model and hopes for the best.

This project takes a different approach. Every claim is extracted, structured, validated, and stored as a first-class entity in an OWL/RDF knowledge graph before the agent ever touches it. When you ask a question, the answer is either in the graph — with a source — or it isn't.

---

## What It Does

You ask a natural language question. The agent translates it into a structured query against the knowledge graph, retrieves matching comparison records, and gives you a direct answer with an exact citation: paper, authors, table or figure, page number.

A concrete example:

> *"For a tabular classification problem with around 5,000 rows and noisy labels, what does the literature say about Random Forest vs XGBoost?"*

The system finds result records that match those conditions, derives the comparison at query time, and responds with something like:

> *Based on [Author et al., 2022], Table 3: Random Forest achieved 2.3% higher F1 than XGBoost on the dataset described (n=4,800, 30% label noise, 42 features). The authors note this advantage narrows when label noise drops below 15%.*

If the graph does not contain a comparison that covers your conditions, it says so. No fabrication, no vague synthesis from half-remembered training data.

---

## Core Design Philosophy

**Depth over volume.** A single well-extracted paper — every comparison condition captured, every caveat preserved, every claim traceable to a specific location — is worth more than fifty papers processed carelessly. The graph grows slowly and deliberately. Papers are only added after manual review of the extracted triples.

This is not a pipeline that ingests everything it can find. It is a curated knowledge base that earns the right to make claims.

**Every fact has a source.** No triple enters the graph without a direct link to the paper it came from, the section or table it appeared in, and the exact conditions under which the reported result holds. The moment provenance becomes optional, the system becomes unreliable.

**Conditions are not optional metadata.** The finding that Random Forest beats XGBoost is meaningless without knowing the dataset size, the feature types, the evaluation metric, and the experimental setup. The ontology captures conditions whenever present; a result with partial conditions is accepted with a flag so the agent can caveat its answer, rather than being rejected outright and losing the data. See `docs/DESIGN.md` for decisions in force (ADR-003).

**The agent reasons over structure, not text.** The LLM in this system is not asked to read papers and answer from memory. It is asked to translate questions into queries and to narrate structured results in plain language. The knowledge lives in the graph. The model handles language.

---

## What Gets Extracted

The knowledge graph is organized around one atomic unit: a **BenchmarkResult** — one method's measured value on one dataset, by one metric, under specific conditions, with a traceable source. Comparisons between methods are not stored; they are derived at query time by matching results that share the same dataset, metric, and conditions.

Each result record captures:

- The method being evaluated
- The metric and its value (including standard error when reported)
- The dataset or dataset characteristics
- The conditions that define when the result holds (dataset size, noise level, feature types, class imbalance, etc.)
- The exact source: paper, year, table or figure, page

The ontology also captures relationships between concepts — how methods relate to families, how conditions relate to problem types, how papers relate to each other through citations. This lets the agent answer questions at different levels of specificity: "what do we know about tree-based methods on small datasets" as well as "exactly how did LightGBM perform on the Higgs dataset in this specific paper."

---

## Scope

The domain is ML Engineering — the practical, empirical side of machine learning. The papers that belong here are the ones that test methods against each other, study the effect of training decisions, or characterize when a technique works and when it breaks down.

This includes supervised learning comparisons across algorithm families, studies of training dynamics and optimizer behavior, the effect of data conditions like class imbalance or distribution shift, feature engineering and preprocessing choices, and inference and deployment tradeoffs. It does not include theoretical proofs, architecture proposals without empirical comparison, or papers that benchmark only against baselines from five years ago.

The corpus starts small — a few dozen carefully chosen papers — and grows only when a new paper adds something the graph does not already cover.

---

## Architecture Overview

**Ingestion.** A paper enters the pipeline as a PDF. An LLM reads it and proposes structured triples. Those proposals go through a manual review step before anything is committed to the graph. The review is not a bottleneck — it is the quality gate that makes everything else trustworthy.

**Knowledge graph.** An OWL/RDF ontology defines the schema. A triple store (Apache Jena Fuseki) stores the instances and serves SPARQL queries. The schema is designed once, carefully, before any data is loaded.

**Semantic layer.** Paper abstracts and condition descriptions are embedded and stored in a vector database alongside the graph. This handles cases where the SPARQL query is too rigid — where the question uses different terminology than the paper did.

**Agent.** A FastAPI backend exposes the knowledge base to an LLM agent with tool access. The agent chooses between structured SPARQL queries, semantic similarity search, or both, depending on the question. It merges the results and produces a sourced answer.

**Interface.** A minimal local chat interface. Two modes: query the existing graph, or submit a new paper for ingestion review.

---

## Stack

| Component | Technology |
|---|---|
| PDF parsing | PyMuPDF |
| Extraction | Anthropic API |
| Knowledge graph | OWL/RDF + Apache Jena Fuseki |
| Vector store | ChromaDB |
| Backend | FastAPI |
| Agent | Anthropic API with tool use |
| Frontend | Vanilla JS |

---

## Why This Exists

This is a personal tool. There are no other users, no deadlines, no institutional constraints. Every design decision is made in favor of correctness and long-term usefulness, not speed of development or breadth of coverage.

The goal is a system that, six months from now, gives a more reliable answer to a question about ML method selection than any general-purpose tool available — because it has read the relevant papers carefully, structured what they actually said, and remembered it exactly.

---

*Built by Charalampos (Babis) Giannakis — MSc Business Analytics (Computational Intelligence), Vrije Universiteit Amsterdam.*
