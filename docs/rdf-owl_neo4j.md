# RDF/OWL and Neo4j

**Our primary data structure is RDF/OWL**, in case we have bottlenecks, the setup below may be useful. 

Both can be used in the **same machine-learning literature ecosystem**, but they would play different roles.

The main idea is:

> **RDF/OWL defines what the literature means; Neo4j makes the literature easy to explore and use.**

## 1. RDF/OWL as the semantic foundation

The RDF knowledge graph would be the authoritative representation of the literature.

It defines concepts such as:

```text
Paper
Author
Method
Model
Dataset
Task
Metric
Experiment
Result
ResearchQuestion
ApplicationDomain
```

And relationships such as:

```text
Paper usesMethod Method
Paper evaluatesOn Dataset
Paper addressesTask Task
Paper reportsMetric Metric
Paper cites Paper
Method isSubclassOf NeuralNetworkMethod
Dataset supportsTask Classification
```

This layer gives you a common vocabulary.

For example:

```turtle
ml:RandomForest rdfs:subClassOf ml:EnsembleMethod .
ml:EnsembleMethod rdfs:subClassOf ml:MachineLearningMethod .
```

Then a query for all `MachineLearningMethod` instances can also return Random Forest through inference.

The RDF layer is useful for:

* ontology and schema definition;
* integrating papers from different sources;
* linking concepts with Wikidata, DBpedia or external taxonomies;
* validating extracted information using SHACL;
* reasoning over subclasses and related concepts;
* keeping stable, globally identifiable entities.

This becomes the **semantic source of truth**.

---

## 2. Neo4j as the exploration and application layer

The same information can be imported into Neo4j as a property graph.

For example:

```text
(Paper)-[:USES_METHOD]->(Method)
(Paper)-[:EVALUATES_ON]->(Dataset)
(Paper)-[:REPORTS_RESULT {
    value: 0.91,
    split: "test",
    metric: "F1"
}]->(Experiment)
```

Neo4j is especially useful when users want to navigate the graph interactively.

Examples:

* find papers that use methods related to transformers;
* find the shortest citation path between two papers;
* recommend papers based on shared methods, datasets and tasks;
* identify influential methods or authors;
* detect research communities;
* find underexplored method–task combinations;
* visualize connections between papers.

Neo4j becomes the **operational and analytical interface**.

---

# Example architecture

A practical ecosystem could look like this:

```text
PDF papers
    ↓
Document parsing
    ↓
LLM / NLP information extraction
    ↓
Structured JSON
    ↓
RDF knowledge graph
    ├── ontology
    ├── SHACL validation
    ├── reasoning
    └── external entity linking
    ↓
Neo4j projection
    ├── search and navigation
    ├── recommendations
    ├── graph algorithms
    ├── visual exploration
    └── application API
```

The RDF graph stores the carefully modelled knowledge.

Neo4j contains a representation optimized for applications and analysis.

---

## Concrete example

Suppose a paper reports:

> A temporal convolutional network was evaluated on the UCI HAR dataset for activity recognition and achieved an F1 score of 0.92.

### RDF representation

```turtle
ex:Paper123 a ml:ResearchPaper ;
    ml:usesMethod ml:TemporalConvolutionalNetwork ;
    ml:evaluatesOn ml:UCI_HAR ;
    ml:addressesTask ml:ActivityRecognition ;
    ml:hasExperiment ex:Experiment123 .

ex:TemporalConvolutionalNetwork
    rdfs:subClassOf ml:DeepLearningMethod .

ex:Experiment123
    ml:hasMetric ml:F1Score ;
    ml:hasValue "0.92"^^xsd:decimal .
```

This representation expresses the meaning and type hierarchy.

### Neo4j representation

```text
(:Paper {id: "Paper123"})
    -[:USES_METHOD]->
(:Method {
    name: "Temporal Convolutional Network",
    category: "Deep Learning"
})

(:Paper {id: "Paper123"})
    -[:EVALUATES_ON]->
(:Dataset {name: "UCI HAR"})

(:Paper {id: "Paper123"})
    -[:REPORTS_RESULT {
        metric: "F1",
        value: 0.92
    }]->
(:Task {name: "Activity Recognition"})
```

This representation is convenient for querying and application development.

---

# How the two systems communicate

There are three main approaches.

## Approach 1: RDF is primary, Neo4j is a derived copy

This is usually the cleanest design.

```text
RDF/OWL graph → export or synchronize → Neo4j
```

The RDF graph remains authoritative.

Neo4j is rebuilt or updated whenever new papers are added.

Advantages:

* no ambiguity about which database is correct;
* ontology and semantic rules remain centralized;
* Neo4j can be optimized specifically for user queries.

This would likely be the strongest choice for your ecosystem.

---

## Approach 2: Neo4j is primary, RDF is exported

You model everything first in Neo4j and periodically export RDF.

This can work when the ecosystem is mainly an application, but semantic modelling becomes harder.

It is more suitable when:

* development speed matters more than formal semantics;
* graph algorithms are the core functionality;
* external linked-data compatibility is secondary.

---

## Approach 3: Separate but synchronized responsibilities

Both systems store different types of information.

For example:

### RDF stores

* paper metadata;
* concept definitions;
* taxonomy;
* ontology;
* external links;
* validated semantic relationships.

### Neo4j stores

* citation network;
* author collaboration network;
* recommendation scores;
* similarity edges;
* graph embeddings;
* user interactions;
* computed communities.

This avoids duplicating everything.

---

# Why not just use RDF?

RDF can technically support most of the ecosystem. You can query it with SPARQL and use graph databases that support RDF.

However, Neo4j can make certain tasks easier:

```text
Paper recommendations
Citation-path exploration
Community detection
Centrality analysis
Graph-based similarity
Interactive visualisation
Operational application queries
```

For example, you might create a computed relationship:

```text
(PaperA)-[:SIMILAR_TO {
    score: 0.87,
    method: "embedding_cosine"
}]->(PaperB)
```

This is very natural in Neo4j.

In RDF, it is also possible, but representing many computed edges and their metadata may become more verbose.

---

# Why not just use Neo4j?

Neo4j alone would let you store and explore the literature, but you would lose some semantic guarantees.

For example, your ecosystem should understand that:

```text
TCN is a DeepLearningMethod
DeepLearningMethod is a MachineLearningMethod
HumanActivityRecognition is a ClassificationTask
F1Score is an EvaluationMetric
```

With RDF/OWL, those meanings are part of the model.

With basic Neo4j, they are usually only labels and relationships created by the application. They do not automatically have standardized logical meaning.

RDF also helps prevent every extraction pipeline from inventing different names:

```text
"Random forest"
"RandomForest"
"RF"
"random-forest"
```

All can be mapped to one URI:

```text
ml:RandomForest
```

---

# A useful division of labour

| Ecosystem function            | Best suited technology                |
| ----------------------------- | ------------------------------------- |
| Ontology and vocabulary       | RDF/OWL                               |
| Paper and concept identifiers | RDF                                   |
| External links                | RDF                                   |
| Validation                    | SHACL                                 |
| Semantic inference            | RDFS/OWL                              |
| Citation-network exploration  | Neo4j                                 |
| Recommendation engine         | Neo4j                                 |
| Community detection           | Neo4j                                 |
| Centrality and path analysis  | Neo4j                                 |
| Interactive graph interface   | Neo4j                                 |
| Graph embeddings              | Either, often Neo4j/application layer |
| Question answering            | Combination of both                   |

---

# Question-answering example

Suppose the user asks:

> Which deep-learning methods have been evaluated for transportation-mode recognition, and which papers report the best unseen-user performance?

The system could work in stages.

### RDF stage

Determine semantically which methods count as deep-learning methods:

```text
TCN
LSTM
CNN
Transformer
CNN-LSTM
```

This may use subclass reasoning.

### Neo4j stage

Traverse relevant papers, experiments and datasets and rank their results:

```cypher
MATCH (p:Paper)-[:USES_METHOD]->(m:Method),
      (p)-[:HAS_EXPERIMENT]->(e:Experiment),
      (e)-[:EVALUATES_TASK]->(t:Task)
WHERE t.name = "Transportation Mode Recognition"
  AND m.semanticCategory = "Deep Learning"
  AND e.evaluationType = "Unseen User"
RETURN p.title, m.name, e.score
ORDER BY e.score DESC
```

### Language-model stage

Turn the structured results into a readable answer, with references to the source papers.

---

# The strongest version of your literature ecosystem

For your project, I would structure it into four layers:

## 1. Semantic layer

RDF, RDFS, OWL and SHACL.

It defines:

```text
What is a method?
What is a task?
What is a dataset?
What counts as an experiment?
How are metrics represented?
```

## 2. Evidence layer

Every extracted statement is connected to its source.

```text
Claim
Paper
Page
Section
Quoted passage
Extraction confidence
```

This is critical because a literature system must show where each fact came from.

## 3. Graph analytics layer

Neo4j stores or projects:

```text
citation links
paper similarity
author networks
method–task networks
dataset reuse
research communities
recommendation relationships
```

## 4. User interface / AI layer

The user asks natural-language questions.

The system translates them into:

* SPARQL for semantic questions;
* Cypher for graph-navigation questions;
* vector search for textual similarity;
* document retrieval for evidence;
* an LLM for synthesizing the final answer.

---

## Example routing

| User question                                                           | Likely system                  |
| ----------------------------------------------------------------------- | ------------------------------ |
| “What is a graph neural network?”                                       | RDF ontology + documents       |
| “Which methods are subclasses of neural models?”                        | RDF/SPARQL                     |
| “How is node2vec connected to link prediction?”                         | RDF + paper evidence           |
| “Find papers similar to this one”                                       | Neo4j + embeddings             |
| “Show the citation path between two papers”                             | Neo4j                          |
| “Who are the central authors in this topic?”                            | Neo4j graph analytics          |
| “Which methods outperform baselines on social-network link prediction?” | RDF + Neo4j + source documents |
| “What research gaps exist?”                                             | Combined analysis + LLM        |

---

The final ecosystem is therefore not simply two databases containing the same information.

It is:

> **RDF for meaning, evidence and interoperability; Neo4j for navigation, analytics and application behaviour.**
