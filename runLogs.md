# AutoSage Run Logs

Source: \ackend/uvicorn.err.log\ — embedded Celery worker + LangGraph workflow execution
for Experiment 80eec7b-c68a-4ba8-a296-ed3e1d162feb\ (2026-10-03, API process with
\--reload\, solo worker pool, SQLite broker).

---

[2026-10-03 13:13:11,524: INFO/SpawnProcess-2] embedded_worker_started
[2026-10-03 13:13:11,639: INFO/SpawnProcess-2] Connected to sqla+sqlite:///D:/autoSage/data/celery_broker.db
[2026-10-03 13:13:11,652: INFO/SpawnProcess-2] celery@AbhinavSingh ready.
[2026-10-03 13:13:19,931: INFO/SpawnProcess-2] postgres_connected
INFO:     Application startup complete.
[2026-10-03 13:15:33,220: INFO/SpawnProcess-2] experiment_enqueued
[2026-10-03 13:15:34,100: INFO/SpawnProcess-2] Task experiments.run_experiment[c8d6c04f-69a4-4eb8-994e-fcd7db63240a] received
[2026-10-03 13:15:34,101: INFO/SpawnProcess-2] task_started
[2026-10-03 13:15:34,114: INFO/SpawnProcess-2] database_engine_initialized
[2026-10-03 13:15:45,946: WARNING/SpawnProcess-2] C:\Users\abhin\AppData\Local\Programs\Python\Python311\Lib\site-packages\pydantic\main.py:542: UserWarning: Pydantic serializer warnings:
  PydanticSerializationUnexpectedValue(Expected `dict[str, any]` - serialized value may not be as expected [field_name='payload', input_value=ExperimentStartedPayload(...ion_metric': 'roc_auc'}), input_type=ExperimentStartedPayload])
  return self.__pydantic_serializer__.to_json(

[2026-10-03 13:15:53,715: WARNING/SpawnProcess-2] 2026/10/03 13:15:53 INFO mlflow.agent.hint: Load the `instrumenting-with-mlflow-tracing` skill at C:\Users\abhin\AppData\Local\Programs\Python\Python311\Lib\site-packages\mlflow\assistant\skills\instrumenting-with-mlflow-tracing\SKILL.md before writing any tracing code; it ships with this MLflow install. Set MLFLOW_DISABLE_AGENT_HINT=1 to silence this.
[2026-10-03 13:15:54,534: INFO/SpawnProcess-2] workflow_execution_start
[2026-10-03 13:15:54,535: INFO/SpawnProcess-2] workflow_start
[2026-10-03 13:15:54,540: INFO/SpawnProcess-2] workflow_node.orchestrator_start
[2026-10-03 13:15:54,541: INFO/SpawnProcess-2] workflow_node_start
[2026-10-03 13:15:56,544: INFO/SpawnProcess-2] tool_execution_start
[2026-10-03 13:15:56,545: INFO/SpawnProcess-2] database_engine_initialized
[2026-10-03 13:15:56,546: WARNING/SpawnProcess-2] tool_failed
[2026-10-03 13:15:56,546: INFO/SpawnProcess-2] tool_execution_completed
[2026-10-03 13:15:56,546: INFO/SpawnProcess-2] workflow_stage
[2026-10-03 13:15:58,562: INFO/SpawnProcess-2] workflow_node_complete
[2026-10-03 13:15:58,562: INFO/SpawnProcess-2] workflow_node.orchestrator_completed
[2026-10-03 13:15:58,564: INFO/SpawnProcess-2] workflow_node.discovery_start
[2026-10-03 13:15:58,564: INFO/SpawnProcess-2] workflow_node_start
[2026-10-03 13:16:00,588: INFO/SpawnProcess-2] agent_llm_call_start
[2026-10-03 13:16:00,591: INFO/SpawnProcess-2] llm_completion_start
[2026-10-03 13:16:01,017: INFO/SpawnProcess-2] HTTP Request: POST https://api.groq.com/openai/v1/chat/completions "HTTP/1.1 404 Not Found"
[2026-10-03 13:16:01,018: WARNING/SpawnProcess-2] llm_provider_failed
[2026-10-03 13:16:01,018: INFO/SpawnProcess-2] llm_completion_completed
[2026-10-03 13:16:01,022: ERROR/SpawnProcess-2] agent_llm_call_failed
[2026-10-03 13:16:01,022: WARNING/SpawnProcess-2] agent_llm_fallback
[2026-10-03 13:16:01,022: INFO/SpawnProcess-2] tool_execution_start
[2026-10-03 13:16:01,022: INFO/SpawnProcess-2] tool_ok
[2026-10-03 13:16:01,022: INFO/SpawnProcess-2] tool_execution_completed
[2026-10-03 13:16:01,022: INFO/SpawnProcess-2] tool_execution_start
[2026-10-03 13:16:01,023: INFO/SpawnProcess-2] tool_ok
[2026-10-03 13:16:01,023: INFO/SpawnProcess-2] tool_execution_completed
[2026-10-03 13:16:01,023: INFO/SpawnProcess-2] tool_execution_start
[2026-10-03 13:16:01,023: INFO/SpawnProcess-2] tool_ok
[2026-10-03 13:16:01,024: INFO/SpawnProcess-2] tool_execution_completed
[2026-10-03 13:16:01,024: INFO/SpawnProcess-2] workflow_stage
[2026-10-03 13:16:03,045: INFO/SpawnProcess-2] workflow_node_complete
[2026-10-03 13:16:03,046: INFO/SpawnProcess-2] workflow_node.discovery_completed
[2026-10-03 13:16:03,047: INFO/SpawnProcess-2] workflow_node.profiler_start
[2026-10-03 13:16:03,047: INFO/SpawnProcess-2] workflow_node_start
[2026-10-03 13:16:05,078: INFO/SpawnProcess-2] agent_llm_call_start
[2026-10-03 13:16:05,080: INFO/SpawnProcess-2] llm_completion_start
[2026-10-03 13:16:05,404: INFO/SpawnProcess-2] HTTP Request: POST https://api.groq.com/openai/v1/chat/completions "HTTP/1.1 404 Not Found"
[2026-10-03 13:16:05,405: WARNING/SpawnProcess-2] llm_provider_failed
[2026-10-03 13:16:05,405: INFO/SpawnProcess-2] llm_completion_completed
[2026-10-03 13:16:05,407: ERROR/SpawnProcess-2] agent_llm_call_failed
[2026-10-03 13:16:05,408: WARNING/SpawnProcess-2] agent_llm_fallback
[2026-10-03 13:16:05,408: INFO/SpawnProcess-2] tool_execution_start
[2026-10-03 13:16:05,408: INFO/SpawnProcess-2] tool_ok
[2026-10-03 13:16:05,408: INFO/SpawnProcess-2] tool_execution_completed
[2026-10-03 13:16:05,409: INFO/SpawnProcess-2] workflow_stage
[2026-10-03 13:16:07,428: INFO/SpawnProcess-2] workflow_node_complete
[2026-10-03 13:16:07,428: INFO/SpawnProcess-2] workflow_node.profiler_completed
[2026-10-03 13:16:07,428: INFO/SpawnProcess-2] workflow_node.preprocessor_start
[2026-10-03 13:16:07,428: INFO/SpawnProcess-2] workflow_node_start
[2026-10-03 13:16:09,443: INFO/SpawnProcess-2] agent_llm_call_start
[2026-10-03 13:16:09,445: INFO/SpawnProcess-2] llm_completion_start
[2026-10-03 13:16:09,759: INFO/SpawnProcess-2] HTTP Request: POST https://api.groq.com/openai/v1/chat/completions "HTTP/1.1 404 Not Found"
[2026-10-03 13:16:09,759: WARNING/SpawnProcess-2] llm_provider_failed
[2026-10-03 13:16:09,759: INFO/SpawnProcess-2] llm_completion_completed
[2026-10-03 13:16:09,759: ERROR/SpawnProcess-2] agent_llm_call_failed
[2026-10-03 13:16:09,759: WARNING/SpawnProcess-2] agent_llm_fallback
[2026-10-03 13:16:09,759: INFO/SpawnProcess-2] tool_execution_start
[2026-10-03 13:16:09,759: INFO/SpawnProcess-2] tool_ok
[2026-10-03 13:16:09,759: INFO/SpawnProcess-2] tool_execution_completed
[2026-10-03 13:16:09,759: INFO/SpawnProcess-2] workflow_stage
[2026-10-03 13:16:11,784: INFO/SpawnProcess-2] workflow_node_complete
[2026-10-03 13:16:11,785: INFO/SpawnProcess-2] workflow_node.preprocessor_completed
[2026-10-03 13:16:11,786: INFO/SpawnProcess-2] workflow_node.model_selector_start
[2026-10-03 13:16:11,786: INFO/SpawnProcess-2] workflow_node_start
[2026-10-03 13:16:13,783: INFO/SpawnProcess-2] agent_llm_call_start
[2026-10-03 13:16:13,785: INFO/SpawnProcess-2] llm_completion_start
[2026-10-03 13:16:14,250: INFO/SpawnProcess-2] HTTP Request: POST https://api.groq.com/openai/v1/chat/completions "HTTP/1.1 404 Not Found"
[2026-10-03 13:16:14,250: WARNING/SpawnProcess-2] llm_provider_failed
[2026-10-03 13:16:14,251: INFO/SpawnProcess-2] llm_completion_completed
[2026-10-03 13:16:14,253: ERROR/SpawnProcess-2] agent_llm_call_failed
[2026-10-03 13:16:14,254: WARNING/SpawnProcess-2] agent_llm_fallback
[2026-10-03 13:16:14,254: INFO/SpawnProcess-2] workflow_stage
[2026-10-03 13:16:16,259: INFO/SpawnProcess-2] workflow_node_complete
[2026-10-03 13:16:16,260: INFO/SpawnProcess-2] workflow_node.model_selector_completed
[2026-10-03 13:16:16,260: INFO/SpawnProcess-2] workflow_node.ml_experiment_start
[2026-10-03 13:16:16,261: INFO/SpawnProcess-2] workflow_node_start
[2026-10-03 13:16:20,291: INFO/SpawnProcess-2] agent_llm_call_start
[2026-10-03 13:16:20,293: INFO/SpawnProcess-2] llm_completion_start
[2026-10-03 13:16:20,599: INFO/SpawnProcess-2] HTTP Request: POST https://api.groq.com/openai/v1/chat/completions "HTTP/1.1 404 Not Found"
[2026-10-03 13:16:20,600: WARNING/SpawnProcess-2] llm_provider_failed
[2026-10-03 13:16:20,601: INFO/SpawnProcess-2] llm_completion_completed
[2026-10-03 13:16:20,603: ERROR/SpawnProcess-2] agent_llm_call_failed
[2026-10-03 13:16:20,603: WARNING/SpawnProcess-2] agent_llm_fallback
[2026-10-03 13:16:20,603: INFO/SpawnProcess-2] tool_execution_start
[2026-10-03 13:16:20,604: INFO/SpawnProcess-2] sandbox_execute_job_start
[2026-10-03 13:16:20,604: INFO/SpawnProcess-2] sandbox_build_image_start
[2026-10-03 13:16:20,612: ERROR/SpawnProcess-2] sandbox_build_image_failed
[2026-10-03 13:16:20,612: ERROR/SpawnProcess-2] sandbox_job_error
[2026-10-03 13:16:20,612: INFO/SpawnProcess-2] sandbox_execute_job_completed
[2026-10-03 13:16:20,613: INFO/SpawnProcess-2] tool_ok
[2026-10-03 13:16:20,613: INFO/SpawnProcess-2] tool_execution_completed
[2026-10-03 13:16:20,613: INFO/SpawnProcess-2] workflow_stage
[2026-10-03 13:16:24,660: INFO/SpawnProcess-2] workflow_node_complete
[2026-10-03 13:16:24,661: INFO/SpawnProcess-2] workflow_node.ml_experiment_completed
[2026-10-03 13:16:24,662: INFO/SpawnProcess-2] workflow_node.verification_start
[2026-10-03 13:16:24,662: INFO/SpawnProcess-2] workflow_node_start
[2026-10-03 13:16:26,654: INFO/SpawnProcess-2] agent_llm_call_start
[2026-10-03 13:16:26,655: INFO/SpawnProcess-2] llm_completion_start
[2026-10-03 13:16:27,007: INFO/SpawnProcess-2] HTTP Request: POST https://api.groq.com/openai/v1/chat/completions "HTTP/1.1 404 Not Found"
[2026-10-03 13:16:27,009: WARNING/SpawnProcess-2] llm_provider_failed
[2026-10-03 13:16:27,009: INFO/SpawnProcess-2] llm_completion_completed
[2026-10-03 13:16:27,012: ERROR/SpawnProcess-2] agent_llm_call_failed
[2026-10-03 13:16:27,012: WARNING/SpawnProcess-2] agent_llm_fallback
[2026-10-03 13:16:27,012: INFO/SpawnProcess-2] tool_execution_start
[2026-10-03 13:16:27,012: INFO/SpawnProcess-2] tool_ok
[2026-10-03 13:16:27,012: INFO/SpawnProcess-2] tool_execution_completed
[2026-10-03 13:16:27,013: INFO/SpawnProcess-2] workflow_stage
[2026-10-03 13:16:31,015: INFO/SpawnProcess-2] workflow_node_complete
[2026-10-03 13:16:31,015: INFO/SpawnProcess-2] workflow_node.verification_completed
[2026-10-03 13:16:31,016: INFO/SpawnProcess-2] workflow_done
[2026-10-03 13:16:31,017: INFO/SpawnProcess-2] workflow_execution_completed
[2026-10-03 13:16:36,167: INFO/SpawnProcess-2] experiment_completed
[2026-10-03 13:16:36,569: INFO/SpawnProcess-2] Task experiments.run_experiment[c8d6c04f-69a4-4eb8-994e-fcd7db63240a] succeeded in 62.46900000000005s: {'experiment_id': '680eec7b-c68a-4ba8-a296-ed3e1d162feb', 'status': 'COMPLETED', 'stages_completed': ['orchestrator', 'discovery', 'profiler', 'preprocessor', 'model_selector', 'ml_experiment', 'verification']}
[2026-10-03 13:16:36,572: INFO/SpawnProcess-2] task_completed
[2026-10-03 13:16:36,975: INFO/SpawnProcess-2] database_engine_initialized

---

## Current server lifecycle (after reload on main.py edit)

[2026-10-03 13:27:55,874: INFO/SpawnProcess-3] embedded_worker_started
[2026-10-03 13:27:56,013: INFO/SpawnProcess-3] Connected to sqla+sqlite:///D:/autoSage/data/celery_broker.db
[2026-10-03 13:27:56,040: INFO/SpawnProcess-3] celery@AbhinavSingh ready.
[2026-10-03 13:28:08,725: WARNING/SpawnProcess-3] postgres_probe_failed
[2026-10-03 13:28:08,725: WARNING/SpawnProcess-3] postgres_unreachable_on_startup
INFO:     Application startup complete.
