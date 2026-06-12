import argparse
import csv
import itertools
import os
import random
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Set, Tuple
import bisect


@dataclass
class GraphCSR:
	name: str
	n: int
	id_to_idx: Dict[str, int]
	idx_to_id: List[str]
	orig_nodes: List[int]
	full_indices: List[int]
	full_index_to_local: Dict[int, int]
	offsets_out: List[int]
	edges_out: List[int]
	offsets_in: List[int]
	edges_in: List[int]
	out_sets: List[Set[int]]
	in_sets: List[Set[int]]
	indeg: List[int]
	outdeg: List[int]
	total_deg: List[int]
	color: List[int]
	color_to_nodes: Dict[int, List[int]]


def read_edge_csv(path: str) -> Tuple[List[str], List[Tuple[str, str]]]:
	ids: Set[str] = set()
	edges: List[Tuple[str, str]] = []
	with open(path, "r", newline="", encoding="utf-8") as f:
		reader = csv.reader(f)
		header = next(reader, None)
		if header is None:
			return [], []
		for row in reader:
			if len(row) < 2:
				continue
			s = row[0].strip()
			t = row[1].strip()
			if not s or not t:
				continue
			ids.add(s)
			ids.add(t)
			edges.append((s, t))
	return sorted(ids), edges


def build_graph_from_adjacency(
	name: str,
	idx_to_id: List[str],
	full_indices: List[int],
	out_neighbors: List[List[int]],
	in_neighbors: List[List[int]],
	wl_rounds: int,
) -> GraphCSR:
	n = len(idx_to_id)
	id_to_idx = {node_id: i for i, node_id in enumerate(idx_to_id)}
	full_index_to_local = {full_idx: i for i, full_idx in enumerate(full_indices)}

	offsets_out = [0] * (n + 1)
	offsets_in = [0] * (n + 1)
	edges_out: List[int] = []
	edges_in: List[int] = []
	out_sets: List[Set[int]] = [set() for _ in range(n)]
	in_sets: List[Set[int]] = [set() for _ in range(n)]

	for i in range(n):
		outs = sorted(set(out_neighbors[i]))
		ins = sorted(set(in_neighbors[i]))
		out_sets[i] = set(outs)
		in_sets[i] = set(ins)
		edges_out.extend(outs)
		edges_in.extend(ins)
		offsets_out[i + 1] = len(edges_out)
		offsets_in[i + 1] = len(edges_in)

	outdeg = [offsets_out[i + 1] - offsets_out[i] for i in range(n)]
	indeg = [offsets_in[i + 1] - offsets_in[i] for i in range(n)]
	total_deg = [indeg[i] + outdeg[i] for i in range(n)]
	color = list(total_deg)
	color_to_nodes: Dict[int, List[int]] = {}
	for v, deg in enumerate(total_deg):
		color_to_nodes.setdefault(deg, []).append(v)

	return GraphCSR(
		name=name,
		n=n,
		id_to_idx=id_to_idx,
		idx_to_id=idx_to_id,
		orig_nodes=full_indices,
		full_indices=full_indices,
		full_index_to_local=full_index_to_local,
		offsets_out=offsets_out,
		edges_out=edges_out,
		offsets_in=offsets_in,
		edges_in=edges_in,
		out_sets=out_sets,
		in_sets=in_sets,
		indeg=indeg,
		outdeg=outdeg,
		total_deg=total_deg,
		color=color,
		color_to_nodes=color_to_nodes,
	)


def build_full_graph(name: str, ids: List[str], edges: List[Tuple[str, str]]) -> GraphCSR:
	n = len(ids)
	id_to_idx = {node_id: i for i, node_id in enumerate(ids)}
	out_neighbors: List[List[int]] = [[] for _ in range(n)]
	in_neighbors: List[List[int]] = [[] for _ in range(n)]

	for s, t in edges:
		u = id_to_idx[s]
		v = id_to_idx[t]
		out_neighbors[u].append(v)
		in_neighbors[v].append(u)

	return build_graph_from_adjacency(
		name=name,
		idx_to_id=list(ids),
		full_indices=list(range(n)),
		out_neighbors=out_neighbors,
		in_neighbors=in_neighbors,
		wl_rounds=1,
	)


def neighbors_weak(g: GraphCSR, v: int) -> Set[int]:
	return g.out_sets[v] | g.in_sets[v]


def get_boundary(g: GraphCSR, selected: Set[int]) -> Set[int]:
	boundary: Set[int] = set()
	for v in selected:
		for w in neighbors_weak(g, v):
			if w not in selected:
				boundary.add(w)
	return boundary


def edge_pattern(g: GraphCSR, u: int, v: int) -> Tuple[bool, bool]:
	return (v in g.out_sets[u], u in g.out_sets[v])


def has_edge_bin(g: GraphCSR, u: int, v: int) -> bool:
	"""Binary-search based check for edge u->v using offsets/edges_out."""
	s = g.offsets_out[u]
	e = g.offsets_out[u + 1]
	i = bisect.bisect_left(g.edges_out, v, s, e)
	return i < e and g.edges_out[i] == v


def consistent_with_match(
	g1: GraphCSR,
	g2: GraphCSR,
	g3: GraphCSR,
	match: List[Tuple[int, int, int]],
	v1: int,
	v2: int,
	v3: int,
) -> bool:
	for m1, m2, m3 in match:
		if not (edge_pattern(g1, m1, v1) == edge_pattern(g2, m2, v2) == edge_pattern(g3, m3, v3)):
			return False
	return True


def check_candidate_partial(
	g1: GraphCSR,
	g2: GraphCSR,
	g3: GraphCSR,
	match: List[Tuple[int, int, int]],
	b1: int,
	b2: int,
	b3: int,
	use_bin: bool = True,
) -> bool:
	"""Check consistency only with respect to current match. Uses binary-search edge checks when use_bin=True."""
	# build mapping m1->(m2,m3)
	map1: Dict[int, Tuple[int, int]] = {m1: (m2, m3) for (m1, m2, m3) in match}
	# iterate through match; for small match sizes this is cheap
	for m1, (m2, m3) in map1.items():
		if use_bin:
			p1 = (has_edge_bin(g1, m1, b1), has_edge_bin(g1, b1, m1))
			p2 = (has_edge_bin(g2, m2, b2), has_edge_bin(g2, b2, m2))
			p3 = (has_edge_bin(g3, m3, b3), has_edge_bin(g3, b3, m3))
		else:
			p1 = (b1 in g1.out_sets[m1], m1 in g1.out_sets[b1])
			p2 = (b2 in g2.out_sets[m2], m2 in g2.out_sets[b2])
			p3 = (b3 in g3.out_sets[m3], m3 in g3.out_sets[b3])
		if not (p1 == p2 == p3):
			return False
	return True


def candidate_score(g1: GraphCSR, g2: GraphCSR, g3: GraphCSR, v1: int, v2: int, v3: int) -> int:
	return g1.total_deg[v1] + g2.total_deg[v2] + g3.total_deg[v3]


def find_core_for_triplet(
	g1: GraphCSR,
	g2: GraphCSR,
	g3: GraphCSR,
	top_k: int = 100,
	R1: int = 1000,
	rng: random.Random = random.Random(42),
) -> List[Tuple[int, int, int]]:
	"""Stage 1: search core within Top-K nodes via repeated random greedy."""
	ta = set(top_nodes_by_degree(g1, top_k))
	tb = set(top_nodes_by_degree(g2, top_k))
	tc = set(top_nodes_by_degree(g3, top_k))

	best_match: List[Tuple[int, int, int]] = []

	for r in range(R1):
		# random seed selection
		a0 = rng.choice(list(ta))
		# select b0 with degree close
		deg_a = g1.total_deg[a0]
		tol = max(5, int(0.2 * deg_a))
		cand_b = [v for v in tb if abs(g2.total_deg[v] - deg_a) <= tol]
		if not cand_b:
			continue
		b0 = rng.choice(cand_b)
		cand_c = [v for v in tc if abs(g3.total_deg[v] - deg_a) <= tol]
		if not cand_c:
			continue
		c0 = rng.choice(cand_c)

		match: List[Tuple[int, int, int]] = [(a0, b0, c0)]
		s1 = {a0}
		s2 = {b0}
		s3 = {c0}

		# greedy expand within Top sets
		while True:
			b1 = get_boundary(g1, s1) & ta
			b2 = get_boundary(g2, s2) & tb
			b3 = get_boundary(g3, s3) & tc
			if not b1 or not b2 or not b3:
				break

			found = False
			# try highest-degree boundary first
			for v1 in sorted(b1, key=lambda x: g1.total_deg[x], reverse=True):
				for v2 in sorted(b2, key=lambda x: g2.total_deg[x], reverse=True):
					if v2 in s2:
						continue
					for v3 in sorted(b3, key=lambda x: g3.total_deg[x], reverse=True):
						if v3 in s3:
							continue
						if check_candidate_partial(g1, g2, g3, match, v1, v2, v3, use_bin=True):
							match.append((v1, v2, v3))
							s1.add(v1)
							s2.add(v2)
							s3.add(v3)
							found = True
							break
					if found:
						break
				if found:
					break
			if not found:
				break

		if len(match) > len(best_match):
			best_match = match

	return best_match


def signature_for_node(g: GraphCSR, node: int, match: List[Tuple[int, int, int]], pos: int) -> Tuple[int, ...]:
	"""Compute a compact signature tuple of directions to nodes in match for a candidate node.
	pos indicates which element of match to compare against (0,1,2 for g1,g2,g3)."""
	sig = []
	for tup in match:
		m = tup[pos]
		d = 0
		if has_edge_bin(g, m, node):
			d |= 1
		if has_edge_bin(g, node, m):
			d |= 2
		sig.append(d)
	return tuple(sig)


def expand_core_to_full(
	g1: GraphCSR,
	g2: GraphCSR,
	g3: GraphCSR,
	core: List[Tuple[int, int, int]],
	target_size: int = 100,
	max_steps: int = 1000,
	L: int = 200,
	R2: int = 100,
	rng: random.Random = random.Random(43),
) -> List[Tuple[int, int, int]]:
	"""Stage 2: based on core, perform R2 randomized greedy expansions over full graphs."""
	best_overall = list(core)

	for run in range(R2):
		match = list(core)
		s1 = {m[0] for m in match}
		s2 = {m[1] for m in match}
		s3 = {m[2] for m in match}

		steps = 0
		while len(match) < target_size and steps < max_steps:
			steps += 1
			B1 = [v for v in get_boundary(g1, s1) if v not in s1 and (neighbors_weak(g1, v) & s1)]
			B2 = [v for v in get_boundary(g2, s2) if v not in s2 and (neighbors_weak(g2, v) & s2)]
			B3 = [v for v in get_boundary(g3, s3) if v not in s3 and (neighbors_weak(g3, v) & s3)]
			if not B1 or not B2 or not B3:
				break

			# limit by degree
			B1 = sorted(B1, key=lambda x: g1.total_deg[x], reverse=True)[:L]
			B2 = sorted(B2, key=lambda x: g2.total_deg[x], reverse=True)[:L]
			B3 = sorted(B3, key=lambda x: g3.total_deg[x], reverse=True)[:L]

			# build signature maps
			sig2nodes_1 = {}
			for v in B1:
				sig = signature_for_node(g1, v, match, pos=0)
				sig2nodes_1.setdefault(sig, []).append(v)
			sig2nodes_2 = {}
			for v in B2:
				sig = signature_for_node(g2, v, match, pos=1)
				sig2nodes_2.setdefault(sig, []).append(v)
			sig2nodes_3 = {}
			for v in B3:
				sig = signature_for_node(g3, v, match, pos=2)
				sig2nodes_3.setdefault(sig, []).append(v)

			found_any = False
			candidates = []
			# enumerate matches by matching signatures
			for sig, nodes1 in sig2nodes_1.items():
				if sig not in sig2nodes_2 or sig not in sig2nodes_3:
					continue
				for v1 in nodes1:
					for v2 in sig2nodes_2[sig]:
						if v2 in s2:
							continue
						for v3 in sig2nodes_3[sig]:
							if v3 in s3:
								continue
							# full verification
							if check_candidate_partial(g1, g2, g3, match, v1, v2, v3, use_bin=True):
								candidates.append((v1, v2, v3))

			if not candidates:
				break

			# choose among candidates: prefer higher score but add randomness
			candidates_sorted = sorted(candidates, key=lambda t: candidate_score(g1, g2, g3, *t), reverse=True)
			pick = None
			if len(candidates_sorted) <= 3:
				pick = rng.choice(candidates_sorted)
			else:
				top3 = candidates_sorted[:3]
				if rng.random() < 0.5:
					pick = top3[0]
				else:
					pick = rng.choice(top3)

			if pick is None:
				break

			match.append(pick)
			s1.add(pick[0])
			s2.add(pick[1])
			s3.add(pick[2])
			found_any = True

			if len(match) > len(best_overall):
				best_overall = list(match)

		# end one run
		if len(best_overall) >= target_size:
			break

	return best_overall


def top_nodes_by_degree(graph: GraphCSR, limit: int) -> List[int]:
	return sorted(range(graph.n), key=lambda x: graph.total_deg[x], reverse=True)[:limit]


def degree_range(limit_deg: int) -> int:
	return max(5, int(limit_deg * 0.2))


def collect_nodes_in_degree_window(graph: GraphCSR, degree_buckets: Dict[int, List[int]], center_deg: int) -> List[int]:
	delta = degree_range(center_deg)
	candidates: List[int] = []
	for deg in range(max(0, center_deg - delta), center_deg + delta + 1):
		candidates.extend(degree_buckets.get(deg, []))
	return sorted(set(candidates), key=lambda x: graph.total_deg[x], reverse=True)


def build_degree_buckets(graph: GraphCSR) -> Dict[int, List[int]]:
	buckets: Dict[int, List[int]] = {}
	for v, deg in enumerate(graph.total_deg):
		buckets.setdefault(deg, []).append(v)
	return buckets


def limited_degree_candidates(
	graph: GraphCSR,
	buckets: Dict[int, List[int]],
	center_deg: int,
	limit: int,
	rng: random.Random,
) -> List[int]:
	delta = degree_range(center_deg)
	candidates: List[int] = []
	for deg in range(max(0, center_deg - delta), center_deg + delta + 1):
		candidates.extend(buckets.get(deg, []))
	if not candidates:
		return []
	unique = sorted(set(candidates), key=lambda x: graph.total_deg[x], reverse=True)
	if len(unique) > limit:
		unique = rng.sample(unique, limit)
		unique.sort(key=lambda x: graph.total_deg[x], reverse=True)
	return unique


def progress_message(tag: str, current: int, total: int, detail: str = "") -> None:
	if total > 0:
		pct = 100.0 * current / total
		prefix = f"[{tag}] {current}/{total} ({pct:.1f}%)"
	else:
		prefix = f"[{tag}] {current}"
	if detail:
		prefix += f" | {detail}"
	print(prefix, flush=True)


def build_seed_candidates_degree_only(
	g1: GraphCSR,
	g2: GraphCSR,
	g3: GraphCSR,
	start_count: int,
	total_limit: int,
	pair_sample_limit: int,
	random_extra: int,
	rng: random.Random,
) -> List[Tuple[int, int, int]]:
	top1 = top_nodes_by_degree(g1, start_count)
	buckets2 = build_degree_buckets(g2)
	buckets3 = build_degree_buckets(g3)

	triads: List[Tuple[int, int, int, int]] = []
	progress_message("seed-scan", 0, len(top1), "building candidates")
	for idx1, v1 in enumerate(top1, start=1):
		d1 = g1.total_deg[v1]
		cand2 = limited_degree_candidates(g2, buckets2, d1, pair_sample_limit, rng)
		cand3 = limited_degree_candidates(g3, buckets3, d1, pair_sample_limit, rng)
		for v2 in cand2:
			for v3 in cand3:
				score = (g1.total_deg[v1] + 1) * (g2.total_deg[v2] + 1) * (g3.total_deg[v3] + 1)
				triads.append((score, v1, v2, v3))
		if len(triads) > total_limit:
			triads = sorted(triads, reverse=True)[:total_limit]
		progress_message("seed-scan", idx1, len(top1), f"candidates={len(triads)}")

	triads.sort(reverse=True)
	seeds: List[Tuple[int, int, int]] = []
	seen: Set[Tuple[int, int, int]] = set()
	for _, v1, v2, v3 in triads:
		seed = (v1, v2, v3)
		if seed in seen:
			continue
		seen.add(seed)
		seeds.append(seed)
		if len(seeds) >= total_limit:
			break

	if random_extra > 0:
		for _ in range(random_extra):
			v1 = rng.choice(top1)
			d1 = g1.total_deg[v1]
			cand2 = limited_degree_candidates(g2, buckets2, d1, pair_sample_limit, rng)
			cand3 = limited_degree_candidates(g3, buckets3, d1, pair_sample_limit, rng)
			if not cand2 or not cand3:
				continue
			seed = (v1, rng.choice(cand2), rng.choice(cand3))
			if seed not in seen:
				seen.add(seed)
				seeds.append(seed)

	return seeds


def greedy_expand_degree_only(
	g1: GraphCSR,
	g2: GraphCSR,
	g3: GraphCSR,
	seed: Tuple[int, int, int],
	target_size: int,
	boundary_limit: int,
	max_steps: int,
	seed_time_limit: float,
) -> List[Tuple[int, int, int]]:
	start_time = time.perf_counter()
	match: List[Tuple[int, int, int]] = [seed]
	s1: Set[int] = {seed[0]}
	s2: Set[int] = {seed[1]}
	s3: Set[int] = {seed[2]}
	b2_buckets = build_degree_buckets(g2)
	b3_buckets = build_degree_buckets(g3)
	progress_message("expand", 1, target_size, f"size={len(match)}")

	for _ in range(max_steps):
		if len(match) >= target_size:
			break
		if time.perf_counter() - start_time > seed_time_limit:
			progress_message("expand-timeout", len(match), target_size, f"size={len(match)}")
			break

		b1 = get_boundary(g1, s1)
		b2 = get_boundary(g2, s2)
		b3 = get_boundary(g3, s3)
		if not b1 or not b2 or not b3:
			break

		b1 = set(sorted(b1, key=lambda x: g1.total_deg[x], reverse=True)[:boundary_limit])
		b2 = set(sorted(b2, key=lambda x: g2.total_deg[x], reverse=True)[:boundary_limit])
		b3 = set(sorted(b3, key=lambda x: g3.total_deg[x], reverse=True)[:boundary_limit])

		best: Tuple[int, int, int] | None = None
		best_score = -1
		ordered_b1 = sorted(b1, key=lambda x: g1.total_deg[x], reverse=True)
		for v1 in ordered_b1:
			d1 = g1.total_deg[v1]
			cand2 = [v for v in limited_degree_candidates(g2, b2_buckets, d1, 20, random.Random(d1 + v1)) if v in b2]
			cand3 = [v for v in limited_degree_candidates(g3, b3_buckets, d1, 20, random.Random(d1 + v1 + 1)) if v in b3]
			if not cand2 or not cand3:
				continue
			ordered_cand2 = sorted(cand2, key=lambda x: g2.total_deg[x], reverse=True)
			ordered_cand3 = sorted(cand3, key=lambda x: g3.total_deg[x], reverse=True)
			for v2 in ordered_cand2:
				if v2 in s2:
					continue
				for v3 in ordered_cand3:
					if v3 in s3:
						continue
					if not check_candidate_partial(g1, g2, g3, match, v1, v2, v3, use_bin=True):
						continue
					score = candidate_score(g1, g2, g3, v1, v2, v3)
					if score > best_score:
						best_score = score
						best = (v1, v2, v3)

		if best is None:
			break

		match.append(best)
		s1.add(best[0])
		s2.add(best[1])
		s3.add(best[2])
		progress_message("expand", len(match), target_size, f"best_score={best_score}")

	return match


def search_best_greedy_match(
	g1: GraphCSR,
	g2: GraphCSR,
	g3: GraphCSR,
	seed_count: int,
	total_seed_limit: int,
	pair_sample_limit: int,
	boundary_limit: int,
	target_size: int,
	max_steps: int,
	seed_time_limit: float,
	random_extra: int,
	rng: random.Random,
) -> List[Tuple[int, int, int]]:
	seeds = build_seed_candidates_degree_only(
		g1,
		g2,
		g3,
		start_count=seed_count,
		total_limit=total_seed_limit,
		pair_sample_limit=pair_sample_limit,
	random_extra=random_extra,
	rng=rng,
	)
	best_match: List[Tuple[int, int, int]] = []
	progress_message("seed-total", 0, len(seeds), "starting search")
	for idx, seed in enumerate(seeds, start=1):
		progress_message("seed", idx, len(seeds), f"seed_deg={g1.total_deg[seed[0]]+g2.total_deg[seed[1]]+g3.total_deg[seed[2]]}")
		match = greedy_expand_degree_only(
			g1,
			g2,
			g3,
			seed,
			target_size=target_size,
			boundary_limit=boundary_limit,
			max_steps=max_steps,
			seed_time_limit=seed_time_limit,
		)
		if len(match) > len(best_match):
			best_match = match
			progress_message("best", len(best_match), target_size, f"seed={idx}")
			if len(best_match) >= target_size:
				break
	return best_match


def load_graphs_from_data(data_dir: str, names: Sequence[str]) -> Dict[str, GraphCSR]:
	graphs: Dict[str, GraphCSR] = {}
	for name in names:
		path = os.path.join(data_dir, f"{name}.csv")
		ids, edges = read_edge_csv(path)
		graphs[name] = build_full_graph(name, ids, edges)
	return graphs


def save_result_csv(
	output_path: str,
	names: Tuple[str, str, str],
	match: List[Tuple[int, int, int]],
	graphs: Dict[str, GraphCSR],
) -> None:
	g1 = graphs[names[0]]
	g2 = graphs[names[1]]
	g3 = graphs[names[2]]
	with open(output_path, "w", newline="", encoding="utf-8") as f:
		writer = csv.writer(f)
		writer.writerow([names[0], names[1], names[2]])
		for v1, v2, v3 in match:
			writer.writerow([g1.idx_to_id[v1], g2.idx_to_id[v2], g3.idx_to_id[v3]])


def triplet_filename(triplet: Tuple[str, str, str]) -> str:
	parts = [x.replace("/", "_").replace("\\", "_").replace(",", "_") for x in triplet]
	return "__".join(parts) + ".csv"


def run_degree_greedy_search_for_triplet(
	full1: GraphCSR,
	full2: GraphCSR,
	full3: GraphCSR,
	seed_count: int,
	total_seed_limit: int,
	pair_sample_limit: int,
	boundary_limit: int,
	target_size: int,
	max_steps: int,
	seed_time_limit: float,
	random_extra: int,
	rng: random.Random,
) -> List[Tuple[int, int, int]]:
	return search_best_greedy_match(
		full1,
		full2,
		full3,
		seed_count=seed_count,
		total_seed_limit=total_seed_limit,
		pair_sample_limit=pair_sample_limit,
		boundary_limit=boundary_limit,
		target_size=target_size,
		max_steps=max_steps,
		seed_time_limit=seed_time_limit,
		random_extra=random_extra,
		rng=rng,
	)


def main() -> None:
	parser = argparse.ArgumentParser(description="Two-stage approximate common induced subgraph search on 5 directed graphs")
	parser.add_argument("--data-dir", default="data", help="Directory containing a.csv,b.csv,c.csv,d.csv,e.csv")
	# parser.add_argument("--graphs", default="a,b,c,d,e", help="Graph names to search, comma separated")
	parser.add_argument("--graphs", default="banc_626_edge_list,fafb_783_edge_list,manc_1.2.1_edge_list,maol_1.1_edge_list,mcns_0.9_edge_list", help="Graph names to search, comma separated")
	parser.add_argument("--seed-count", type=int, default=100, help="Number of high-degree nodes in graph 1 for seed scanning")
	parser.add_argument("--seed-limit", type=int, default=1, help="Number of seeds to keep for actual expansion")
	parser.add_argument("--pair-sample-limit", type=int, default=100, help="Maximum nodes kept per side when generating candidates for each start node")
	parser.add_argument("--top-k", type=int, default=100, help="Select top-K high-frequency nodes in each graph for core search")
	parser.add_argument("--R1", type=int, default=1000, help="Number of random greedy repeats in first stage")
	parser.add_argument("--R2", type=int, default=100, help="Number of expansion repeats per core in second stage")
	parser.add_argument("--L", type=int, default=200, help="Maximum number of boundary nodes considered per graph per round")
	parser.add_argument("--boundary-limit", type=int, default=30, help="Upper limit of boundary nodes kept per expansion")
	parser.add_argument("--target-size", type=int, default=100, help="Stop current seed when reaching this size")
	parser.add_argument("--max-steps", type=int, default=200, help="Maximum expansion steps per seed")
	parser.add_argument("--seed-time-limit", type=float, default=10.0, help="Time limit (seconds) per seed")
	parser.add_argument("--random-extra", type=int, default=100, help="Number of extra random seeds")
	parser.add_argument("--seed", type=int, default=42, help="Random seed")
	parser.add_argument("--output-dir", default="matches", help="Output directory for each triplet result")
	parser.add_argument("--best-output", default="best_match.csv", help="Path to the aggregated best result CSV")
	args = parser.parse_args()

	graph_names = [x.strip() for x in args.graphs.split(",") if x.strip()]
	if len(graph_names) < 3:
		raise ValueError("At least 3 graphs are required")

	rng = random.Random(args.seed)
	graphs = load_graphs_from_data(args.data_dir, graph_names)
	os.makedirs(args.output_dir, exist_ok=True)

	best_triplet: Tuple[str, str, str] | None = None
	best_match: List[Tuple[int, int, int]] = []

	for triplet in itertools.combinations(graph_names, 3):
		g1 = graphs[triplet[0]]
		g2 = graphs[triplet[1]]
		g3 = graphs[triplet[2]]

		# Stage 1: find core within Top-K
		core = find_core_for_triplet(g1, g2, g3, top_k=args.top_k, R1=args.R1, rng=rng)
		print(f"triplet={triplet}, core_size={len(core)}")

		if len(core) >= args.target_size:
			cur = core
		else:
			# Stage 2: expand core to full graph
			cur = expand_core_to_full(
				g1,
				g2,
				g3,
				core,
				target_size=args.target_size,
				max_steps=args.max_steps,
				L=args.L,
				R2=args.R2,
				rng=rng,
			)

		print(f"triplet={triplet}, match_size={len(cur)}")
		out_path = os.path.join(args.output_dir, triplet_filename(triplet))
		save_result_csv(out_path, triplet, cur, graphs)
		print(f"saved={out_path}")
		if len(cur) > len(best_match):
			best_match = cur
			best_triplet = triplet

	if best_triplet is None:
		raise RuntimeError("Failed to find a valid triplet")

	try:
		save_result_csv(args.best_output, best_triplet, best_match, graphs)
		print(f"result_saved={args.best_output}")
	except PermissionError as exc:
		print(f"best_output_skip={args.best_output}, reason={exc}")
	print(f"best_triplet={best_triplet}, best_size={len(best_match)}")


if __name__ == "__main__":
	main()