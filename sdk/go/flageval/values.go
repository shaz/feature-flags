package flageval

import (
	"math"
	"strconv"
)

// asString renders an attribute value for hashing/string ops. Integral floats
// (JSON numbers decode to float64) render without a decimal point so a context
// key of 42 hashes the same as "42".
func asString(v any) string {
	switch t := v.(type) {
	case string:
		return t
	case bool:
		if t {
			return "true"
		}
		return "false"
	case float64:
		if t == math.Trunc(t) && !math.IsInf(t, 0) {
			return strconv.FormatInt(int64(t), 10)
		}
		return strconv.FormatFloat(t, 'f', -1, 64)
	case nil:
		return ""
	default:
		return ""
	}
}

// equalAny compares two JSON-decoded values for "in"-style equality.
func equalAny(a, b any) bool {
	switch av := a.(type) {
	case string:
		bv, ok := b.(string)
		return ok && av == bv
	case bool:
		bv, ok := b.(bool)
		return ok && av == bv
	case float64:
		bv, ok := b.(float64)
		return ok && av == bv
	default:
		return false
	}
}

func asNumbers(a, b any) (float64, float64, bool) {
	af, aok := a.(float64)
	bf, bok := b.(float64)
	return af, bf, aok && bok
}
