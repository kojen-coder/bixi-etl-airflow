from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from delta.tables import DeltaTable
import requests
import os
from pyspark.sql import SparkSession
import pyspark.sql.functions as F

os.environ['NO_PROXY'] = '*'

# Set Delta Lake version
delta_version = "2.4.0"  # Use Delta Lake 2.4.0 for Spark 3.4.0

# Create a Spark session with Delta support
spark = SparkSession.builder \
    .appName("BixiDeltaTable") \
    .config("spark.jars.packages", f"io.delta:delta-core_2.12:{delta_version}") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

# Set the path for the Delta table
delta_table_path = '../bixi_data/delta_table'
# Temporary path to store the intermediate Parquet file
temp_parquet_path = '../bixi_data/temp_parquet/df_combined.parquet'

# Define the DAG
with DAG(
    dag_id='bixi_etl_pipeline',
    schedule_interval='*/5 * * * *',  # You can adjust the schedule as needed. '*/15 * * * *'
    start_date=datetime(2023, 1, 1),
    catchup=False
) as dag:

    def fetch_data(**kwargs):
        os.environ['NO_PROXY'] = '*'

        # URLs for station information and status
        station_info_url = "https://gbfs.velobixi.com/gbfs/en/station_information.json"
        station_status_url = "https://gbfs.velobixi.com/gbfs/en/station_status.json"
        
        # Fetch station information and status
        station_info_response = requests.get(station_info_url)
        station_status_response = requests.get(station_status_url)
        
        # Convert to JSON
        station_info = station_info_response.json()
        station_status = station_status_response.json()

        # Push data to XComs (stations_info_list and stations_status_list)
        ti = kwargs['ti']
        ti.xcom_push(key='stations_info_list', value=station_info['data']['stations'])
        ti.xcom_push(key='stations_status_list', value=station_status['data']['stations'])

    def transform_data(**kwargs):
        """Read the data from XComs, combine into a DataFrame, and save to a Parquet file."""
        # Fetch data from XComs
        ti = kwargs['ti']
        stations_info_list = ti.xcom_pull(key='stations_info_list', task_ids='extract_task')
        stations_status_list = ti.xcom_pull(key='stations_status_list', task_ids='extract_task')

        # Convert both lists to Spark DataFrames
        df_info = spark.createDataFrame(stations_info_list)
        df_status = spark.createDataFrame(stations_status_list)\
                    .withColumn("last_reported", F.col("last_reported").cast("timestamp"))

        # Merge the station information with status on 'station_id'
        df_combined = df_info.join(df_status, 'station_id', 'inner')

        # Select only the required columns
        df_final = df_combined.select(
            'station_id',
            'name',
            'lat',
            'lon',
            'capacity',
            'num_bikes_available',
            'num_ebikes_available',
            'num_bikes_disabled',
            'num_docks_available',
            'num_docks_disabled',
            'is_renting',
            'is_returning',
            'last_reported'
        )

        # Ensure the temporary directory exists
        os.makedirs(os.path.dirname(temp_parquet_path), exist_ok=True)

        # Save the combined DataFrame to a Parquet file (temp file for the next task)
        df_final.write.mode("overwrite").parquet(temp_parquet_path)

    def load_data_to_delta(**kwargs):
        """Load the transformed data from Parquet into the Delta table."""
        # Read the combined DataFrame from the Parquet file
        df_combined = spark.read.parquet(temp_parquet_path)

        # Check if the Delta table exists
        if DeltaTable.isDeltaTable(spark, delta_table_path):
            # If the table exists, use Delta's merge operation for upsert
            delta_table = DeltaTable.forPath(spark, delta_table_path)

            # Perform the merge (upsert) to avoid duplicates based on 'station_id' and 'last_reported'
            delta_table.alias("existing") \
                .merge(
                    df_combined.alias("new"), 
                    "existing.station_id = new.station_id AND existing.last_reported = new.last_reported"
                ) \
                .whenMatchedUpdateAll() \
                .whenNotMatchedInsertAll() \
                .execute()
        else:
            # If the Delta table does not exist, create it
            df_combined.write.format("delta").save(delta_table_path)

    # Define the tasks
    extract_task = PythonOperator(
        task_id='extract_task',
        python_callable=fetch_data,
        provide_context=True  # Ensures Airflow passes the context for XComs
    )

    transform_task = PythonOperator(
        task_id='transform_task',
        python_callable=transform_data,
        provide_context=True  # Ensures Airflow passes the context for XComs
    )

    load_task = PythonOperator(
        task_id='load_task',
        python_callable=load_data_to_delta,
        provide_context=True  # Ensures Airflow passes the context for XComs
    )

    # Set task dependencies
    extract_task >> transform_task >> load_task
