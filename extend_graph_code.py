import csv
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Sequence, Set, Tuple


@dataclass
class Graph:
	name: str
	out: Dict[str, Set[str]]
	in_: Dict[str, Set[str]]
	deg: Dict[str, int]


def read_graph_csv(path: str, name: str) -> Graph:
	out: Dict[str, Set[str]] = {}
	in_: Dict[str, Set[str]] = {}

	with open(path, "r", newline="", encoding="utf-8") as f:
		reader = csv.reader(f)
		next(reader, None)
		for row in reader:
			if len(row) < 2:
				continue
			s = row[0].strip()
			t = row[1].strip()
			if not s or not t:
				continue
			out.setdefault(s, set()).add(t)
			in_.setdefault(t, set()).add(s)
			out.setdefault(t, set())
			in_.setdefault(s, set())

	all_nodes = set(out.keys()) | set(in_.keys())
	deg = {u: len(out.get(u, set())) + len(in_.get(u, set())) for u in all_nodes}
	return Graph(name=name, out=out, in_=in_, deg=deg)


def weak_neighbors(g: Graph, u: str) -> Set[str]:
	return g.out.get(u, set()) | g.in_.get(u, set())


def edge_pattern(g: Graph, u: str, v: str) -> Tuple[bool, bool]:
	return (v in g.out.get(u, set()), u in g.out.get(v, set()))


def read_best_match(path: str) -> Tuple[Tuple[str, str, str], List[Tuple[str, str, str]]]:
	with open(path, "r", newline="", encoding="utf-8") as f:
		reader = csv.reader(f)
		header = next(reader)
		if header is None or len(header) < 3:
			raise ValueError("best_match.csv 第一行必须包含三个数据集名称")
		names = (header[0].strip(), header[1].strip(), header[2].strip())
		rows: List[Tuple[str, str, str]] = []
		for row in reader:
			if len(row) < 3:
				continue
			rows.append((row[0].strip(), row[1].strip(), row[2].strip()))
	return names, rows


def consistent_with_match(
	g1: Graph,
	g2: Graph,
	g3: Graph,
	match: Sequence[Tuple[str, str, str]],
	v1: str,
	v2: str,
	v3: str,
) -> bool:
	for m1, m2, m3 in match:
		p1 = edge_pattern(g1, m1, v1)
		p2 = edge_pattern(g2, m2, v2)
		p3 = edge_pattern(g3, m3, v3)
		if not (p1 == p2 == p3):
			return False
	return True


def get_boundary(g: Graph, used: Set[str]) -> Set[str]:
	b: Set[str] = set()
	for u in used:
		for v in weak_neighbors(g, u):
			if v not in used:
				b.add(v)
	return b


def try_expand_once(
	g1: Graph,
	g2: Graph,
	g3: Graph,
	seed_match: List[Tuple[str, str, str]],
	rng: random.Random,
	max_steps: int = 100,
	attempts_per_step: int = 200,
) -> List[Tuple[str, str, str]]:
	match = list(seed_match)
	used1 = {x[0] for x in match}
	used2 = {x[1] for x in match}
	used3 = {x[2] for x in match}

	for _ in range(max_steps):
		b1 = list(get_boundary(g1, used1))
		b2 = list(get_boundary(g2, used2))
		b3 = list(get_boundary(g3, used3))
		if not b1 or not b2 or not b3:
			break

		valid: List[Tuple[str, str, str]] = []
		for _ in range(attempts_per_step):
			v1 = rng.choice(b1)
			v2 = rng.choice(b2)
			v3 = rng.choice(b3)
			if v1 in used1 or v2 in used2 or v3 in used3:
				continue
			if consistent_with_match(g1, g2, g3, match, v1, v2, v3):
				valid.append((v1, v2, v3))

		if not valid:
			break

		# 50%选最好，50%随机选top3，平衡贪心与随机探索
		valid = sorted(
			valid,
			key=lambda t: g1.deg.get(t[0], 0) + g2.deg.get(t[1], 0) + g3.deg.get(t[2], 0),
			reverse=True,
		)
		# topk = valid[: min(3, len(valid))]
		topk = valid[: min(9, len(valid))]
		pick = topk[0] if rng.random() < 0.5 else rng.choice(topk)

		match.append(pick)
		used1.add(pick[0])
		used2.add(pick[1])
		used3.add(pick[2])

	return match


def write_match(path: str, names: Tuple[str, str, str], match: Sequence[Tuple[str, str, str]]) -> None:
	with open(path, "w", newline="", encoding="utf-8") as f:
		writer = csv.writer(f)
		writer.writerow([names[0], names[1], names[2]])
		for a, b, c in match:
			writer.writerow([a, b, c])


def main() -> None:
	data_dir = "data"
	best_match_path = "best_match_best.csv"
	output_path = "best_match_best.csv"

	rng = random.Random(42)

	# 按要求先读取5个基础csv
	# base_names = ["a", "b", "c", "d", "e"]
	base_names = ["banc_626_edge_list", "fafb_783_edge_list", "manc_1.2.1_edge_list", "maol_1.1_edge_list", "mcns_0.9_edge_list"]
	graphs: Dict[str, Graph] = {}
	for name in base_names:
		path = os.path.join(data_dir, f"{name}.csv")
		if os.path.exists(path):
			graphs[name] = read_graph_csv(path, name)

	names, base_match = read_best_match(best_match_path)
	if len(base_match) < 5:
		raise ValueError("best_match.csv 行数不足5，无法抽取5~9个点作为初始子图")

	# 根据 best_match 第一行选取相应数据；如未预加载则补充读取
	for name in names:
		if name not in graphs:
			path = os.path.join(data_dir, f"{name}.csv")
			if not os.path.exists(path):
				raise FileNotFoundError(f"找不到图文件: {path}")
			graphs[name] = read_graph_csv(path, name)

	g1 = graphs[names[0]]
	g2 = graphs[names[1]]
	g3 = graphs[names[2]]

	best = list(base_match)

	# 外层：每次重新随机选一个5~9点原始子图。
	# 内层：从该原始子图出发，做30~50次独立随机贪心扩张（每次最多100步），取该种子下最好结果。
	seed_rounds = 10000
	best_seed_size = 0
	best_restarts = 0

	for i in range(seed_rounds):
		seed_size = min(rng.randint(3, 9), len(base_match))
		original_seed = rng.sample(base_match, seed_size)
		restarts = 100

		best_for_seed = list(original_seed)
		for _ in range(restarts):
			cur = try_expand_once(g1, g2, g3, original_seed, rng, max_steps=100, attempts_per_step=200)
			if len(cur) > len(best_for_seed):
				best_for_seed = cur

		if len(best_for_seed) > len(best):
			best = best_for_seed
			best_seed_size = seed_size
			best_restarts = restarts

		if i % 50 == 0:
			write_match(output_path, names, best)
			print(
				f"Round {i}/{seed_rounds}, current best size={len(best)}, "
				f"seed_size={seed_size}, best_seed_size={best_seed_size}, best_restarts={best_restarts}"
			)

	write_match(output_path, names, best)
	print(
		f"input={best_match_path}, output={output_path}, seed_rounds={seed_rounds}, "
		f"best_seed_size={best_seed_size}, best_restarts={best_restarts}, max_steps=100, size={len(best)}"
	)


if __name__ == "__main__":
	main()
