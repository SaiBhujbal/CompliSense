# 📇 CompliSense Quick Reference

## 🚀 Quick Commands

### Setup & Run
```bash
# Clone and configure
git clone https://github.com/SaiBhujbal/CompliSense.git
cd CompliSense
cp .env.example .env
# Edit .env with your API keys

# With Docker (recommended)
docker-compose --profile ingest up --build  # First time: ingest data
docker-compose --profile app up             # Run application

# Without Docker
pip install -r requirements.txt
python ingest_data.py                       # First time: ingest data
streamlit run src/ui/app.py                 # Run application
```

### Access
- **App URL**: http://localhost:8501
- **Data Volume**: `compli-sense-data` (Docker managed)

---

## 📂 File Navigation

| File/Directory | Purpose | Key Functions |
|----------------|---------|---------------|
| **src/agents/** | Agent implementations | All `*_node()` functions |
| **src/graph/workflow.py** | Workflow orchestration | `create_workflow()` |
| **src/state.py** | State schema | `AgentState` TypedDict |
| **src/config.py** | Configuration | All constants & settings |
| **src/utils/setup.py** | Utilities | `get_llm()`, `setup_vector_store()` |
| **src/ui/app.py** | Streamlit UI | Main app logic |
| **ingest_data.py** | Data pipeline | Document ingestion |

---

## 🔧 Agent Reference

| Agent | File | Purpose | Model | Input | Output |
|-------|------|---------|-------|-------|--------|
| **Orchestrator** | `orchestrator_agent.py` | Query understanding | Llama-3-8B | `user_query` | `is_ambiguous`, `analysis_intent` |
| **RBI** | `rbig_agent.py` | Compliance RAG | Llama-3-70B | `user_query` | `rbi_compliance_report` |
| **PESTEL** | `pestel_agent.py` | Macro analysis | Llama-3-70B | `analysis_intent` | `pestel_report` |
| **Competitor** | `competitor_agent.py` | Market intel | Llama-3-70B | `analysis_intent` | `competitor_report` |
| **Trend** | `trend_agent.py` | Future prediction | Llama-3-70B | `analysis_intent` | `trend_report` |
| **Validator** | `validator_agent.py` | Quality check | Llama-3-8B | All reports | `validation_status` |
| **Analysis** | `analysis_agent.py` | Synthesis | Llama-3-70B | All reports | `final_analysis` |
| **Response** | `response_agent.py` | User formatting | Llama-3-70B | `final_analysis` | `final_response` |

---

## ⚙️ Configuration Quick Ref

### Environment Variables (.env)
```bash
GROQ_API_KEY=xxx              # Required: Groq LLM
TAVILY_API_KEY=xxx            # Required: Web search
RBI_DATA_PATH=./data          # Optional: Data directory
CHROMA_DB_PATH=./chroma_db    # Optional: Vector DB path

# Note: OpenAI API key is no longer required - we use free HuggingFace embeddings
```

### Key Config Values (src/config.py)
```python
DEFAULT_LLM_MODEL = "llama3-70b-8192"
FAST_LLM_MODEL = "llama3-8b-8192"
MAX_VALIDATION_RETRIES = 2
RETRIEVAL_TOP_K = 5
CHUNK_SIZE = 1000
```

---

## 🔄 Workflow States

### State Fields
```python
user_query: str                    # User input
is_ambiguous: bool                 # Needs clarification?
analysis_intent: str               # Extracted intent
rbi_compliance_report: str         # RBI analysis
pestel_report: str                 # PESTEL analysis
competitor_report: str             # Competition analysis
trend_report: str                  # Trend prediction
validation_status: str             # 'valid' or 'invalid'
retry_count: int                   # Validation retries
final_analysis: str                # Strategic synthesis
final_response: str                # User-facing output
```

### Workflow Flow
```
Query → Orchestrator → {Ambiguous? → Clarify : Parallel Agents}
Parallel Agents → Validator → {Invalid & retries<2? → Retry : Analysis}
Analysis → Response → Output
```

---

## 🛠️ Common Tasks

### Add New Agent
1. Create `src/agents/new_agent.py`
2. Define `new_agent_node(state: dict) -> dict`
3. Add state field to `src/state.py`
4. Register in `src/graph/workflow.py`
5. Export from `src/agents/__init__.py`

### Modify LLM Model
```python
# In src/config.py
DEFAULT_LLM_MODEL = "llama3-70b-8192"  # Change here
```

### Adjust Vector Search
```python
# In src/config.py
RETRIEVAL_TOP_K = 10  # More documents

# In src/agents/rbig_agent.py
retriever = vector_store.as_retriever(
    search_kwargs={"k": 10, "score_threshold": 0.7}
)
```

### Update Data Sources
Edit `data_sources.yaml` then run:
```bash
docker-compose --profile ingest up --build
```

---

## 🐛 Debugging

### Enable Debug Logging
```python
# Add to any file
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Test Single Agent
```python
from src.agents.rbig_agent import rbig_node

state = {"user_query": "test"}
result = rbig_node(state)
print(result)
```

### Check State Flow
```python
# In any agent
def my_agent_node(state: dict) -> dict:
    print(f"State keys: {state.keys()}")
    # ... rest of code
```

---

## 📊 Monitoring

### Key Metrics to Track
- Agent execution time
- Validation retry rate
- LLM token usage
- Error frequency
- User satisfaction (thumbs up/down)

### Health Checks
```bash
# Check vector store
ls -lh data/chroma_db/

# Check logs
docker-compose logs app

# Check running containers
docker-compose ps
```

---

## 🔒 Security Checklist

- [ ] API keys in `.env` (never commit)
- [ ] `.gitignore` includes `.env`
- [ ] Input validation on user queries
- [ ] Rate limiting on API calls
- [ ] Sanitize LLM outputs before display
- [ ] Regular dependency updates
- [ ] HTTPS in production
- [ ] Authentication enabled

---

## 📚 Documentation Index

1. **README.md** - User guide & setup
2. **CODEBASE_ANALYSIS.md** - Complete technical analysis
3. **IMPROVEMENTS.md** - All changes & fixes
4. **DEVELOPER_GUIDE.md** - Development handbook
5. **SUMMARY.md** - Executive summary
6. **QUICK_REFERENCE.md** - This file

---

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| Import errors | Check `__init__.py` files exist |
| Vector store not found | Run `python ingest_data.py` |
| API errors | Verify API keys in `.env` |
| Slow responses | Check network/API quotas |
| Validation loops | Check retry_count < 2 |
| Session conflicts | Each user has unique thread_id |

---

## 🔗 Useful Links

- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **Groq Console**: https://console.groq.com/
- **Tavily API**: https://docs.tavily.com/
- **Streamlit**: https://docs.streamlit.io/

---

## 📞 Support

- **Issues**: GitHub Issues
- **Docs**: `/docs` folder (this repository)
- **Code**: Well-commented throughout

---

*Last Updated: 2025*
*Quick Ref v1.0*
