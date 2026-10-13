import sys
sys.path.insert(0, r'D:\autoSage\backend')

from app.agents.discovery import discovery_node, _find_uploaded_dataset
from app.agents.state import ExperimentWorkflowState
from app.core.observability import set_experiment_id

set_experiment_id('debug-lognone-001')

state = {
    'experiment_id': 'debug-lognone-001',
    'workspace_id': 'test-ws',
    'attempt': 0,
    'max_attempts': 3,
    'current_stage': 'queued',
    'status': 'RUNNING',
    'stages_completed': [],
    'events': ['experiment debug-lognone-001 queued'],
    'errors': [],
    'tool_calls': [],
    'dataset_info': {},
    'profile': {},
    'preprocessing_spec': {},
    'model_spec': {},
    'ml_result': {},
    'verification': {},
    'verification_passed': False,
    'fail_stage': None,
    'config': {
        'dataset_name': 'lending_applications_q3.csv',  # KEY: set from frontend
        'dataset': 'lending_applications_q3.csv',
        'target_column': 'defaulted',
        'task_type': 'classification',
        'evaluation_metric': 'accuracy',
        'prompt': 'Classify loan default yes/no using the Lending Q3 dataset',
    },
    'primary_metric': 'accuracy',
    'compare_models': False,
}

print("=== Test: Discovery with LLM unavailable (heuristic fallback) ===")
print(f"Config has dataset_name: {state['config'].get('dataset_name')}")
print(f"Config has dataset: {state['config'].get('dataset')}")
print()

result = discovery_node(state)
ds_info = result.get('dataset_info', {})
print(f"Dataset found: {ds_info.get('name')}")
print(f"Source: {ds_info.get('source')}")
print(f"Target: {ds_info.get('target_column')}")
print(f"Events: {result.get('events')}")

uploaded = _find_uploaded_dataset(state['config'])
print(f"\n_find_uploaded_dataset result: {uploaded is not None}")
if uploaded:
    print(f"  Found: {uploaded['name']}")

tool_calls = result.get('tool_calls', [])
print(f"\nTool calls made: {len(tool_calls)}")
if tool_calls:
    for tc in tool_calls:
        print(f"  - {tc.get('tool')}: success={tc.get('success')}")
else:
    print("  ✓ No tool calls - Discovery used config.dataset_name to find dataset from uploads")

print()
print("=" * 60)
if ds_info.get('name') == 'lending_applications_q3.csv' and ds_info.get('source') == 'upload' and len(tool_calls) == 0:
    print("✓ FIX VERIFIED: Discovery finds dataset from uploads even without LLM")
    print("✓ No search_dataset tool call - avoids tool_choice=none error")
else:
    print("✗ Fix not working - Discovery still calling search tool")