# LLM Integration & Provider Abstraction

## 1. Provider Interface

The AI services layer decouples the workflow from specific foundation model APIs using an abstract provider interface (`BaseLLMProvider` in `packages/ai_services/src/ai_services/providers/base.py`):

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None, **kwargs: Any) -> str:
        """Generate unstructured text completion."""
        ...

    @abstractmethod
    def generate_structured(
        self, prompt: str, response_model: type[T], system_prompt: str | None = None, **kwargs: Any
    ) -> T:
        """Generate structured response conforming to target Pydantic model."""
        ...
```

---

## 2. Supported Providers

### 1. `DeterministicMockLLMProvider` (Default for CI/Testing)

- **Class**: `ai_services.providers.mock.DeterministicMockLLMProvider`
- **Use Case**: Continuous Integration, automated pytest execution, deterministic benchmark evaluation.
- **Latency**: 0ms network latency.
- **Cost**: $0.00.
- **Behavior**: Implements deterministic semantic classification, certified metric resolution, and syntax-correct PostgreSQL 16 queries against the 12 governed financial metrics.
- **Enabling**: Set `LLM_PROVIDER=mock` in `.env`.

### 2. `OpenAICompatibleProvider` (Live Inference)

- **Class**: `ai_services.providers.openai_compatible.OpenAICompatibleProvider`
- **Use Case**: Production deployment with modern hosted APIs (OpenAI, Anthropic Claude via OpenAI gateway, Azure OpenAI, vLLM, Ollama).
- **Protocol**: Standard REST API `POST /v1/chat/completions`.
- **Enabling**: Set `LLM_PROVIDER=openai` (or custom endpoint) in `.env`.

---

## 3. Configuration Parameters

Environment variables configured in `.env` (managed centrally via `shared.config.Settings`):

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `mock` | Active provider: `mock`, `openai`, `custom`. |
| `LLM_MODEL` | `gpt-4o-mini` | Target foundation model identifier. |
| `LLM_API_KEY` | None | API authorization token (optional when provider is `mock`). |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | Base URL for OpenAI-compatible endpoints. |
| `LLM_TEMPERATURE` | `0.0` | Sampling temperature (0.0 for deterministic financial queries). |
| `LLM_TIMEOUT_SECONDS` | `30` | HTTP request timeout for live inference. |

---

## 4. Structured Output Guarantees

Nodes utilize `generate_structured()` using Pydantic validation:
- `QuestionUnderstanding`: Parses intent and filters out malicious inputs before state progression.
- `MetricResolution`: Maps natural language to governed metric identifiers (`metric_id`, `source_model`, `formula`).
- Fallbacks are implemented on every node to guarantee graceful degradation without crashing the LangGraph execution runtime.
