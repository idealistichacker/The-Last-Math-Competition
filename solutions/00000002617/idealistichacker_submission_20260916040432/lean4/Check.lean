import Main

open IncidenceAlgebra

namespace TLMC2617

#check IncidenceAlgebra.mul_apply
#check IncidenceAlgebra.one_apply
#check IncidenceAlgebra.ext
#check Ideal.mem_jacobson_iff
#synth Ring A

#check offDiagonal
#check TLMC2617.offDiagonal_ne_zero
#check TLMC2617.right_mul_offDiagonal_sq_zero
#check TLMC2617.offDiagonal_mem_jacobson
#check TLMC2617.jacobson_ne_bot

#print axioms TLMC2617.offDiagonal_ne_zero
#print axioms TLMC2617.right_mul_offDiagonal_sq_zero
#print axioms TLMC2617.offDiagonal_mem_jacobson
#print axioms TLMC2617.jacobson_ne_bot

end TLMC2617
