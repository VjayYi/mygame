"""武器容积轮廓 v0.30：按武器外形画格子，27 个（9 品类 × 改装/均衡/强攻）格数与 v0.24 容积一一对应。

参数化生成 + 按格数搜索；'#' 为可用格，'.' 为缺口。轮廓朝向：剑/刀/枪/炮横放，爪/斧/拳套/弓竖放。
"""
# ruff: noqa: E501
VOLUME = {
    "刀": (26, 18, 12), "剑": (27, 19, 13), "爪": (25, 17, 11), "斧": (24, 16, 10), "拳套": (25, 17, 11),
    "步枪": (26, 18, 12), "炮筒": (24, 16, 10), "手枪": (27, 19, 13), "弓": (27, 19, 13),
}
FORMS = ("改装", "均衡", "强攻")


def norm(cells):
    mr = min(r for r, _ in cells)
    mc = min(c for _, c in cells)
    return {(r - mr, c - mc) for r, c in cells}


def connected(cells):
    if not cells:
        return False
    start = next(iter(cells))
    seen, st = {start}, [start]
    while st:
        r, c = st.pop()
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (r + d[0], c + d[1])
            if n in cells and n not in seen:
                seen.add(n)
                st.append(n)
    return len(seen) == len(cells)


def rows_of(cells):
    cells = norm(cells)
    h = max(r for r, _ in cells) + 1
    w = max(c for _, c in cells) + 1
    return ["".join("#" if (r, c) in cells else "." for c in range(w)) for r in range(h)]


# ---------------------------------------------------------------- 各武器生成器：返回 (cells, 说明)
def sword(guard_h, pommel, grip, bw, length, tip):
    mid = guard_h // 2
    cells = set()
    c = 0
    if pommel:
        cells.add((mid, c))
        c += 1
    for _ in range(grip):
        cells.add((mid, c))
        c += 1
    for r in range(guard_h):
        cells.add((r, c))
    c += 1
    top = mid - bw // 2
    for k in range(length):
        for r in range(top, top + bw):
            cells.add((r, c + k))
    if tip:
        cells.add((mid, c + length))
    return cells


def knife(grip, guard, blade_h, length, tip):
    cells = set()
    c = 0
    for _ in range(grip):
        for r in (1, 2):
            cells.add((r, c))
        c += 1
    if guard:
        for r in range(4):
            cells.add((r, c))
        c += 1
    for k in range(length):
        for r in range(blade_h):
            cells.add((r, c + k))
    if tip:
        for r in (1, 2):
            cells.add((r, c + length))
    return cells


def claw(fingers, finger_w, finger_h, palm_h, gap, thumb):
    """爪：几根并排的爪尖（每根宽 finger_w、高 finger_h）+ 下面一整块掌。gap=指间空隙。"""
    cells = set()
    w = fingers * finger_w + (fingers - 1) * gap
    for i in range(fingers):
        c0 = i * (finger_w + gap)
        for r in range(finger_h):
            for c in range(c0, c0 + finger_w):
                cells.add((r, c))
    for r in range(finger_h, finger_h + palm_h):
        for c in range(w):
            cells.add((r, c))
    if thumb:
        cells.add((finger_h + 1, -1))
    return cells


def axe(head_w, head_h, edge, handle_len):
    cells = set()
    off = 1 if edge else 0
    for r in range(head_h):
        for c in range(head_w):
            cells.add((r + 1, c + off))
    if edge:
        for r in range(head_h + 2):
            cells.add((r, 0))
    hc = off + head_w - 2
    for k in range(handle_len):
        cells.add((head_h + 1 + k + (0 if edge else 0), hc))
    return cells


def fist(body_w, body_h, knuckles, cuff_w, cuff_h, thumb):
    cells = set()
    k = (body_w + 1) // 2 if knuckles else 0
    top = 1 if knuckles else 0
    for c in range(0, body_w, 2):
        if knuckles:
            cells.add((0, c))
    for r in range(body_h):
        for c in range(body_w):
            cells.add((top + r, c))
    cx = (body_w - cuff_w) // 2
    for r in range(cuff_h):
        for c in range(cuff_w):
            cells.add((top + body_h + r, cx + c))
    if thumb:
        cells.add((top + 1, -1))
    _ = k
    return cells


def rifle(stock, body, barrel, barrel_t, mag):
    cells = set()
    for c in range(stock + body):
        cells.add((0, c))
        cells.add((1, c))
    for k in range(barrel):
        for r in range(barrel_t):
            cells.add((r, stock + body + k))
    for m in range(mag):
        cells.add((2 + m, stock + 1))
    return cells


def cannon(breech_w, breech_h, barrel_len, barrel_h, muzzle_h):
    big = max(breech_h, muzzle_h, barrel_h)
    mid = big // 2
    cells = set()
    c = 0

    def col(h, cc):
        for r in range(mid - h // 2, mid - h // 2 + h):
            cells.add((r, cc))

    for _ in range(breech_w):
        col(breech_h, c)
        c += 1
    for _ in range(barrel_len):
        col(barrel_h, c)
        c += 1
    col(muzzle_h, c)
    return cells


def pistol(slide, grip, trigger):
    cells = set()
    for c in range(slide):
        cells.add((0, c))
        cells.add((1, c))
    for k in range(grip):
        cells.add((2 + k, 0))
        cells.add((2 + k, 1))
    if trigger:
        cells.add((2, 2))
    return cells


def bow(h, thick, depth, gap, strlen):
    """弓：h 行；弓臂是向左凸出的粗弧（thick 宽、凸 depth 格），右侧是中段为 strlen 的弦，弦两端与弧相接。"""
    half = (h - 1) / 2
    starts = [round(depth * (((i - half) / half) ** 2)) for i in range(h)]
    cells = set()
    for i, st in enumerate(starts):
        for c in range(st, st + thick):
            cells.add((i, c))
    sc = max(starts) + thick + gap
    top = (h - strlen) // 2
    for i in range(top, top + strlen):
        cells.add((i, sc))
    for i in (top, top + strlen - 1):
        for c in range(starts[i] + thick, sc):
            cells.add((i, c))
    return cells


BOW13 = {(0, 1), (0, 2), (1, 0), (1, 1), (1, 3), (2, 0), (2, 1), (2, 3), (3, 0), (3, 1), (3, 3), (4, 1), (4, 2)}


def fit(rows, n):
    """把字符画模板收缩/扩张到恰好 n 格：先去邻居最少的角格（保持连通），不够再补邻居最多的格。"""
    cells = {(r, c) for r, row in enumerate(rows) for c, ch in enumerate(row) if ch == "#"}
    nb = ((1, 0), (-1, 0), (0, 1), (0, -1))

    def deg(p, cs):
        return sum((p[0] + d[0], p[1] + d[1]) in cs for d in nb)

    for _ in range(200):
        if len(cells) == n:
            break
        if len(cells) > n:
            order = sorted(cells, key=lambda p: (deg(p, cells), p))
            for p in order:
                rest = cells - {p}
                if connected(rest):
                    cells = rest
                    break
        else:
            cand = {(r + d[0], c + d[1]) for r, c in cells for d in nb} - cells
            cand = {p for p in cand if p[0] >= 0 and p[1] >= 0}
            cells.add(max(sorted(cand), key=lambda p: deg(p, cells)))
    assert len(cells) == n, (n, len(cells))
    return norm(cells)


def _first(gen, args_iter, n):
    for a in args_iter:
        cells = norm(gen(*a))
        if len(cells) == n and connected(cells):
            return cells, a
    raise RuntimeError("no match for %s n=%d" % (gen.__name__, n))


# v0.30b：轮廓“粗一点、有意境即可”。除改装型外，不再出现 1 格宽的细线，保证大模块（6~7 格）基本都放得下。
TEMPLATES = {
    "剑": {
        27: ["...#.......", "...#######.", "###########", "...#######.", "...#......."],
        19: ["..#......", "..####...", "#########", "..####...", "..#......"],
        13: ["..#...", "..###.", "######", "..##..", "..#..."],
    },
    "爪": {
        25: ["#.#.#.#", "#.#.#.#", "#######", "#######", "..###.."],
        17: ["#.#.#", "#.#.#", "#####", "#####", ".#..."],
        11: ["#.#.#", "#####", ".###."],
    },
    "炮筒": {
        24: ["#####", "##.##", "#####", "#####", "#####"],
        16: ["#####", "#####", "#####", "..#.."],
        10: ["####", "####", ".##."],
    },
    "斧": {
        24: ["#.....", "######", "######", "######", "#...#.", "....#.", "....#.", "....#."],
        16: ["#....", "#####", "#####", "#.###", "..#.."],
        10: ["####", "####", ".##."],
    },
    "步枪": {
        26: ["#################", "#######..........", "....#............", "....#............"],
        18: ["#########", "#######..", "..##....."],
        12: ["#######", "####...", "..#...."],
    },
}


def build(cat, n):
    if cat in TEMPLATES and n in TEMPLATES[cat]:
        rows = TEMPLATES[cat][n]
        return fit(rows, n), ("模板",)
    if cat == "剑":
        return _first(sword, ((g, p, gr, 3, L, t) for g in (5, 3) for p in (1, 0) for t in (1, 0) for gr in (2, 1, 3) for L in range(12, 0, -1)), n)
    if cat == "刀":
        return _first(knife, ((gr, g, 4, L, t) for g in (1, 0) for t in (1, 0) for gr in (3, 2, 4, 1) for L in range(10, 0, -1)), n)
    if cat == "拳套":
        return _first(fist, ((bw, bh, k, cw, ch, th) for k in (1, 0) for th in (0, 1) for bw in (5, 4, 3) for bh in (3, 4, 2) for cw in (3, 2) for ch in (2, 1, 3)), n)
    if cat == "手枪":
        return _first(pistol, ((s, g, t) for t in (1, 0) for s in (8, 7, 6, 5, 9, 4) for g in (5, 4, 3, 2, 6)), n)
    if cat == "弓":
        tmpl = {
            27: ["...###", "..####", "####.#", "####.#", "####.#", "..####", "...###"],
            19: ["..###", ".####", "###.#", "###.#", ".####", "..###"],
            13: [".###", "####", "##.#", "####", ".###"],
        }
        return fit(tmpl[n], n), ("模板收缩",)
    raise KeyError(cat)


def all_masks():
    out = {}
    for cat, vols in VOLUME.items():
        for form, n in zip(FORMS, vols):
            cells, args = build(cat, n)
            out[f"{cat}|{form}"] = (rows_of(cells), args)
    return out


if __name__ == "__main__":
    for key, (rows, args) in all_masks().items():
        print(key, sum(r.count("#") for r in rows), args)
        for r in rows:
            print("   ", r)


_CACHE = {}


def all_masks_cached():
    if not _CACHE:
        _CACHE.update({k: v[0] for k, v in all_masks().items()})
    return _CACHE
