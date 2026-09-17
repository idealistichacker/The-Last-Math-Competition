# Disproof package for conjecture 00000002617

**Status: local package ready for independent review.** This directory has not
been committed, pushed, submitted upstream, merged, accepted, or recorded as a
solution by organizers. It claims no priority, award, ranking, affiliation, or
human verification. It includes a compiled `main.pdf`, but a future independent
`review.json` is still required before it can be considered for publication.

Prepared with AI assistance for GitHub account `idealistichacker`; no
institutional affiliation is claimed.

## Exact frozen statement and scope

The organizer source is `conjectures/00000002617.md` at upstream commit
`95acb520ec5607c826b8a997b1ef2fc82d6f7c57`.

> **English.** Definition: Incidence algebras of locally finite posets: the
> structure of convolution algebras. Conjecture: The Jacobson radical of an
> incidence algebra is zero, with semisimplicity evidenced by pointwise
> invertibility of the Möbius function; the vanishing of the radical follows
> from local finiteness of the unit decomposition.

> **中文。** 定义：局部有限偏序集的关联代数：卷积代数的结构。猜想：关联代数的
> Jacobson 根为零且半单性的证据为 Möbius 函数的逐点可逆；根的消没由单位分解的
> 局部有限性给出。

- Frozen Git blob: `e23e80d92bfbf3e0970c427716f7ce3c2f97a39e`
- SHA-256 of raw Git-blob bytes: `03ba0f9febb435b53de0c4df73642bbb647b1a0b9eef3f297cedf5263564bc5b`

This package addresses **only** the zero-Jacobson-radical clause under an
explicit conventional instance: rational coefficients and the standard
ordered two-element poset. It does not assert an all-coefficient-rings result,
does not formalize semisimplicity, and does not treat the source's Möbius-
function sentence as a proof object.

## Standard Mathlib counterexample

The Lean object is exactly:

```lean
A := IncidenceAlgebra ℚ (Fin 2)
```

`Fin 2` is the ordered chain `0 < 1`. Let `e : A` be the actual incidence-
algebra function that is `1` on the strict interval `(0,1)` and `0` elsewhere.

The formalization proves:

1. `e ≠ 0`.
2. For every `y : A`, actual Mathlib convolution satisfies `(y * e)^2 = 0`.
3. Using Mathlib's `Ideal.mem_jacobson_iff` with `z = 1 - y * e`,
   `e ∈ Ideal.jacobson (⊥ : Ideal A)`.
4. Therefore `Ideal.jacobson (⊥ : Ideal A) ≠ ⊥`.

Thus the universal wording that the Jacobson radical of an incidence algebra is
zero has a counterexample if it includes this ordinary field-coefficient,
two-point locally finite-poset case. This is a statement about the actual
Mathlib incidence algebra and actual Mathlib Jacobson radical, not a bespoke
three-coordinate replacement.

## Pinned dependency and reproduction

- Lean: `leanprover/lean4:v4.33.1`
- Mathlib Git URL: `https://github.com/leanprover-community/mathlib4.git`
- Mathlib commit: `0df444a360eaa60ab8c11dca51a86af692955474`
- `lean4/lake-manifest.json` records Mathlib as a `git` dependency, never a
  local path dependency.

From this package directory:

```powershell
python .\reproduce.py `
  --lake <path-to-lake.exe> `
  --repo <path-to-LastMathC-checkout>
```

The script first checks the frozen source blob, raw hash, Git-pinned manifest
and package checkout heads. It sets `MATHLIB_NO_CACHE_ON_UPDATE=1` because the
optional Mathlib binary-cache hook is unreliable on this Windows host; source
builds remain the authoritative verification. By default it runs `lake update`,
then `lake build`, warning-as-error replay of `Main.lean`, and `Check.lean`.
If GitHub transport is temporarily unavailable but every package checkout is
already present, `--skip-update` verifies every manifest package's Git HEAD and
origin before building; it does not permit an unchecked offline fallback.

## Honest remaining gates

This package includes a locally compiled `main.pdf` after visual review, but has
no independent `review.json` yet. Before future publication, a different reviewer
must check statement alignment, mathematics, Lean correspondence, reproducibility,
and the compiled PDF; the release coordinator must then refresh upstream
source/duplicate state and obey the active-solution-PR limit. None of those
local results implies organizer acceptance.
