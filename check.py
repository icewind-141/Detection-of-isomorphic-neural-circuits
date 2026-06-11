import csv
import sys
from collections import defaultdict

def load_graph(csv_path):
    """加载有向图，返回节点集合和边集合（元组 (src, dst)）"""
    edges = set()
    nodes = set()
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)  # 跳过表头 "source neuron id,target neuron id"
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
    # 读取 best_match.csv
    with open(match_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        if len(header) < 3:
            print("Error: best_match.csv 第一行至少需要三个数据集名称")
            return
        ds_names = [h.strip() for h in header[:3]]   # dataset_A, dataset_B, dataset_C
        
        # 读取节点对应关系
        triples = []
        for row in reader:
            if len(row) < 3:
                continue
            triples.append((row[0].strip(), row[1].strip(), row[2].strip()))
    
    if not triples:
        print("No matching triples found.")
        return
    
    # 加载三个数据集的图
    graphs = []
    for ds in ds_names:
        csv_file = f"{data_dir}/{ds}.csv"   # 假设文件名如 a.csv, b.csv
        try:
            nodes, edges = load_graph(csv_file)
            graphs.append((nodes, edges))
        except FileNotFoundError:
            print(f"Error: 找不到文件 {csv_file}")
            return
    
    # 提取每个数据集对应的节点列表（按 triples 顺序）
    node_lists = []
    for idx in range(3):
        node_lists.append([triple[idx] for triple in triples])
    
    # 检查所有节点是否存在于对应的图中
    for i, (nodes, _) in enumerate(graphs):
        for node in node_lists[i]:
            if node not in nodes:
                print(f"Error: 节点 {node} 不在数据集 {ds_names[i]} 中")
                return
    
    N = len(triples)
    inconsistent_nodes = set()
    
    # 检查所有节点对之间的边一致性
    for i in range(N):
        for j in range(i+1, N):
            # 三个数据集中的对应节点对
            a1, b1, c1 = triples[i]
            a2, b2, c2 = triples[j]
            
            # 检查六种可能的边方向（每个数据集内两个方向）
            # 分别检查 a1->a2, a2->a1; b1->b2, b2->b1; c1->c2, c2->c1
            # 要求三个数据集中边存在性完全相同
            
            # 获取每个数据集的边集
            edges_a = graphs[0][1]
            edges_b = graphs[1][1]
            edges_c = graphs[2][1]
            
            # 定义函数检查某方向边是否存在
            def exists(edges, src, dst):
                return (src, dst) in edges
            
            # 检查 a1->a2
            a_forward = exists(edges_a, a1, a2)
            b_forward = exists(edges_b, b1, b2)
            c_forward = exists(edges_c, c1, c2)
            if not (a_forward == b_forward == c_forward):
                inconsistent_nodes.add(i)
                inconsistent_nodes.add(j)
                continue
            
            # 检查 a2->a1
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
        # 输出每个不一致节点的三元组，按 triples 中的顺序
        # 注意 inconsistent_nodes 是索引集合，需要排序以稳定输出
        for idx in sorted(inconsistent_nodes):
            print(f"{triples[idx][0]}, {triples[idx][1]}, {triples[idx][2]}")

if __name__ == "__main__":
    # 用法：python check.py [best_match.csv] [data_dir]
    if len(sys.argv) >= 2:
        match_file = sys.argv[1]
        data_dir = sys.argv[2] if len(sys.argv) >= 3 else 'data'
    else:
        match_file = 'best_match_better5.csv'
        data_dir = 'data'
    check_isomorphism(match_file, data_dir)