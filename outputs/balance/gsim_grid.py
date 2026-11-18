"""模块拼图（Python 版，与 Unity 的 ModuleGrid 同规则）：旋转 4 向 + 镜像，不越界、不压缺口、不重叠。"""
# ruff: noqa: E501

SHAPE_CELLS = {
    "直2": [(0, 0), (0, 1)],
    "直3": [(0, 0), (0, 1), (0, 2)],
    "弯3": [(0, 0), (1, 0), (1, 1)],
    "直4": [(0, 0), (0, 1), (0, 2), (0, 3)],
    "方4": [(0, 0), (0, 1), (1, 0), (1, 1)],
    "L4": [(0, 0), (1, 0), (2, 0), (2, 1)],
    "T4": [(0, 0), (0, 1), (0, 2), (1, 1)],
    "Z4": [(0, 0), (0, 1), (1, 1), (1, 2)],
    "直5": [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)],
    "P5": [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0)],
    "L5": [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1)],
    "T5": [(0, 0), (0, 1), (0, 2), (1, 1), (2, 1)],
    "U5": [(0, 0), (0, 2), (1, 0), (1, 1), (1, 2)],
    "Z5": [(0, 0), (0, 1), (1, 1), (2, 1), (2, 2)],
    "W5": [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2)],
    "十5": [(0, 1), (1, 0), (1, 1), (1, 2), (2, 1)],
    "矩6": [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)],
    "L6": [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (4, 1)],
    "T6": [(0, 0), (0, 1), (0, 2), (1, 1), (2, 1), (3, 1)],
    "U6": [(0, 0), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3)],
    "阶6": [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2), (3, 2)],
}


from module_shapes import SHAPES as NEW_SHAPES  # noqa: E402

SHAPE_CELLS.update(NEW_SHAPES)


def transform(cells, rot, mirror):
    cur = [(r, -c if mirror else c) for r, c in cells]
    for _ in range(rot):
        cur = [(c, -r) for r, c in cur]
    mr = min(r for r, _ in cur)
    mc = min(c for _, c in cur)
    return [(r - mr, c - mc) for r, c in cur]


def orientations(cells):
    seen, res = set(), []
    for mirror in (False, True):
        for rot in range(4):
            t = transform(cells, rot, mirror)
            key = tuple(sorted(t))
            if key not in seen:
                seen.add(key)
                res.append(t)
    return res


ORI = {k: orientations(v) for k, v in SHAPE_CELLS.items()}


class Grid:
    def __init__(self, mask):
        self.rows, self.cols = len(mask), len(mask[0])
        self.open = {(r, c) for r, row in enumerate(mask) for c, ch in enumerate(row) if ch == "#"}
        self.taken = set()
        self.volume = len(self.open)

    @property
    def free(self):
        return self.volume - len(self.taken)

    def auto_place(self, shape):
        for cells in ORI[shape]:
            for r in range(self.rows):
                for c in range(self.cols):
                    cs = [(r + a, c + b) for a, b in cells]
                    if all(x in self.open and x not in self.taken for x in cs):
                        self.taken.update(cs)
                        return True
        return False
