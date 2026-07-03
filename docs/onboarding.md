# Onboarding Guide

Welcome to the M-Pesa Fraud Detection team! This guide will get you up to speed in 1-2 weeks.

## Week 1: Setup & Understanding

### Day 1: Environment Setup

**Morning (2 hours)**

```bash
# 1. Clone repository
git clone https://github.com/Victor-Kipruto-Rop/victor-kipruto-rop-portfolio.git
cd mpesa_safaricom/fraud_anomaly_detection

# 2. Create Python virtual environment
python3.10 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify setup
python -m pytest tests/ -v --tb=short
# Expected: 30 passed, 0 failed
```

**Afternoon (2 hours)**

- [ ] Read [README.md](../README.md) (entry point)
- [ ] Read [docs/architecture.md](architecture.md) (system design)
- [ ] Skim [docs/glossary.md](glossary.md) (unfamiliar terms)

**Evening**

Set up IDE:
- VS Code recommended
- Extensions: Python, Pylance, Jupyter, Git Graph
- Formatter: Black (configured in `pyproject.toml`)

---

### Day 2: Core Concepts

**Morning (2 hours)**

- [ ] Read [docs/fraud_detection.md](fraud_detection.md) — Configuration & check details
- [ ] Read [docs/model_strength_report.md](model_strength_report.md) — ML model overview
- [ ] Watch video: "ML Model Basics" (10 min, on team wiki)

**Afternoon (2 hours)**

- [ ] Clone and run ML training locally:
  ```bash
  python ml/train_model.py \
    --data ml/synthetic_transactions.parquet \
    --output-dir models/test_run \
    --sample-size 50
  ```
- [ ] Inspect generated model card: `models/test_run/MODEL_CARD.md`
- [ ] Discuss questions with buddy

**Evening**

- [ ] Skim test files to understand test patterns:
  - `tests/test_aggregator.py` (simple example, 100% coverage)
  - `tests/test_checks.py` (more complex, 100% coverage)

---

### Day 3: Running Code

**Morning (2 hours)**

- [ ] Start Flask app locally:
  ```bash
  export FLASK_ENV=development
  python -m flask run --host=0.0.0.0 --port=5000
  ```

- [ ] Test endpoint:
  ```bash
  curl -X POST http://localhost:5000/score \
    -H "Content-Type: application/json" \
    -d '{
      "TransID": "TEST_001",
      "MSISDN": "254712345678",
      "TransAmount": "5000",
      "TransTime": "20260101120000"
    }'
  ```

- [ ] Expected response:
  ```json
  {
    "decision": "ACCEPT",
    "score": 25.3,
    "checks": { ... }
  }
  ```

**Afternoon (2 hours)**

- [ ] Run full test suite with coverage:
  ```bash
  PYTHONPATH=../real_time_transaction_streaming:..:.  \
    pytest tests/ --cov --cov-report=html -v
  ```
- [ ] Open `htmlcov/index.html` in browser
- [ ] Identify low-coverage modules (target: 80%+)

**Evening**

- [ ] Pick one low-coverage module, read the code:
  - [ ] Understand what each function does
  - [ ] Sketch test cases on paper

---

### Day 4-5: Deeper Dive

**Day 4 (Full Day)**

- [ ] Read through a complex module (e.g., `engine.py`):
  - Create a mind map of functions & dependencies
  - Trace a transaction through the full pipeline
  - Identify unclear parts → add to questions list

- [ ] Pair-program with buddy:
  - Debug a failing test together
  - Add a simple test case
  - Submit PR for review

**Day 5 (Full Day)**

- [ ] Integration testing:
  - [ ] Stop Flask app
  - [ ] Read [docs/integration_notes.md](integration_notes.md)
  - [ ] Understand how real transaction streaming calls fraud detection
  - [ ] Mock a call from upstream system & trace through code

- [ ] Documentation review:
  - [ ] List any missing docs (add to README Index)
  - [ ] Note any confusing explanations (ask buddy or create issue)

---

## Week 2: Contributing

### Day 6: First PR

**Morning (2 hours)**

- [ ] Pick a task from the GitHub issues:
  - Label: `good-first-issue`
  - Complexity: Small (< 100 lines)
  - Example: Add unit test for utility function, fix typo in docs

- [ ] Create branch:
  ```bash
  git checkout -b fix/issue-123-describe-fix
  ```

**Afternoon (2 hours)**

- [ ] Make changes
- [ ] Run tests locally (ensure all pass):
  ```bash
  pytest tests/test_your_module.py -v
  pytest tests/ --cov -v  # Full suite if time permits
  ```

- [ ] Commit with clear message:
  ```bash
  git commit -m "fix: Add validation for empty MSISDN in schema_validator

  - Closes #123
  - Added check for non-empty string in validator.validate()
  - Updated test_schema_validator.py with edge case
  "
  ```

- [ ] Push and create PR

**Evening**

- [ ] Respond to code review feedback (expected within 24h)
- [ ] Make requested changes
- [ ] Ping reviewer once ready

---

### Day 7: Code Review & Best Practices

**Morning (2 hours)**

- [ ] Read someone else's PR:
  - Understand the change
  - Leave constructive feedback (if asked)
  - Ask clarifying questions

- [ ] Review best practices:
  - [ ] [docs/adr/](adr/) — Architecture Decision Records
  - [ ] Naming conventions (read random module, notice patterns)
  - [ ] Comment style (one comment per 10 lines of complex code)

**Afternoon (2 hours)**

- [ ] Merge your PR (once approved)
- [ ] Update CHANGELOG.md with your contribution
- [ ] Celebrate! 🎉

---

### Day 8-10: Deeper Tasks

Choose one:

#### Option A: Add a New Check
- Read `checks/base.py` (base class)
- Read one existing check (e.g., `checks/velocity_detector.py`)
- Implement `checks/my_new_check.py`
- Write tests in `tests/test_my_new_check.py`
- Integrate into engine
- PR & review

#### Option B: Improve Test Coverage
- Run `pytest --cov` and find low-coverage module
- Write tests to increase coverage to 80%+
- Verify test quality (each test checks one thing)
- PR & review

#### Option C: Fix a Documentation Gap
- Identify confusing docs (ask teammates)
- Rewrite for clarity
- Get feedback from non-author (ensures clarity)
- PR & review

#### Option D: Performance Investigation
- Profile the full pipeline:
  ```bash
  python -m cProfile -s cumtime -o profile.stats ml/train_model.py \
    --data ml/synthetic_transactions.parquet
  ```
- Identify bottleneck (slowest 3 functions)
- Document findings in issue
- Propose optimization
- PR & review

---

## Essential Resources

| Resource | Link | Time |
|----------|------|------|
| README | [docs/README.md](../README.md) | 10 min |
| Architecture | [docs/architecture.md](architecture.md) | 20 min |
| Glossary | [docs/glossary.md](glossary.md) | 5 min |
| Model Info | [docs/model_strength_report.md](model_strength_report.md) | 15 min |
| Integration | [docs/integration_notes.md](integration_notes.md) | 15 min |
| ADRs | [docs/adr/](adr/) | 10 min |

**Total Onboarding Time**: ~2-3 hours reading + ~40 hours hands-on = ~1-1.5 weeks

---

## Your First Week Checklist

- [ ] Cloned repo & ran tests locally (30 min)
- [ ] Read README & architecture docs (1 hour)
- [ ] Started Flask app & tested `/score` endpoint (1 hour)
- [ ] Understood 2 fraud checks in detail (2 hours)
- [ ] Found 1 undocumented behavior & asked buddy (30 min)
- [ ] Ran full test suite with coverage (30 min)
- [ ] Assigned first GitHub issue (5 min)
- [ ] **End of Week 1**: You can explain the fraud detection pipeline to someone

---

## Second Week Checklist

- [ ] Submitted first PR (code review turned around) (3 hours)
- [ ] Reviewed someone else's PR (1 hour)
- [ ] Merged your PR (5 min celebration)
- [ ] Picked a harder task (add test / improve coverage) (5 hours)
- [ ] Attended team standup & shared progress (30 min)
- [ ] **End of Week 2**: You can independently implement small features

---

## Office Hours & Support

**Questions?** Ask in Slack or book time with your buddy:

- **Buddy**: [Your buddy's name] (assigned on Day 1)
- **Team Lead**: [TL name] (weekly sync every Friday @ 10 AM)
- **Slack Channels**: 
  - #fraud-detection (general questions)
  - #fraud-detection-engineering (technical deep dives)
  - #fraud-detection-newbies (new hire support)

---

## Success Criteria (End of 2 Weeks)

- [ ] Can run tests locally & understand results
- [ ] Can explain the 4 main fraud checks to someone
- [ ] Have merged at least 1 PR
- [ ] Can add a unit test for an existing function
- [ ] Know where to find documentation for new questions
- [ ] Have attended 2 team standups & participated

**If all checked**: You're ready for independent work! 🚀

---

## Long-Term Growth (Months 2-6)

- Lead design of a new feature (own the ADR)
- Mentor the next new hire
- Own on-call rotation (with backup)
- Contribute to architecture improvements
- Publish internal tech blog post on learnings
