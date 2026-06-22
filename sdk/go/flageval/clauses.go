package flageval

import (
	"regexp"
	"strings"
)

func matchClauses(clauses []Clause, store Store, ctx Context) bool {
	for _, c := range clauses {
		if !matchClause(c, store, ctx) {
			return false
		}
	}
	return true
}

func matchClause(c Clause, store Store, ctx Context) bool {
	var res bool
	if c.Op == "segmentMatch" {
		res = anySegmentMatch(c.Values, store, ctx)
	} else if v, ok := ctx.attr(c.ContextKind, c.Attribute); ok {
		// A clause matches if the context value satisfies the op for ANY target value.
		for _, target := range c.Values {
			if opMatch(c.Op, v, target) {
				res = true
				break
			}
		}
	}
	if c.Negate {
		return !res
	}
	return res
}

func opMatch(op string, ctxVal, target any) bool {
	switch op {
	case "in":
		return equalAny(ctxVal, target)
	case "startsWith":
		return strings.HasPrefix(asString(ctxVal), asString(target))
	case "endsWith":
		return strings.HasSuffix(asString(ctxVal), asString(target))
	case "contains":
		return strings.Contains(asString(ctxVal), asString(target))
	case "matches":
		re, err := regexp.Compile(asString(target))
		return err == nil && re.MatchString(asString(ctxVal))
	case "lessThan":
		a, b, ok := asNumbers(ctxVal, target)
		return ok && a < b
	case "greaterThan":
		a, b, ok := asNumbers(ctxVal, target)
		return ok && a > b
	default:
		return false // before/after/semVer* not yet implemented (DESIGN.md §4)
	}
}

// anySegmentMatch reports whether the context belongs to any of the named segments.
func anySegmentMatch(segmentKeys []any, store Store, ctx Context) bool {
	for _, sk := range segmentKeys {
		seg, ok := store.Segments[asString(sk)]
		if ok && segmentContains(seg, store, ctx) {
			return true
		}
	}
	return false
}

func segmentContains(seg Segment, store Store, ctx Context) bool {
	key, ok := ctx.key(seg.ContextKind)
	if ok {
		for _, e := range seg.Excluded {
			if e == key {
				return false
			}
		}
		for _, i := range seg.Included {
			if i == key {
				return true
			}
		}
	}
	for _, r := range seg.Rules {
		if matchClauses(r.Clauses, store, ctx) {
			return true
		}
	}
	return false
}
