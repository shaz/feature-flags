// Package flageval is the reference implementation of fubo-flags evaluation and
// bucketing (DESIGN.md §4–§5). It is validated against the language-agnostic
// conformance corpus; every other SDK must match its behavior vector-for-vector.
package flageval

// Variation is one possible value of a flag. Rules/targets/fallthrough reference
// variations by index into Flag.Variations.
type Variation struct {
	Name  string `json:"name"`
	Value any    `json:"value"`
}

type Clause struct {
	ContextKind string `json:"contextKind"`
	Attribute   string `json:"attribute"`
	Op          string `json:"op"`
	Values      []any  `json:"values"`
	Negate      bool   `json:"negate"`
}

type WeightedVariation struct {
	Variation int `json:"variation"`
	Weight    int `json:"weight"` // hundred-thousandths; weights in a rollout sum to 100000
}

type Rollout struct {
	ContextKind string              `json:"contextKind"`
	BucketBy    string              `json:"bucketBy"`
	Variations  []WeightedVariation `json:"variations"`
}

// Rule and Fallthrough carry exactly one of Variation / Rollout.
type Rule struct {
	Clauses   []Clause `json:"clauses"`
	Variation *int     `json:"variation"`
	Rollout   *Rollout `json:"rollout"`
}

type Fallthrough struct {
	Variation *int     `json:"variation"`
	Rollout   *Rollout `json:"rollout"`
}

type Target struct {
	ContextKind string   `json:"contextKind"`
	Variation   int      `json:"variation"`
	Keys        []string `json:"keys"`
}

type Prerequisite struct {
	FlagKey   string `json:"flagKey"`
	Variation int    `json:"variation"`
}

type Config struct {
	Enabled       bool           `json:"enabled"`
	Targets       []Target       `json:"targets"`
	Rules         []Rule         `json:"rules"`
	Fallthrough   Fallthrough    `json:"fallthrough"`
	OffVariation  int            `json:"offVariation"`
	Prerequisites []Prerequisite `json:"prerequisites"`
}

type Flag struct {
	Key        string      `json:"key"`
	Salt       string      `json:"salt"`
	Kind       string      `json:"kind"`
	Variations []Variation `json:"variations"`
	Config     Config      `json:"config"`
}

type SegmentRule struct {
	Clauses []Clause `json:"clauses"`
}

type Segment struct {
	Key         string        `json:"key"`
	ContextKind string        `json:"contextKind"`
	Included    []string      `json:"included"`
	Excluded    []string      `json:"excluded"`
	Rules       []SegmentRule `json:"rules"`
}

// Store holds the assembled ruleset an evaluation reads from (other flags for
// prerequisites, segments for segmentMatch clauses).
type Store struct {
	Flags    map[string]Flag
	Segments map[string]Segment
}

// Result of evaluating one flag for one context.
type Result struct {
	VariationIndex int    `json:"variationIndex"`
	Value          any    `json:"value"`
	Reason         string `json:"reason"`
}
