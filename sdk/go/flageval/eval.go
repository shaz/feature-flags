package flageval

// Evaluate resolves one flag for one context against the store. Order (first hit
// wins): off → prerequisites → targets → rules → fallthrough (DESIGN.md §4).
func Evaluate(flag Flag, store Store, ctx Context) Result {
	return evaluate(flag, store, ctx, map[string]bool{})
}

func evaluate(flag Flag, store Store, ctx Context, visiting map[string]bool) Result {
	cfg := flag.Config

	off := func(reason string) Result {
		return Result{
			VariationIndex: cfg.OffVariation,
			Value:          flag.Variations[cfg.OffVariation].Value,
			Reason:         reason,
		}
	}
	hit := func(idx int, reason string) Result {
		return Result{VariationIndex: idx, Value: flag.Variations[idx].Value, Reason: reason}
	}

	// 1. off
	if !cfg.Enabled {
		return off("OFF")
	}

	// 2. prerequisites — each must be on and evaluate to the required variation
	for _, p := range cfg.Prerequisites {
		pf, ok := store.Flags[p.FlagKey]
		if !ok || visiting[p.FlagKey] { // missing or cyclic prereq fails closed
			return off("PREREQUISITE_FAILED")
		}
		visiting[p.FlagKey] = true
		res := evaluate(pf, store, ctx, visiting)
		delete(visiting, p.FlagKey)
		if !pf.Config.Enabled || res.VariationIndex != p.Variation {
			return off("PREREQUISITE_FAILED")
		}
	}

	// 3. individual targets
	for _, t := range cfg.Targets {
		if k, ok := ctx.key(t.ContextKind); ok {
			for _, key := range t.Keys {
				if key == k {
					return hit(t.Variation, "TARGET_MATCH")
				}
			}
		}
	}

	// 4. rules, in order
	for _, r := range cfg.Rules {
		if matchClauses(r.Clauses, store, ctx) {
			if r.Variation != nil {
				return hit(*r.Variation, "RULE_MATCH")
			}
			if r.Rollout != nil {
				return hit(bucketVariation(flag, *r.Rollout, ctx), "RULE_MATCH")
			}
		}
	}

	// 5. fallthrough
	if cfg.Fallthrough.Variation != nil {
		return hit(*cfg.Fallthrough.Variation, "FALLTHROUGH")
	}
	if cfg.Fallthrough.Rollout != nil {
		return hit(bucketVariation(flag, *cfg.Fallthrough.Rollout, ctx), "FALLTHROUGH")
	}
	return off("FALLTHROUGH") // defensive: no fallthrough configured
}
