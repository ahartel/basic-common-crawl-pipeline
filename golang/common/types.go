package common

type URL struct {
	SurtURL   string                 `json:"surt_url"`
	Timestamp string                 `json:"timestamp"`
	Metadata  map[string]interface{} `json:"metadata"`
}
