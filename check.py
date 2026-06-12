import csv
import sys
from collections import defaultdict

def load_graph(csv_path):
    """Load directed graph, return node set and edge set (tuple (src, dst))."""
    edges = set()
    nodes = set()
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header "source neuron id,target neuron id"
        for row in reader:
            if len(row) < 2:
                continue
            src = row[0].strip()
            dst = row[1].strip()
            edges.add((src, dst))
            nodes.add(src)
            nodes.add(dst)
    return nodes, edges

def check_isomorphism(match_file, data_dir='data'):
    # Read best_match.csv
    with open(match_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        if len(header) < 3:
            print("Error: best_match.csv first line requires at least three dataset names")
            return
        ds_names = [h.strip() for h in header[:3]]   # dataset_A, dataset_B, dataset_C
        
        # Read node correspondences
        triples = []
        for row in reader:
            if len(row) < 3:
                continue
            triples.append((row[0].strip(), row[1].strip(), row[2].strip()))
    
    if not triples:
        print("No matching triples found.")
        return
    
    # Load graphs for all three datasets
    graphs = []
    for ds in ds_names:
        csv_file = f"{data_dir}/{ds}.csv"   # Assume file names like a.csv, b.csv
        try:
            nodes, edges = load_graph(csv_file)
            graphs.append((nodes, edges))
        except FileNotFoundError:
            print(f"Error: File not found {csv_file}")
            return
    
    # Extract node lists for each dataset (in the order of triples)
    node_lists = []
    for idx in range(3):
        node_lists.append([triple[idx] for triple in triples])
    
    # Check if all nodes exist in their corresponding graphs
    for i, (nodes, _) in enumerate(graphs):
        for node in node_lists[i]:
            if node not in nodes:
                print(f"Error: Node {node} is not in dataset {ds_names[i]}")
                return
    
    N = len(triples)
    inconsistent_nodes = set()
    
    # Check consistency of edges between all pairs of nodes in the triples
    for i in range(N):
        for j in range(i+1, N):
            # Corresponding node pairs in the three datasets
            a1, b1, c1 = triples[i]
            a2, b2, c2 = triples[j]
            
            # Check six possible edge directions (two directions in each dataset)
            # Check a1->a2, a2->a1; b1->b2, b2->b1; c1->c2, c2->c1
            # Require edge existence to be identical across three datasets
            
            # Get edge set of each dataset
            edges_a = graphs[0][1]
            edges_b = graphs[1][1]
            edges_c = graphs[2][1]
            
            # Define function to check existence of an edge in a given direction
            def exists(edges, src, dst):
                return (src, dst) in edges
            
            # Check a1->a2
            a_forward = exists(edges_a, a1, a2)
            b_forward = exists(edges_b, b1, b2)
            c_forward = exists(edges_c, c1, c2)
            if not (a_forward == b_forward == c_forward):
                inconsistent_nodes.add(i)
                inconsistent_nodes.add(j)
                continue
            
            # Check a2->a1
            a_backward = exists(edges_a, a2, a1)
            b_backward = exists(edges_b, b2, b1)
            c_backward = exists(edges_c, c2, c1)
            if not (a_backward == b_backward == c_backward):
                inconsistent_nodes.add(i)
                inconsistent_nodes.add(j)
                continue
    
    if not inconsistent_nodes:
        print("yes")
    else:
        x = len(inconsistent_nodes)
        print(x)
        # Output triple of each inconsistent node, in the order of triples
        # Note: inconsistent_nodes is a set of indices, need to sort for stable output
        for idx in sorted(inconsistent_nodes):
            print(f"{triples[idx][0]}, {triples[idx][1]}, {triples[idx][2]}")

if __name__ == "__main__":
    # Usage: python check.py [best_match.csv] [data_dir]
    if len(sys.argv) >= 2:
        match_file = sys.argv[1]
        data_dir = sys.argv[2] if len(sys.argv) >= 3 else 'data'
    else:
        match_file = 'best_match_better5.csv'
        data_dir = 'data'
    check_isomorphism(match_file, data_dir)