import pyodbc
#runs only 2 alert endpoints, anomaly logs and position logs which is served to the dashboard
import os
import azure.functions as fn
import json
import logging

app=fn.FunctionApp()

def get_connection():
    driver="{ODBC Driver 18 for SQL Server}"
    server=os.environ["sql_server"]
    database=os.environ["sql_database"]
    username=os.environ["sql_username"]
    password=os.environ["sql_password"]

    conn_str=f"Driver={driver};Server={server};Database={database}; UID={username};PWD={password}"
    return pyodbc.connect(conn_str)

#anomaly alert endpoint
@app.route(route="alert",auth_level=fn.AuthLevel.FUNCTION)
def alert(req:fn.HttpRequest)->fn.HttpResponse:
    logging.info("Alert function triggered")                #http endpoint that works when an alert is triggered
    try:        
        data=req.get_json()
    except ValueError:
        return fn.HttpResponse("Invalid Json body",status_code=400)  #bad request
    animal_id=data.get("animal_id")
    anomaly_type=data.get("anomaly_type")
    lat=data.get("lat")
    lon=data.get("lon")

    if not animal_id or not anomaly_type or lat is None or lon is None:       #missing fields
        return fn.HttpResponse("Missing fields",status_code=400)    #bad request
    message=f"ALERT: Tiger {animal_id}-{anomaly_type} detected at ({lat},{lon})"
    logging.warning(message)
    
    return fn.HttpResponse(json.dumps({"status":"received","message":message}),mimetype="application/json",status_code=200)   #ok


#telemetry position endpoint
@app.route(route="positions",auth_level=fn.AuthLevel.ANONYMOUS)
def positions(req:fn.HttpRequest)->fn.HttpResponse:
    logging.info("Positions function has been triggered")
    try:
        conn=get_connection()
        cursor=conn.cursor()

        cursor.execute("""SELECT t.animal_id,t.lat, t.lon ,t.speed_kmph, t.still,t.speed_anomaly, t.outside_boundary FROM AnimalTelemetry AS t
        WHERE t.timestamp=(SELECT MAX(t2.timestamp) FROM AnimalTelemetry AS t2 WHERE t2.animal_id=t.animal_id)""")  #gives the latest record for each animal

        rows=cursor.fetchall()
        res=[]
        for row in rows:
            res.append({
                "animal_id":row[0],"lat":row[1], "lon":row[2] ,"speed_kmph":row[3],"still":row[4],"speed_anomaly":row[5],
                "outside_boundary":row[6]})

        cursor.close()
        conn.close()
        return fn.HttpResponse(json.dumps(res),mimetype="application/json",status_code=200)   #ok

    except Exception as e:
        logging.error(f"Position endpoint failed: {e}")
        return fn.HttpResponse(json.dumps({"error":str(e)}),mimetype="application/json",status_code=500)  #internal server error 


@app.route(route="history",auth_level=fn.AuthLevel.ANONYMOUS)       #used so that on clicking a marker we can see the previous path of the tiger, and all its previous positions
def history(req:fn.HttpRequest)->fn.HttpResponse:
    logging.info("History function triggered")

    try:
        animal_id=req.params.get("animal_id")

        if not animal_id:
            return fn.HttpResponse(
                json.dumps({"error":"animal_id missing"}),mimetype="application/json",status_code=400)

        conn=get_connection()
        cursor=conn.cursor()

        cursor.execute("""SELECT animal_id,timestamp,lat,lon FROM AnimalTelemetry where animal_id=? order by timestamp""",animal_id)

        rows=cursor.fetchall()

        res=[]
        for row in rows:
            res.append({"animal_id":row[0],"timestamp": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),"lat":row[2],"lon":row[3]})

        cursor.close()
        conn.close()
        return fn.HttpResponse(json.dumps(res),mimetype="application/json",status_code=200) #ok

    except Exception as e:
        logging.error(f"History endpoint failed: {e}")
        return fn.HttpResponse(json.dumps({"error":str(e)}),mimetype="application/json",status_code=500)    #internal server error

