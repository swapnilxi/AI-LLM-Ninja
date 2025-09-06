# Makefile

AIRFLOW_VERSION=2.9.3
PYTHON_MINOR=3.12
CONSTRAINT_URL=https://raw.githubusercontent.com/apache/airflow/constraints-$(AIRFLOW_VERSION)/constraints-$(PYTHON_MINOR).txt
AIRFLOW_HOME=$(CURDIR)/airflow_home

# Create venv with Python 3.12
airflow-venv:
	uv python install $(PYTHON_MINOR)
	uv venv --python $(PYTHON_MINOR) .venv-airflow
	@echo "✅ Airflow venv created at .venv-airflow"
	@echo "👉 Activate with: source .venv-airflow/bin/activate"

# Install Airflow with pinned constraints
airflow-install: airflow-venv
	source .venv-airflow/bin/activate && \
	uv pip install "apache-airflow==$(AIRFLOW_VERSION)" --constraint "$(CONSTRAINT_URL)"

# Initialize Airflow DB and create default admin
airflow-init:
	mkdir -p $(AIRFLOW_HOME)/dags
	source .venv-airflow/bin/activate && \
	AIRFLOW_HOME=$(AIRFLOW_HOME) uv run airflow db init && \
	AIRFLOW_HOME=$(AIRFLOW_HOME) uv run airflow users create \
	  --username admin --password admin \
	  --firstname A --lastname U --role Admin --email admin@example.com

# Run Airflow standalone (scheduler + webserver)
airflow-up:
	source .venv-airflow/bin/activate && \
	AIRFLOW_HOME=$(AIRFLOW_HOME) uv run airflow standalone
