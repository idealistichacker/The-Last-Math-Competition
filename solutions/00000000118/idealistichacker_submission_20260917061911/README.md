# Local proof package for conjecture 00000000118

**Status: submitted for upstream review in PR #103; not accepted.** An internal
independent-AI review is recorded in `review.json`. This package has been submitted
for maintainer review, but has not been merged, accepted, or recorded as a solution
by the organizers. It asserts no priority, award, ranking, affiliation, human
verification, or organizer approval. The internal review is not organizer review
and does not replace future maintainer or release-coordinator checks.

Prepared with AI assistance for the GitHub account `idealistichacker`; no
institutional affiliation is claimed.

## Frozen bilingual source and statement interpretation

The source was read in both languages at organizer commit
`95acb520ec5607c826b8a997b1ef2fc82d6f7c57`.

> **English.** Conjecture: Iterated prime chains: for every M there exists an
> integer-coefficient quadratic f such that f(0), f¹(0), …, f^M(0) are all
> prime.
>
> **中文。** 猜想：迭代素链:对每个 M,存在整系数二次 f,使 f(0), f¹(0), …,
> f^M(0) 全为素数。

- Frozen Git blob: `697131a7b8dc0a62c539018c7d22612df1e7909a`
- SHA-256 of the **raw frozen Git-blob bytes**:
  `91b64b4a671db1806c346247acbc2e0d849c5f73337bc807806c7cd00bbd580a`
- The present Windows working-tree file has CRLF bytes with SHA-256
  `e0d0528ef9238bd6333f20d77e952f79cd845e98c2c26dba905552578174ec16`.
  That is not the canonical blob-byte hash; the reproducibility script checks
  the Git object above.

We use the standard compositional convention
\(f^{\circ 0}(x)=x\) and \(f^{\circ(n+1)}(x)=f(f^{\circ n}(x))\).
Because the displayed list starts with `f(0)`, this package requires `f(0)`
and then, for each positive index `i` with `1 <= i <= M`, requires
`f^i(0)`. It does **not** silently require `f^0(0)=0` to be prime. For
`M = 0`, the retained requirement is therefore just primality of `f(0)`.
The source does not require distinct values, so the repeated value below is
allowed. This is an explicit interpretation, not a claim that organizers have
endorsed it; an internal independent statement-alignment review has passed, while
fresh release-coordinator checks remain required before any future publication.

## Mathematical construction

Take the integer-coefficient quadratic

\[
 f(x)=x^2-2x+2=(x-1)^2+1.
\]

Its quadratic coefficient is `1`, so its degree is exactly two. Directly,
\(f(0)=2\) and \(f(2)=2\). By induction,
\(f^{\circ i}(0)=2\) for every `i >= 1`; `2` is prime. Thus this one
quadratic witnesses every finite bound `M` under the stated interpretation.
No finite search or unproved prime heuristic is used.

## Formal Lean evidence

`lean4/Main.lean` formalizes:

- compositional iteration on `Int`;
- a positive-natural prime predicate `NatPrime`, embedded as `IntegerPrime`;
- `IntegerQuadratic`, requiring an integer quadratic coefficient `a != 0`;
- the precise `HasPrimeChain M` interpretation above; and
- `PrimeChain.iterated_prime_chains : forall M : Nat, HasPrimeChain M`.

The fixed polynomial is represented by the actual function
`x * x + (-2) * x + 2`. `lean4/Check.lean` runs `#print axioms` for every
advertised theorem. The source has no `sorry`, `admit`, declaration of an
axiom, `native_decide`, or unsafe evaluation.

The project is intentionally dependency-free apart from the Lean 4.33.1
standard distribution:

- Lean toolchain: `leanprover/lean4:v4.33.1`
- verified executable version: Lean 4.33.1, commit
  `819816b2e0a3bf405af45ae5c7af2491d8f5bee6`
- `lean4/lake-manifest.json`: no package dependencies and no path dependencies.

## Reproduction and artifacts

`main.pdf` was compiled locally from `main.tex` with cached-only
Tectonic 0.15.0. Its SHA-256 is recorded in `submission.json`.
`reproduce.py` independently rebuilds the PDF with cached-only Tectonic and
checks byte equality against that recorded artifact hash.

From this directory, run only local tools:

```powershell
python .\reproduce.py `
  --lake D:\AStudy\开源杂\LastMathC\.local\tools\lean-4.33.1-windows\bin\lake.exe `
  --tectonic D:\AStudy\开源杂\LastMathC\.local\tools\tectonic.exe `
  --repo D:\AStudy\开源杂\LastMathC\.local\worktrees\00000000118
```

The script uses local Git object inspection, builds the dependency-free Lean
project, replays `Main.lean` with warnings treated as errors, prints theorem
axioms, and compiles TeX with `--only-cached`. It neither performs a package
update nor invokes a network command.

## Upstream-review status and future changes

An internal independent-AI review is recorded in `review.json`; the release
coordinator refreshed the organizer source, duplicate state, issue/PR state, and
explicit parallel-WIP authorization before opening upstream PR #103. The package
is now submitted for upstream review through that PR. It is not merged or
accepted, and it does not establish priority, rank, award, affiliation, or
organizer approval.

Any future substantive change to this package must receive a fresh independent
review, full validation, and a normal non-force update to the same PR branch.
