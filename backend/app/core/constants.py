# File parsing
UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB
EXCEL_BATCH_SIZE = 10_000  # rows per COPY batch
DB_BATCH_SIZE = 1_000  # rows per executemany / ANY() batch

# Reconciliation
RECONCILE_LOOKUP_BATCH = 1_000  # bank_ids per SQL query

# Fuzzy matching
FUZZY_SIMILARITY_THRESHOLD = 0.3  # pg_trgm minimum
FUZZY_MAX_CANDIDATES = 5  # per unmatched ID

# Anomaly detection
ANOMALY_AMOUNT_ZSCORE = 3.0  # standard deviations for outlier
ANOMALY_DATE_WINDOW_DAYS = 365  # expected transaction window

# Export
CSV_STREAM_BATCH = 5_000  # rows per streaming chunk
