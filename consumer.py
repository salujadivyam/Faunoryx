import os
import json
import asyncio
from functools import partial
from dotenv import load_dotenv
from azure.eventhub.aio import EventHubConsumerClient
from functools import partial
from sql_writer import SQL

load_dotenv()
eventhub_name=os.environ["eventhub_name"]
listen_conn_str=os.environ["listen_conn_str"]
sql_password=os.environ["sql_password"]
sql_username=os.environ["sql_username"]                #taking all the variables from the .env file
sql_database=os.environ["sql_database"]
sql_server=os.environ["sql_server"]


async def on_event(partition_context,event,sql_writer):             #this function will run whenever an event is triggered
    body=event.body_as_str()
    ping=json.load(body)
    sql_writer.insert_telemetry(ping)

    if ping["still"]:
        sql_writer.insert_anomaly(ping,"stillness")
    if ping["speed_anomaly"]:
        sql_writer.insert_anomaly(ping,"speed_anomaly")
    if ping["outside_boundary"]:
        sql_writer.insert_anomaly(ping,"boundary_excursion")

async def main():
    sql_writer=SQL(sql_server,sql_username,sql_database,sql_password)
    client=EventHubConsumerClient.from_connection_string(conn_str=listen_conn_str,
                                                         consumer_group="$Default",
                                                         eventhub_name=eventhub_name)
    handler=partial(on_event,sql_writer=sql_writer)
    print("consumer has started, now are listening for events")
    async with client:
        await client.receive(on_evnt=handler,starting_position="-1")
if __name__=="__main__":
    asyncio.run(main())



        


