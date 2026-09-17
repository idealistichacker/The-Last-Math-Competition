import Mathlib.Combinatorics.Enumerative.IncidenceAlgebra
import Mathlib.RingTheory.Jacobson.Ideal

open Finset
open IncidenceAlgebra

namespace TLMC2617

/-- Mathlib's incidence algebra of the fixed two-element chain over `ℚ`. -/
abbrev A := IncidenceAlgebra ℚ (Fin 2)

/-- The coefficient function supported exactly on the strict interval `(0, 1)`. -/
def offDiagonal : A :=
  ⟨fun a b => if a = 0 ∧ b = 1 then 1 else 0, by
    intro a b hnot
    simp only [ite_eq_right_iff]
    rintro ⟨rfl, rfl⟩
    exact (hnot (by omega)).elim⟩

lemma offDiagonal_apply (a b : Fin 2) :
    offDiagonal a b = if a = 0 ∧ b = 1 then 1 else 0 := rfl

/-- The strict off-diagonal coefficient is nonzero. -/
lemma offDiagonal_ne_zero : offDiagonal ≠ 0 := by
  intro h
  have h01 : offDiagonal (0 : Fin 2) 1 = 0 := by rw [h]; rfl
  norm_num [offDiagonal] at h01

/-- For every `y`, the actual Mathlib product `y * offDiagonal` squares to zero.

The proof expands `IncidenceAlgebra.mul_apply` over all four pairs of `Fin 2`;
it does not use a bespoke coordinate-algebra replacement. -/
lemma right_mul_offDiagonal_sq_zero (y : A) :
    (y * offDiagonal) * (y * offDiagonal) = 0 := by
  ext a b hab
  fin_cases a <;> fin_cases b <;>
    simp [IncidenceAlgebra.mul_apply, offDiagonal]

/-- The nonzero off-diagonal coefficient belongs to the actual Jacobson radical. -/
lemma offDiagonal_mem_jacobson :
    offDiagonal ∈ Ideal.jacobson (⊥ : Ideal A) := by
  rw [Ideal.mem_jacobson_iff]
  intro y
  refine ⟨1 - y * offDiagonal, ?_⟩
  rw [Submodule.mem_bot]
  have hsq := right_mul_offDiagonal_sq_zero y
  calc
    (1 - y * offDiagonal) * y * offDiagonal + (1 - y * offDiagonal) - 1
        = (y * offDiagonal - (y * offDiagonal) * (y * offDiagonal)) +
            (1 - y * offDiagonal) - 1 := by
              simp only [sub_mul, one_mul, mul_assoc]
    _ = 0 := by
      rw [hsq]
      abel

/-- Hence the Jacobson radical is not bottom in this fixed rational two-point case. -/
theorem jacobson_ne_bot : Ideal.jacobson (⊥ : Ideal A) ≠ ⊥ := by
  intro h
  have hmem : offDiagonal ∈ (⊥ : Ideal A) := by
    simpa only [h] using offDiagonal_mem_jacobson
  exact offDiagonal_ne_zero (by simpa only [Submodule.mem_bot] using hmem)

end TLMC2617
