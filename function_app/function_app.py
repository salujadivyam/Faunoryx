import pyodbc
#runs only 2 alert endpoints, anomaly logs and position logs which is served to the dashboard
import os
import azure.functions as fn
import json
import logging

app=fn.FunctionApp()

#anomaly alert endpoint
@app.route(route="alert",auth_level=fn.AuthLevel.FUNCTION)
def alert(req=fn.HttpRequest)->fn.HttpResponse:
    logging.info("Alert function triggered")                #http endpoint that works when an alert is triggered
    try:        
        data=req.get_json()
    except ValueError:
        return fn.HttpResponse("Invalid Json body",status_code=400)  #bad request
    animal_id=data.get("animal_id")
    anomaly_type=data.get("anomaly_type")
    lat=data.get("lat")
    lon=data.get("lon")

    if not animal_id or anomaly_type:       #missing fields
        return fn.HttpResponse("Missing fields",status_code=400)    #bad request
    message=f"ALERT: Tiger {animal_id}-{anomaly_type} detected at ({lat},{lon})"
    logging.warning(message)
    
    return fn.HttpResponse(json.dumps({"status":"received","message":message}),mimetype="application/json",status_code=200)   #ok
