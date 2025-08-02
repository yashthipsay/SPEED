import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO
from datetime import datetime

class S3Persistor:
    """Handles formatting and writing of trading data to AWS S3 as Parquet files."""

    def __init__(self, bucket_name: str, aws_access_key: str, aws_secret_key: str, region: str):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=region
        )
        print(f"✅ S3Persistor initialized for bucket: {self.bucket_name}")


    def write_orderbook_snapshot(self, exchange: str, symbol: str, snapshot:dict):
        """
        Converts an order book snapshot to a partitioned Parquet object and writes it to S3.
        """
        try:
            # Get a high-precision UTC timestamp
            utc_now = datetime.utcnow()

            # Create a DataFrame based on the required schema
            data = {
                'timestamp': [utc_now],
                'exchange': [exchange],
                'symbol': [symbol],
                'bids': [snapshot['bids']],
                'asks': [snapshot['asks']]
            }
            df = pd.DataFrame(data)

            # Define the S3 path with partitioning

            sanitized_symbol = symbol.replace('/', '-')
            s3_key = (
                f"orderbooks/date={utc_now.strftime('%Y-%m-%d')}/"
                f"pair={sanitized_symbol}/"
                f"{int(utc_now.timestamp() * 1000)}.parquet"
            )

            # Write Dataframe to a Paraquet object in memory
            parquet_buffer = BytesIO()
            df.to_parquet(parquet_buffer, engine='pyarrow')

            # Upload the in-memory object to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=parquet_buffer.getvalue()
            )
            print(f"Successfully wrote {s3_key} to S3.")

        except Exception as e:
            print(f"❌ Error writing to S3: {e}")