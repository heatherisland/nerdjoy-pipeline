FROM quay.io/astronomer/astro-runtime:12.1.1

COPY src /usr/local/airflow/src
COPY dbt /usr/local/airflow/dbt
COPY dashboard /usr/local/airflow/dashboard
COPY scripts /usr/local/airflow/scripts

ENV PYTHONPATH=/usr/local/airflow/src:$PYTHONPATH
