package flageval

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

type vector struct {
	Name        string         `json:"name"`
	Flag        Flag           `json:"flag"`
	Segments    []Segment      `json:"segments"`
	PrereqFlags []Flag         `json:"prereqFlags"`
	Context     map[string]any `json:"context"`
	Expected    Result         `json:"expected"`
}

// TestConformance runs the shared corpus (conformance/vectors.json) through the
// evaluator. This is the contract every SDK must satisfy.
func TestConformance(t *testing.T) {
	path := filepath.Join("..", "..", "..", "conformance", "vectors.json")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read vectors: %v", err)
	}
	var vectors []vector
	if err := json.Unmarshal(data, &vectors); err != nil {
		t.Fatalf("parse vectors: %v", err)
	}
	if len(vectors) == 0 {
		t.Fatal("no vectors loaded")
	}

	for _, v := range vectors {
		t.Run(v.Name, func(t *testing.T) {
			store := Store{Flags: map[string]Flag{v.Flag.Key: v.Flag}, Segments: map[string]Segment{}}
			for _, pf := range v.PrereqFlags {
				store.Flags[pf.Key] = pf
			}
			for _, s := range v.Segments {
				store.Segments[s.Key] = s
			}

			got := Evaluate(v.Flag, store, ParseContext(v.Context))

			if got.VariationIndex != v.Expected.VariationIndex {
				t.Errorf("variationIndex: got %d want %d", got.VariationIndex, v.Expected.VariationIndex)
			}
			if got.Reason != v.Expected.Reason {
				t.Errorf("reason: got %q want %q", got.Reason, v.Expected.Reason)
			}
			if !reflect.DeepEqual(got.Value, v.Expected.Value) {
				t.Errorf("value: got %#v want %#v", got.Value, v.Expected.Value)
			}
		})
	}
}

// TestBucketParity pins the SHA1 bucketing to values derived independently by
// conformance/reference_bucket.py — cross-language parity, not self-agreement.
func TestBucketParity(t *testing.T) {
	cases := []struct {
		key  string
		want float64
	}{
		{"user-alpha", 0.0000205136},
		{"user-bravo", 0.0206997911},
		{"user-charlie", 0.8059973456},
		{"user-delta", 0.1185812884},
		{"user-echo", 0.8582182628},
	}
	for _, c := range cases {
		got := bucket("reco-rail-ml", "s4ltf1xed", c.key)
		if math.Abs(got-c.want) > 1e-9 {
			t.Errorf("bucket(%s): got %.10f want %.10f", c.key, got, c.want)
		}
	}
}
