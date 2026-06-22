package flageval

// Context is a multi-context (DESIGN.md §4): one or more kinds (user, device,
// org…), each with its own attributes including "key".
type Context struct {
	kinds map[string]map[string]any
}

// ParseContext normalizes both the single-kind shorthand
// ({"kind":"user","key":...}) and the multi-kind form
// ({"kind":"multi","user":{...},"device":{...}}).
func ParseContext(raw map[string]any) Context {
	kinds := map[string]map[string]any{}
	kind, _ := raw["kind"].(string)

	if kind == "multi" {
		for k, v := range raw {
			if k == "kind" {
				continue
			}
			if m, ok := v.(map[string]any); ok {
				kinds[k] = m
			}
		}
	} else {
		if kind == "" {
			kind = "user"
		}
		attrs := map[string]any{}
		for k, v := range raw {
			if k != "kind" {
				attrs[k] = v
			}
		}
		kinds[kind] = attrs
	}
	return Context{kinds: kinds}
}

func (c Context) attr(kind, name string) (any, bool) {
	m, ok := c.kinds[kind]
	if !ok {
		return nil, false
	}
	v, ok := m[name]
	return v, ok
}

func (c Context) key(kind string) (string, bool) {
	v, ok := c.attr(kind, "key")
	if !ok {
		return "", false
	}
	s, ok := v.(string)
	return s, ok
}
