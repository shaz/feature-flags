package flageval

import (
	"crypto/sha1"
	"encoding/hex"
	"strconv"
)

// denom is 0xFFFFFFFFFFFFFFF (15 hex F's, 60 bits) — LaunchDarkly's divisor.
const denom = float64(0xFFFFFFFFFFFFFFF)

// bucket maps (flagKey, salt, value) to a float in [0, 1). DESIGN.md §5.
// Must stay byte-for-byte identical to the reference in
// conformance/reference_bucket.py and every other SDK.
func bucket(flagKey, salt, value string) float64 {
	sum := sha1.Sum([]byte(flagKey + "." + salt + "." + value))
	first15 := hex.EncodeToString(sum[:])[:15]
	n, _ := strconv.ParseUint(first15, 16, 64) // 60 bits fits in uint64
	return float64(n) / denom
}

// bucketVariation picks a variation for a rollout via sticky bucketing.
func bucketVariation(flag Flag, r Rollout, ctx Context) int {
	bucketBy := r.BucketBy
	if bucketBy == "" {
		bucketBy = "key"
	}
	value := ""
	if v, ok := ctx.attr(r.ContextKind, bucketBy); ok {
		value = asString(v)
	}
	b := bucket(flag.Key, flag.Salt, value)

	cum := 0.0
	for _, wv := range r.Variations {
		cum += float64(wv.Weight) / 100000.0
		if b < cum {
			return wv.Variation
		}
	}
	return r.Variations[len(r.Variations)-1].Variation // rounding catch-all
}
