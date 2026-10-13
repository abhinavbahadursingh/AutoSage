import sys
sys.path.insert(0, r'D:\autoSage\backend')

from app.agents.discovery import discovery_node
from app.agents.state import ExperimentWorkflowState

# Simulate the exact loan-default experiment from NewExperiment.tsx
state = {
    'experiment_id': 'loan-default-experiment',
    'workspace_id': 'test-ws',
    'attempt': 0,
    'max_attempts': 3,
    'current_stage': 'queued',
    'status': 'RUNNING',
    'stages_completed': [],
    'events': ['experiment loan-default-experiment queued'],
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
        'prompt': 'Classify loan default yes/no using the Lending Q3 dataset',
        'dataset': 'lending_applications_q3.csv',
        'dataset_name': 'lending_applications_q3.csv',  # THIS IS KEY
        'dataset_path': 'lending_applications_q3.csv',
        'target_column': 'defaulted',
        'task_type': 'classification',
        'evaluation_metric': 'accuracy',
    },
    'primary_metric': 'accuracy',
    'compare_models': False,
}

result = discovery_node(state)
ds_info = result.get('dataset_info', {})

print("=== Discovery Result ===")
print(f"Dataset name: {ds_info.get('name')}")
print(f"Target column: {ds_info.get('target_column')}")
print(f"Source: {ds_info.get('source')}")
print(f"Rows: {ds_info.get('rows')}")
print(f"Events: {result.get('events')}")

# Critical check: Was the search tool called?
tool_calls = result.get('tool_calls', [])
if tool_calls:
    print(f"\nTool calls made: {len(tool_calls)}")
    for tc in tool_calls:
        print(f"  - {tc.get('tool')}: success={tc.get('success')}")
else:
    print(f"\n✓ No tool calls made - Discovery used config.dataset_name to find dataset from uploads")

# Verify the fix
if ds_info.get('name') == 'lending_applications_q3.csv' and ds_info.get('source') == 'upload':
    print("\n✓ FIX VERIFIED: Discovery found dataset from uploads using config.dataset_name")
    print("✓ No search tool call needed - avoids tool_choice=none error with Groq")
else:
    print("\n✗ Discovery did not find the expected dataset")