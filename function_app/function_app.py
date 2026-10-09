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

        cursor.execute("""SELECT t.animal_id,t.lat, t.lon ,t.speed_kmph, t.still,t.speed_anomaly, t.outside_boundary, t.behaviour FROM AnimalTelemetry AS t
        WHERE t.timestamp=(SELECT MAX(t2.timestamp) FROM AnimalTelemetry AS t2 WHERE t2.animal_id=t.animal_id)""")  #gives the latest record for each animal

        rows=cursor.fetchall()
        res=[]
        for row in rows:
            res.append({
                "animal_id":row[0],"lat":row[1], "lon":row[2] ,"speed_kmph":row[3],"still":row[4],"speed_anomaly":row[5],
                "outside_boundary":row[6],"behaviour":row[7]})

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


@app.route(route="stats",auth_level=fn.AuthLevel.ANONYMOUS)       #feeds dashboard pie chart, counters, top-5 fastest panel
def stats(req:fn.HttpRequest)->fn.HttpResponse:
    logging.info("Stats function triggered")
    try:
        conn=get_connection()
        cursor=conn.cursor()

        cursor.execute("""SELECT t.behaviour, t.speed_kmph, t.still, t.outside_boundary, t.animal_id FROM AnimalTelemetry AS t
        WHERE t.timestamp=(SELECT MAX(t2.timestamp) FROM AnimalTelemetry AS t2 WHERE t2.animal_id=t.animal_id)""")
        rows=cursor.fetchall()

        behaviour_counts={"normal":0,"sustained-fast":0,"hunting":0}
        still_count=0
        outside_count=0
        speeds=[]
        for row in rows:
            behaviour,speed,still,outside,animal_id=row
            if behaviour in behaviour_counts:
                behaviour_counts[behaviour]+=1
            if still:
                still_count+=1
            if outside:
                outside_count+=1
            speeds.append((animal_id,speed))

        speeds.sort(key=lambda x:x[1],reverse=True)
        top5=[{"animal_id":a,"speed_kmph":s} for a,s in speeds[:5]]
        avg_speed=sum(s for _,s in speeds)/len(speeds) if speeds else 0

        res={
            "total_tigers":len(rows),
            "behaviour_counts":behaviour_counts,
            "still_count":still_count,
            "outside_count":outside_count,
            "avg_speed_kmph":round(avg_speed,2),
            "top5_fastest":top5
        }

        cursor.close()
        conn.close()
        return fn.HttpResponse(json.dumps(res),mimetype="application/json",status_code=200)

    except Exception as e:
        logging.error(f"Stats endpoint failed: {e}")
        return fn.HttpResponse(json.dumps({"error":str(e)}),mimetype="application/json",status_code=500)

@app.route(route="recent-anomalies",auth_level=fn.AuthLevel.ANONYMOUS)
def recent_anomalies(req:fn.HttpRequest)->fn.HttpResponse:
    logging.info("Recent Anomalies function has been triggered")

    try:
        conn=get_connection()
        cursor=conn.cursor()
        cursor.execute("""SELECT TOP 20 animal_id,timestamp,lat,lon,anomaly_type FROM MovementAnomalies ORDER BY timestamp DESC""")
        rows=cursor.fetchall()
        res=[]
        for row in rows:
            res.append({"animal_id":row[0],"timestamp":row[1].isoformat() if hasattr(row[1],"isoformat") else str(row[1]),"lat":row[2],"lon":row[3],"anomaly_type":row[4]})
        cursor.close()
        conn.close()
        return fn.HttpResponse(json.dumps(res),mimetype="application/json",status_code=200)
    except Exception as e:
        logging.error(f"Recent Anomalies endpoint has failed: {e}")
        return fn.HttpResponse(json.dumps({"error":str(e)}),mimetype="application/json",status_code=500)

@app.route(route="trend",auth_level=fn.AuthLevel.ANONYMOUS)
def trend(req:fn.HttpRequest)->fn.HttpResponse:
    logging.info("Trend function triggered")


    try:
        conn=get_connection()
        cursor=conn.cursor()
        cursor.execute("""SELECT DATEPART(hour,timestamp) AS hr, anomaly_type, COUNT(*) AS cnt FROM MovementAnomalies
        WHERE timestamp>=DATEADD(hour,-24,SYSUTCDATETIME()) GROUP BY DATEPART(hour,timestamp),anomaly_type ORDER BY hr""")
        rows=cursor.fetchall()
        res=[{"hour":row[0],"anomaly_type":row[1],"count":row[2]} for row in rows]
        cursor.close()
        conn.close()
        
        return fn.HttpResponse(json.dumps(res),mimetype="application/json",status_code=200)
    except Exception as e:
        logging.error(f"Trend endpoint failed: {e}")
        return fn.HttpResponse(json.dumps({"error":str(e)}),mimetype="application/json",status_code=500)
