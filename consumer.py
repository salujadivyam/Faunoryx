import os
import pyodbc
import json
import asyncio
from dotenv import load_dotenv
from azure.eventhub.aio import EventHubConsumerClient

load_dotenv()
eventhub_name=os.environ["eventhub_name"]
listen_conn_str=os.environ["listen_conn_str"]
sql_password=os.environ["sql_password"]
sql_username=os.environ["sql_username"]
sql_database=os.environ["sql_database"]
sql_server=os.environ["sql_server"]


class SQL:
    def __init__(self, server, username, database, password):
        driver="{ODBC Driver 18 for SQL Server}"
        conn_str=f"Driver={driver}; Server={server}; Database={database}; UID={username}; PWD={password}"
        self.conn=pyodbc.connect(conn_str)
        self.cursor=self.conn.cursor()


        


