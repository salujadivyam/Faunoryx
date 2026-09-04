import pyodbc

class SQL:
    def __init__(self,server,username,database,password):
        conn_str=f"Driver={driver};Server={server};Database={database};UID={username};PWD={password}"
        self.conn=pyodbc.connect(conn_str)
        self.cursor=self.conn.cursor()
        driver="{ODBC Driver 18 for SQL Server}"

    def insert_telemetry(self,ping):
        self.cursor.execute( """INSERT INTO AnimalTelemetry(animal_id, timestamp, lat,lon, speed_kmph,still, speed_anomaly,outside_boundary)
        VALUES(?,?,?,?,?,?,?,?)""")
        self.conn.commit()

