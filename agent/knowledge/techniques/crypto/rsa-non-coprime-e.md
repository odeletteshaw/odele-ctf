# RSA：e 与 φ(n) 不互素（gcd(e, p-1) > 1）

**一句话**：拿到 p、q、e、c 时，先算 `gcd(e, p-1)` 和 `gcd(e, q-1)`。只要某一侧 gcd > 1，`d = pow(e, -1, φ(n))` 就走不通，得**分模求解 + 单位根补候选 + CRT 合并**，候选数 = `gcd(e, φ(n))`。

## 触发信号

- 题面直接给了 `e、p、q、c`（或能求出 p、q）。
- `factorint(e)` 得到 e 有小因子（如 `3 × 34543`）。
- 直接 `pow(e, -1, p-1)` 抛 `ValueError: base is not invertible`。
- `gcd(e, p-1) > 1` 或 `gcd(e, q-1) > 1`。

## 关键第一步（诊断，不要跳）

```python
from math import gcd
print(gcd(e, p-1), gcd(e, q-1))
```

**不要急着完全分解 p-1 / q-1**——那通常是超大合数，`sympy.factorint` 会病态地慢（和 `primitive_root`/`discrete_log` 同类的坑）。gcd 只需要一次取模，完全够定位问题。

## 套路

设 `g = gcd(e, p-1)`（假设只有模 p 侧不互素，模 q 侧互素）：

1. **互素侧正常解**：`dq = pow(e, -1, q-1)`；`mq = pow(c, dq, q)`（唯一解）。
2. **不互素侧**：令 `m = (p-1) // g`（g 次单位根的分母），
   - `d = pow(e, -1, m)`（在模 `(p-1)/g` 下求逆）。
   - 找 g 次单位根 ω：扫描 `a = 2,3,...`，`ω = pow(a, m, p)`，要求 `pow(ω, g, p) == 1` 且 `ω != 1`。
   - 候选：`mp_j = (pow(c, d, p) * pow(ω, j, p)) % p`，`j = 0..g-1`。
3. **CRT 合并**：`qinv = pow(q, -1, p)`；对每个 mp：`k = ((mp - mq) * qinv) % p`；`m = mq + q * k`。
4. **判别**：所有候选都满足 `pow(m, e, n) == c`（数学上都是解），**必须靠明文可打印性/语义**挑真正的 flag，不能用密文自检。

## 可复用代码

```python
from math import gcd

def rsa_non_coprime_e(p, q, e, c):
    n = p * q
    g = gcd(e, p - 1)  # 或 gcd(e, q-1)，哪侧 >1 就处理哪侧
    # 模 q 侧（假设互素）
    mq = pow(c, pow(e, -1, q - 1), q)
    # 模 p 侧（g 个候选）
    m = (p - 1) // g
    d = pow(e, -1, m)
    om = next(pow(a, m, p) for a in range(2, 2000)
              if pow(a, m, p) != 1 and pow(pow(a, m, p), g, p) == 1)
    qinv = pow(q, -1, p)
    out = []
    for j in range(g):
        mp = (pow(c, d, p) * pow(om, j, p)) % p
        k = ((mp - mq) * qinv) % p
        mm = mq + q * k
        assert pow(mm, e, n) == c
        b = mm.to_bytes((mm.bit_length() + 7) // 8, 'big')
        out.append(b)
    return out  # 用可打印性挑真正的 flag
```

## 坑

- **坑 1**：第一反应 `d = pow(e, -1, phi)` 直接抛 `ValueError`。正确姿势是先 `gcd(e, p-1)`/`gcd(e, q-1)`。
- **坑 2**：`gcd(e, φ(n)) > 1` **不等于无解**。候选数 = 这个 gcd，单位根补出来再 CRT。
- **坑 3**：所有候选都能通过 `pow(m,e,n)==c` 自检，**不能用密文自检挑答案**，要靠可打印性。
- **坑 4**：单位根 ω 用 `a^( (p-1)/g )` 小范围暴力扫即可（a 从 2 起，一般几百内就命中），不用大整数离散对数。

## 关联

- 同类「别陷入大数硬分解」的坑见 `CLAUDE.md` 血的教训（`primitive_root`、`discrete_log` 病态慢）。
- 相关 RSA 模板：立方根、Fermat、Wiener、共模、Håstad、共因子、LSB oracle、格（LLL/HNP）。
