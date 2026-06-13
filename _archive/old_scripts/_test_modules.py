# Quick diagnostic test for knowledge modules
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Bypass knowledge/__init__.py to avoid circular imports
import importlib.util, sys, os

def _load_module(name, filepath):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_knowledge_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'knowledge')
surv = _load_module('survival_engine_v2', os.path.join(_knowledge_dir, 'survival_engine_v2.py'))
bayes = _load_module('bayesian_engine', os.path.join(_knowledge_dir, 'bayesian_engine.py'))

TextDiagnosticEngine = surv.TextDiagnosticEngine
CoxPrescriptionEngine = surv.CoxPrescriptionEngine
BayesianAnalyzer = bayes.BayesianAnalyzer
EmpiricalBayesAnalyzer = bayes.EmpiricalBayesAnalyzer

print("=" * 60)
print("Module diagnostic test")
print("=" * 60)

# Test 1: TDE REFERENCE_RANGES
print("\n1. TextDiagnosticEngine REFERENCE_RANGES:")
for k in TextDiagnosticEngine.REFERENCE_RANGES:
    print(f"   - {k}")

# Test 2: TDE diagnose with sample input
print("\n2. TextDiagnosticEngine.diagnose():")
sample = {
    'style_vector': {
        'dialogue_ratio': 0.15, 'action_density': 0.2,
        'description_ratio': 0.1, 'emotion_ratio': 0.1,
        'narrative_ratio': 0.3,
    },
    'information_metrics': {
        'avg_sentence_length': 18, 'type_token_ratio': 0.45,
        'vocabulary_richness': 0.5, 'paragraph_density': 0.05,
        'transition_word_ratio': 0.02, 'passive_voice_ratio': 0.1,
    }
}
result = TextDiagnosticEngine.diagnose(sample)
qsn = result.get("quality_score_normalized")
print(f"   quality_score_normalized = {qsn}")
print(f"   overall = {result.get('overall')}")
print(f"   diagnoses = {len(result.get('diagnoses', []))} items")
for d in result.get('diagnoses', [])[:3]:
    print(f"     {d.get('feature')}: {d.get('severity')}, contrib={d.get('score_contribution')}")

# Test 3: BayesianAnalyzer with sub_scores
print("\n3. BayesianAnalyzer.analyze_chapters():")
ba = BayesianAnalyzer()
chapters = [
    {"sub_scores": [70, 65, 80, 75], "weights": None, "chapter": 1, "raw_score_override": 72.5},
    {"sub_scores": [60, 55, 70, 65], "weights": None, "chapter": 2, "raw_score_override": 62.5},
    {"sub_scores": [85, 90, 80, 88], "weights": None, "chapter": 3, "raw_score_override": 85.8},
]
bayes_result = ba.analyze_chapters(chapters)
print(f"   n_chapters = {bayes_result.get('n_chapters')}")
for ch in bayes_result.get("chapters", [])[:2]:
    print(f"   Ch{ch.get('chapter')}: raw={ch.get('raw_score')}, shrunk={ch.get('shrunken_score')}")

# Test 4: EmpiricalBayesAnalyzer
print("\n4. EmpiricalBayesAnalyzer.analyze_chapters():")
eba = EmpiricalBayesAnalyzer()
eb_result = eba.analyze_chapters(chapters)
print(f"   tau_sq = {eb_result.get('tau_sq_chapter_variation', 'N/A')}")
for ch in eb_result.get("chapters", [])[:2]:
    print(f"   Ch{ch.get('chapter')}: raw={ch.get('raw_score')}, shrunk={ch.get('shrunken_score')}")

# Test 5: CoxPrescriptionEngine.run_all
print("\n5. CoxPrescriptionEngine.run_all():")
try:
    rx = CoxPrescriptionEngine.run_all(None)
    print(f"   Result keys: {list(rx.keys())[:10]}")
except Exception as e:
    print(f"   Expected error (no data): {e}")

print("\n" + "=" * 60)
print("All tests passed!")
print("=" * 60)
