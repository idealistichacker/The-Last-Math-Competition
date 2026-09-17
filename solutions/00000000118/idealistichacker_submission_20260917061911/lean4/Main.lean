import Std

namespace PrimeChain

/-- The `n`-fold compositional iterate of `f` at `x`. -/
def iterate (f : Int → Int) : Nat → Int → Int
  | 0 => fun x => x
  | n + 1 => fun x => f (iterate f n x)

/-- Elementary positive-natural primality. -/
def NatPrime (p : Nat) : Prop :=
  2 ≤ p ∧ ∀ d : Nat, d ∣ p → d = 1 ∨ d = p

/-- A natural prime embedded in the integers. -/
def IntegerPrime (z : Int) : Prop :=
  ∃ p : Nat, NatPrime p ∧ z = (p : Int)

/-- A function represented by an exact degree-two polynomial over the integers. -/
def IntegerQuadratic (f : Int → Int) : Prop :=
  ∃ a b c : Int, a ≠ 0 ∧ ∀ x : Int, f x = a * x * x + b * x + c

/-- The fixed polynomial `x^2 - 2*x + 2`. -/
def primeQuadratic (x : Int) : Int :=
  x * x + (-2) * x + 2

/--
The source list begins with `f(0)`. We consequently require that value and,
for each positive index at most `M`, the corresponding compositional iterate.
-/
def HasPrimeChain (M : Nat) : Prop :=
  ∃ f : Int → Int, IntegerQuadratic f ∧ IntegerPrime (f 0) ∧
    ∀ i : Nat, 1 ≤ i → i ≤ M → IntegerPrime (iterate f i 0)

theorem naturalPrime_two : NatPrime 2 := by
  constructor
  · exact Nat.le_refl 2
  · intro d hd
    have hle : d ≤ 2 := Nat.le_of_dvd (Nat.succ_pos 1) hd
    cases d with
    | zero =>
      rcases hd with ⟨c, hc⟩
      have hc' : 2 = 0 := hc.trans (Nat.zero_mul c)
      exact False.elim (Nat.noConfusion hc')
    | succ d =>
      cases d with
      | zero => exact Or.inl rfl
      | succ d =>
        have hle1 : Nat.succ d ≤ Nat.succ 0 := Nat.succ_le_succ_iff.mp hle
        have hle0 : d ≤ 0 := Nat.succ_le_succ_iff.mp hle1
        have hd0 : d = 0 := Nat.eq_zero_of_le_zero hle0
        subst d
        exact Or.inr rfl

theorem primeQuadratic_is_quadratic : IntegerQuadratic primeQuadratic := by
  refine ⟨1, -2, 2, Int.one_ne_zero, ?_⟩
  intro x
  change x * x + (-2) * x + 2 = 1 * x * x + (-2) * x + 2
  rw [Int.one_mul]

theorem primeQuadratic_zero : primeQuadratic 0 = 2 := by
  rfl

theorem primeQuadratic_two : primeQuadratic 2 = 2 := by
  rfl

theorem integerPrime_two : IntegerPrime 2 := by
  exact ⟨2, naturalPrime_two, rfl⟩

/-- Every positive compositional iterate of the chosen quadratic at zero is two. -/
theorem iterate_primeQuadratic_succ (n : Nat) :
    iterate primeQuadratic (Nat.succ n) 0 = 2 := by
  induction n with
  | zero =>
      exact primeQuadratic_zero
  | succ n ih =>
      change primeQuadratic (iterate primeQuadratic (Nat.succ n) 0) = 2
      rw [ih]
      exact primeQuadratic_two

theorem iterate_primeQuadratic_succ_is_prime (n : Nat) :
    IntegerPrime (iterate primeQuadratic (Nat.succ n) 0) := by
  rw [iterate_primeQuadratic_succ]
  exact integerPrime_two

/-- For every finite bound, the fixed exact quadratic has the required prime chain. -/
theorem iterated_prime_chains : ∀ M : Nat, HasPrimeChain M := by
  intro M
  refine ⟨primeQuadratic, primeQuadratic_is_quadratic, ?_, ?_⟩
  · rw [primeQuadratic_zero]
    exact integerPrime_two
  · intro i hi _
    cases i with
    | zero => exact False.elim (Nat.not_succ_le_zero 0 hi)
    | succ n => exact iterate_primeQuadratic_succ_is_prime n

end PrimeChain