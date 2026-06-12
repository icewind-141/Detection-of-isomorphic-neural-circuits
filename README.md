# Weakly Connected Common Subgraph Search Across Multiple Connectomes

## Overview

This project addresses the task:

> **Find a weakly connected common isomorphic subgraph of size 100–1000 shared by at least three connectome datasets.**

Because exact maximum common subgraph search is NP-hard and the datasets contain a very large number of neurons, exhaustive search is computationally infeasible. Our approach therefore focuses on finding **large biologically meaningful common subgraphs efficiently**, rather than guaranteeing global optimality.

The algorithm consists of two stages:

1. **Hub-based Seed Alignment**

   * Rapidly identify a small set of highly reliable aligned neurons.
   * Construct an initial common core subgraph.

2. **Greedy Expansion**

   * Expand the aligned core into a larger weakly connected common subgraph.
   * Continue until no further valid extensions exist or the target size is reached.

The key idea is that biological neural networks contain a small number of highly connected **hub neurons**, which provide strong structural signatures for alignment across datasets.

---

## Technical Strategy

### Biological Motivation

Unlike random graphs, connectomes exhibit strong degree heterogeneity:

* Most neurons have relatively few connections.
* A small number of neurons act as hubs and possess exceptionally large degrees.

These hub neurons are highly distinctive. If two neurons both occupy hub positions in different connectomes, they are significantly more likely to correspond to one another than a randomly chosen neuron pair.

Therefore, rather than searching over the entire graph immediately, we first restrict attention to a small set of high-degree neurons and attempt to identify reliable alignments among them.

This dramatically reduces the search space while increasing the probability of finding biologically meaningful correspondences.

---

## Assumptions

The algorithm relies on the following assumptions:

#### 1. Structural Consistency

The target subgraph preserves adjacency relationships across datasets.

Specifically, if two matched neurons are connected in one graph, the corresponding matched neurons must exhibit the same directed connectivity pattern in the other graphs.

#### 2. Hub Preservation

Highly connected neurons tend to remain highly connected across related connectomes.

Therefore degree information can be used as a heuristic for discovering initial alignments.

#### 3. Local Expansion Validity

Once a small set of correct alignments is found, neighboring neurons are more likely to have corresponding matches nearby.

This allows the search to expand outward from an aligned core.

---

## Methodology

### Stage 0: Graph Preprocessing

For each dataset:

* Read the directed edge list.
* Build incoming and outgoing adjacency lists.
* Compute

[
deg(v)=in_degree(v)+out_degree(v)
]

for every neuron.

* Store original neuron identifiers for output.



### Stage 1: Hub-Based Seed Alignment

#### Step 1.1: Select Candidate Hub Neurons

For each graph:

* Rank neurons by total degree.
* Select the top 100 highest-degree neurons.

These Top-100 neurons form a compact induced subgraph that retains much of the graph's distinctive structure while reducing the search space by several orders of magnitude.

#### Why Top-100?

Searching directly over all neurons would generate an enormous number of possible alignments.

Instead, we exploit a connectome-specific property:

> Hub neurons are far more likely to represent true correspondences than randomly selected neurons.

Restricting the search to the Top-100 hubs substantially increases the probability of discovering genuine alignments rather than accidental graph isomorphisms.



#### Step 1.2: Randomized Core Search

For each triple of datasets:

1. Randomly select a seed neuron from one graph.
2. Choose neurons with similar degree in the other two graphs.
3. Form an initial matched triplet.
4. Greedily add additional triplets whose edge relationships to the current matched set are identical across all three graphs.
5. Repeat many independent restarts.

The largest aligned structure found becomes the **seed core**.

The objective of this stage is not to obtain the final answer, but rather to identify several highly reliable aligned neurons that can serve as anchors for later expansion.



### Stage 2: Global Expansion

Starting from the aligned core:

1. Maintain the matched neuron sets in each graph.
2. Track boundary neurons adjacent to the current subgraph.
3. Search for new neuron triplets whose connectivity pattern with the existing matched nodes is identical across all datasets.
4. Add valid matches and update the boundary.
5. Repeat until no valid extension exists.

This stage expands the search from a small trusted core into the full graph.



### Graph Matching Heuristic

To accelerate candidate generation, each boundary neuron is represented by a connectivity signature describing its relationships to already matched neurons:

* outgoing edge
* incoming edge
* bidirectional edge
* no edge

Neurons sharing the same signature are grouped together.

Only candidates with matching signatures are compared directly.

This reduces the number of expensive exact consistency checks.



### Randomized Search Strategy

The search is intentionally randomized.

When multiple valid expansions exist:

* higher-degree candidates are preferred,
* but random selection is also introduced.

This prevents the algorithm from becoming trapped in poor local optima.

Multiple independent runs are performed, and the largest discovered subgraph is retained.

---

## Heuristics Used

The algorithm employs several heuristics:

| Heuristic                         | Purpose                                 |
|  |  |
| Top-100 hub filtering             | Reduce search space dramatically        |
| Degree similarity matching        | Generate plausible initial alignments   |
| Random restarts                   | Escape local optima                     |
| Connectivity signatures (hashing) | Accelerate candidate generation         |
| Boundary-only expansion           | Focus search on weakly connected growth |
| Degree-biased selection           | Favor structurally informative neurons  |

These heuristics sacrifice theoretical optimality in exchange for practical scalability.

---

## Reproducing Results

### Directory Structure

```text
project/
├── .gitattributes
├── best_match.csv                # Preliminary results
├── best_match_better1.csv        # Intermediate results (for expansion purposes)
├── best_match_better2.csv        
├── best_match_better3.csv        
├── best_match_better4.csv        
├── best_match_better5.csv        
├── network.csv                   # Final result
├── code.py
├── check.py
├── science.md                    # Scientific summary
├── science.pdf                   # Scientific summary
├── extend_graph_code.py
├── transform_network.csv # Transform final result, for copying to the Codex
├── data/
│   ├── a.csv                     # These are the testing input
│   ├── b.csv
│   ├── c.csv
│   ├── d.csv
│   ├── e.csv
│   ├── banc_626_edge_list.csv    # These are the true input
│   ├── fafb_783_edge_list.csv
│   ├── manc_1.2.1_edge_list.csv
│   ├── maol_1.1_edge_list.csv
│   └── mcns_0.9_edge_list.csv
├── docs/                         # Figures for the scientific summary
├── matches/
│   ├── banc_626_edge_list__fafb_783_edge_list__manc_1.2.1_edge_list.csv    # These are the core matching neurons under those three dataset in the filename
│   ├── banc_626_edge_list__fafb_783_edge_list__maol_1.1_edge_list.csv
│   ├── banc_626_edge_list__fafb_783_edge_list__mcns_0.9_edge_list.csv
│   ├── banc_626_edge_list__manc_1.2.1_edge_list__maol_1.1_edge_list.csv
│   ├── banc_626_edge_list__manc_1.2.1_edge_list__mcns_0.9_edge_list.csv
│   ├── banc_626_edge_list__maol_1.1_edge_list__mcns_0.9_edge_list.csv
│   ├── fafb_783_edge_list__manc_1.2.1_edge_list__maol_1.1_edge_list.csv
│   ├── fafb_783_edge_list__manc_1.2.1_edge_list__mcns_0.9_edge_list.csv
│   ├── fafb_783_edge_list__maol_1.1_edge_list__mcns_0.9_edge_list.csv
│   └── manc_1.2.1_edge_list__maol_1.1_edge_list__mcns_0.9_edge_list.csv
└── README.md
```



### Run Main Search

```bash
python code.py
```



### Validate Result

```bash
python check.py best_match.csv data
```

A successful validation prints:

```text
yes
```

indicating that all matched triplets satisfy edge-consistency constraints.



### Optional Post-Expansion

To further enlarge a discovered subgraph:

```bash
python extend_graph_code.py --data-dir ./data --best-match best_match.csv --output best_match_better1.csv
python extend_graph_code.py --data-dir ./data --best-match best_match_better1.csv --output best_match_better2.csv
python extend_graph_code.py --data-dir ./data --best-match best_match_better2.csv --output best_match_better3.csv
python extend_graph_code.py --data-dir ./data --best-match best_match_better3.csv --output best_match_better4.csv
python extend_graph_code.py --data-dir ./data --best-match best_match_better4.csv --output best_match_better5.csv
python extend_graph_code.py --data-dir ./data --best-match best_match_better5.csv --output network.csv
```

This script repeatedly restarts from randomly selected subsets of the current solution and attempts additional greedy expansions.


### Validate Final Result 

```bash
python check.py network.csv data
```

A successful validation prints:

```text
yes
```

indicating that all matched triplets satisfy edge-consistency constraints.

---
## Computational Complexity

#### Stage 1

Search is restricted to Top-100 hub neurons.

This dramatically reduces complexity and typically completes within minutes.

#### Stage 2

Expansion cost depends primarily on:

* graph size
* boundary size
* number of randomized restarts

Typical runtime ranges from minutes to hours depending on parameter settings.

---

## Summary

The central idea of this work is:

> **First identify a small number of highly reliable aligned hub neurons, then use these anchors to guide expansion toward a large common weakly connected subgraph.**

By exploiting the unique hub structure of biological connectomes, the algorithm searches a dramatically smaller space than generic graph-isomorphism approaches, making large-scale common subgraph discovery computationally practical while still producing biologically plausible alignments.
