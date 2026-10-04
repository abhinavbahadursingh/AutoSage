"""E2E experiment run through the verification gate."""
import os
import sys
import time
import uuid
import json

import httpx

# Must be set BEFORE importing app.core.config
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"

# Give some time for the server to start (this script will be run after server is up)
API_BASE = "http://localhost:8000/api/v1"

def main():
    client = httpx.Client(timeout=180.0)  # long timeout for ML run

    # 1. Get dev token
    print("1. Getting dev token...")
    resp = client.post(f"{API_BASE}/auth/dev-token", json={
        "email": "test@example.com",
        "name": "Test User"
    })
    assert resp.status_code == 201, f"dev-token failed: {resp.text}"
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   Got token")

    # 2. Create workspace
    ws_name = f"E2E Workspace {uuid.uuid4().hex[:8]}"
    print(f"2. Creating workspace '{ws_name}'...")
    resp = client.post(f"{API_BASE}/workspaces", json={"name": ws_name}, headers=headers)
    assert resp.status_code == 201, f"create workspace failed: {resp.text}"
    workspace = resp.json()
    workspace_id = workspace["id"]
    print(f"   Workspace created: {workspace_id}")

    # 3. Create experiment with telco_churn dataset
    dataset_path = "D:/autoSage/data/uploads/telco_churn_2024.csv"
    exp_name = f"E2E Experiment {uuid.uuid4().hex[:8]}"
    print(f"3. Creating experiment '{exp_name}' with telco_churn...")
    resp = client.post(f"{API_BASE}/experiments", json={
        "name": exp_name,
        "workspace_id": workspace_id,
        "config": {
            "dataset_path": dataset_path,
            "dataset_name": "telco_churn_2024.csv",
            "target_column": "Churn",
            "task_type": "classification",
            "primary_metric": "accuracy",
            "compare_models": True,
            "model_params": {},
        },
        "max_retries": 0,
    }, headers=headers)
    assert resp.status_code == 201, f"create experiment failed: {resp.text}"
    experiment = resp.json()
    experiment_id = experiment["id"]
    print(f"   Experiment created: {experiment_id}")

    # 4. Start experiment
    print("4. Starting experiment...")
    resp = client.post(f"{API_BASE}/experiments/{experiment_id}/start", headers=headers)
    assert resp.status_code == 200, f"start failed: {resp.text}"
    start_result = resp.json()
    print(f"   Started, status: {start_result['status']}")

    # 5. Wait for completion (eager mode runs inline, but worker may return before completion)
    # Poll experiment status
    print("5. Waiting for experiment to complete...")
    for i in range(60):  # up to 5 minutes
        time.sleep(5)
        resp = client.get(f"{API_BASE}/experiments/{experiment_id}", headers=headers)
        assert resp.status_code == 200
        exp = resp.json()
        status = exp["status"]
        print(f"   Poll {i+1}: status={status}")
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            break
    else:
        raise TimeoutError("Experiment did not complete in time")

    assert status == "COMPLETED", f"Experiment failed: {exp}"
    print(f"   Experiment completed!")

    # 6. Verify experiment
    print("6. Running verification gate...")
    resp = client.post(f"{API_BASE}/verification/experiment", json={
        "experiment_id": experiment_id,
    }, headers=headers)
    assert resp.status_code == 200, f"verify experiment failed: {resp.text}"
    verification = resp.json()
    print(f"   Verification overall_status: {verification['overall_status']}")
    print(f"   Verification overall_confidence: {verification['overall_confidence']:.4f}")
    print(f"   Total claims: {verification['total_claims']}")
    print(f"   Verified: {verification['verified_count']}")
    print(f"   Conflict: {verification['conflict_count']}")
    print(f"   Rejected: {verification['rejected_count']}")
    print(f"   Unverified: {verification['unverified_count']}")

    # 7. Check static checks in response
    static = verification.get("static_checks", [])
    print(f"   Static checks ({len(static)}):")
    for check in static:
        print(f"     {check['name']}: {'PASSED' if check['passed'] else 'FAILED'} (skipped={check.get('skipped')})")
        for d in check.get("details", []):
            print(f"       - {d}")

    # 8. Assert VERIFIED
    assert verification["overall_status"] == "VERIFIED", f"Expected VERIFIED, got {verification['overall_status']}"
    print("\n✅ E2E SUCCESS: Experiment verified!")

    # 9. Show evidence in results
    print("\nEvidence summary:")
    for result in verification["results"][:5]:  # first 5
        print(f"  Claim: {result['claim_text'][:80]}")
        print(f"    Status: {result['status']}, Confidence: {result['confidence_score']:.3f}")
        print(f"    Supporting: {len(result['supporting_evidence'])}, Contradicting: {len(result['contradicting_evidence'])}")
        if result["supporting_evidence"]:
            print(f"    First support: {result['supporting_evidence'][0]['content'][:100]}...")

    print("\n🎉 All checks passed!")


if __name__ == "__main__":
    main()