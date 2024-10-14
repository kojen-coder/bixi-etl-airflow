# BIXI Bike Station Data Pipelines with Delta Lake (Ongoing)

BIXI is a popular bike-sharing system in Montreal, offering over 600 stations and handling millions of trips each year. With frequent data updates provided by BIXI’s real-time GBFS (General Bikeshare Feed Specification) feed, this project aims to build a scalable and efficient data pipeline to capture, store, and manage real-time station and bike availability data.

## Project Goal

The goal of this project is to create a real-time data pipeline that processes frequent updates (every 10 seconds) from BIXI's feed, handles data deduplication, and ensures continuous ingestion through automated scheduling. By integrating robust data engineering practices such as ACID compliance, the use of Delta Tables for upserts, and leveraging Apache Airflow for job scheduling, this project ensures that the data is accurate, reliable, and scalable.

## Key Challenges

### 1. **High-Frequency Updates**
- **Challenge**: The BIXI system updates station data every 10 seconds, meaning that the `last_reported` timestamps for stations change frequently. This creates a challenge in ensuring data completeness while managing high-frequency updates.
- **Solution**: The pipeline schedules jobs with Apache Airflow to automatically fetch new data at regular intervals. Delta Lake’s upsert (merge) functionality helps ensure only unique or changed data is stored, ensuring ACID properties are maintained and avoiding duplicate records.

### 2. **Data Deduplication**
- **Challenge**: Due to the high update frequency, fetching the same data multiple times risks storing redundant data in the dataset.
- **Solution**: The use of Delta Tables allows for efficient deduplication via upserts, where only new or changed records are inserted. This is crucial in managing the station data, ensuring the pipeline adheres to ACID principles (Atomicity, Consistency, Isolation, Durability) while maintaining data integrity.

### 3. **Handling Large and Growing Data Volumes**
- **Challenge**: As real-time data accumulates, the volume of data grows rapidly, requiring scalable storage solutions.
- **Solution**: Apache Spark and Delta Lake are utilized to handle large datasets efficiently. Data is saved in Parquet format initially and later merged into Delta Tables, which provides both efficient querying and storage.

### 4. **Automation and Scheduling**
- **Challenge**: Manually running the pipeline to fetch data would be inefficient and error-prone, especially given the rapid update frequency of the data.
- **Solution**: Apache Airflow is used to schedule jobs for data ingestion, automating the ETL (Extract, Transform, Load) process. This ensures continuous, reliable data ingestion without manual intervention and supports CI/CD practices for deploying and maintaining the pipeline.

### 5. **Ensuring Data Completeness**
- **Challenge**: For high-usage stations, frequent changes in station data mean the risk of missing updates if data isn’t fetched quickly enough.
- **Solution**: By fine-tuning Airflow’s job scheduling intervals and leveraging streaming solutions in future versions (like Apache Kafka), the pipeline ensures that no updates are missed and that the system captures the full data history.

## Technologies and Tools

- **Apache Airflow**: Handles the scheduling of data ingestion jobs, ensuring automation and the continuous operation of the pipeline.
- **Apache Spark**: Powers the transformation and processing of large datasets efficiently.
- **Delta Lake**: Provides ACID transactions, upsert capabilities, and efficient management of frequent updates through Delta Tables.
- **Apache Kafka** (Upcoming): Will be used for real-time streaming ingestion to ensure no data is lost and further optimize the pipeline for high-frequency updates.
- **Parquet**: A columnar storage format used to store large datasets in an efficient manner, reducing storage costs while enabling fast queries.
- **SQLite**: Used initially for simple data storage but later replaced by scalable solutions like Parquet and Delta Lake for improved performance.
- **CI/CD Practices**: Continuous Integration and Continuous Deployment practices are followed to maintain, test, and deploy the pipeline efficiently.
