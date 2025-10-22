import os, io
import pyarrow.parquet as pq
from inferencer import Inferencer
<<<<<<< Updated upstream
ENABLE_KAFKA = os.getenv("ENABLE_KAFKA", "0").lower() in {"1", "true", "yes"}
if ENABLE_KAFKA:
	from kafka_utils import create_producer
=======
import os
from kafka_utils import create_producer
>>>>>>> Stashed changes
from client_utils import get_file

GATEWAY_URL = os.environ['GATEWAY_URL']
EXPERIMENT = os.environ.get('MANUAL_EXPERIMENT','Default')
RUN_NAME = os.environ.get('MANUAL_RUN','GRU')
IDENTIFIER = os.environ.get('IDENTIFIER','manualtest')

print(f"[manual_infer] Starting manual inference for experiment={EXPERIMENT} run={RUN_NAME} identifier={IDENTIFIER}")
<<<<<<< Updated upstream
=======
ENABLE_KAFKA = os.getenv("ENABLE_KAFKA", "false").lower() == "true"
>>>>>>> Stashed changes
print(f"[config] Kafka enabled: {ENABLE_KAFKA}")
producer = create_producer() if ENABLE_KAFKA else None
inf = Inferencer(GATEWAY_URL, producer, 'DLQ-performance-eval','performance-eval')
inf.load_model(EXPERIMENT, RUN_NAME)

print("[manual_infer] Downloading evaluation parquet")
parquet_buf = get_file(GATEWAY_URL,'processed-data','test_processed_data.parquet')
parquet_buf.seek(0,2)
size = parquet_buf.tell()
parquet_buf.seek(0)
print(f"[manual_infer] Parquet bytes: {size}")

table = pq.read_table(source=parquet_buf)
df = table.to_pandas()
print(f"[manual_infer] DataFrame shape: {df.shape}")

print("[manual_infer] Running perform_inference()")
inf.perform_inference(df)
print("[manual_infer] Done.")
