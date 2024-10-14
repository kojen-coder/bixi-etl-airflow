from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import requests
import pandas as pd
import os

os.environ['NO_PROXY'] = '*'

# Define the DAG
with DAG(
    dag_id='bixi_dag_combined',
    schedule_interval=None,  # Run manually '*/15 * * * *'
    start_date=datetime(2023, 1, 1),
    catchup=False
) as dag:

    def fetch_data(**kwargs):
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
        """Read the data from XComs, combine, and save to a Parquet file."""
        # Fetch data from XComs
        ti = kwargs['ti']
        stations_info_list = ti.xcom_pull(key='stations_info_list', task_ids='extract_task')
        stations_status_list = ti.xcom_pull(key='stations_status_list', task_ids='extract_task')

        # Convert both lists to DataFrames
        df_info = pd.DataFrame(stations_info_list)
        df_status = pd.DataFrame(stations_status_list)

        # Merge the station information with status on 'station_id'
        df_combined = pd.merge(df_info, df_status, on='station_id')

        # Convert Unix time (seconds) to a human-readable format in the 'last_reported' column
        df_combined['last_reported'] = df_combined['last_reported'].apply(
            lambda x: datetime.fromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(x) else None
        )

        # Select the relevant columns
        df_final = df_combined[[
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
        ]]

        # Generate the output file name with current timestamp
        current_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        output_file = f'../bixi_data/stations_combined_{current_timestamp}.parquet'

        # Ensure the directory exists
        os.makedirs('../bixi_data', exist_ok=True)

        # Save the combined DataFrame as a Parquet file
        df_final.to_parquet(output_file, index=False)

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

    # Set task dependencies
    extract_task >> transform_task
