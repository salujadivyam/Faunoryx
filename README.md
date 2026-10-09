# Faunoryx

Faunoryx is a simulated live tracking system for 149 tigers in Nagarahole Tiger Reserve. It runs on Azure and the whole setup is created with Terraform.

A Python script moves the tigers around inside the real reserve boundary and sends their GPS pings to Azure Event Hubs. A second script reads those pings and saves them in Azure SQL. Azure Functions serve the data as an API, and a dashboard built on Azure Maps shows where every tiger is, how it is behaving and where it has been.

![Dashboard overview](docs/images/01-dashboard-overview.png)

## Contents

1. [How it fits together](#how-it-fits-together)
2. [Tools used](#tools-used)
3. [Folder layout](#folder-layout)
4. [The simulator](#the-simulator)
5. [Terraform](#terraform)
6. [Consumer and SQL writer](#consumer-and-sql-writer)
7. [Database tables](#database-tables)
8. [Azure Functions API](#azure-functions-api)
9. [Alerts](#alerts)
10. [The dashboard](#the-dashboard)
11. [Running it](#running-it)
12. [Keeping secrets safe](#keeping-secrets-safe)
13. [Cost](#cost)
14. [Problems I ran into](#problems-i-ran-into)
15. [What I would add next](#what-i-would-add-next)

## How it fits together

![Architecture](docs/images/02-architecture.png)

1. The simulator creates one GPS ping per tiger on every tick and sends it to Event Hubs.
2. Event Hubs holds the stream until something reads it.
3. The consumer reads each ping and saves it in Azure SQL. If the ping shows an anomaly, the consumer also logs it and calls the alert endpoint.
4. Azure Functions read from SQL and return JSON.
5. The dashboard calls the API and draws everything on Azure Maps.

## Tools used

| Part | Tool |
|---|---|
| Simulation | Python 3.11 |
| Event stream | Azure Event Hubs |
| Database | Azure SQL Database (serverless) |
| API | Azure Functions (Python) |
| Map | Azure Maps Web SDK |
| Monitoring | Azure Monitor action group and metric alert, plus a budget |
| Infrastructure | Terraform with the azurerm provider |
| Frontend | One HTML file with plain JavaScript |

## Folder layout

```
Faunoryx/
  Simulator/      animal_position_script.py and the reserve GeoJSON
  consumer/       consumer.py and sql_writer.py
  function_app/   function_app.py
  dashboard/      index.html and the reserve GeoJSON
  terraform/      main.tf, variables.tf, outputs.tf
  docs/images/    screenshots used in this README
```

## The simulator

The simulator lives in `Simulator/animal_position_script.py`. It creates 149 tigers and moves each one on every tick. The tick length comes from `tick_seconds` in the `.env` file. The default is 1800 seconds (30 minutes), which feels right for a real jungle. For demos I set it to 30 so the map changes while you watch.

### Classes

The script has four classes.


| Class | What it does |
|---|---|
| `GeoUtils` | Loads the reserve polygon from the GeoJSON file and checks whether a point is inside it |
| `Animal` | Keeps the state of one tiger such as its ID, position, behaviour and how long it has been still |
| `TelemetryPublisher` | Wraps the Event Hubs producer and sends the pings |
| `Simulator` | Runs the tick loop, moves the tigers, runs the checks and builds each ping |

### Behaviours

On every tick a tiger is in one of three behaviours.

| Behaviour | Meaning |
|---|---|
| normal | Walking around in small steps, sometimes staying put |
| sustained-fast | Travelling fast for a while. This is always counted as a speed anomaly |
| hunting | A short sprint. It only counts as an anomaly if the speed goes over the top limit |

### How speed is worked out

Each move changes the latitude and longitude a little. To get the real distance between the old and new point I use the haversine formula. It measures distance along the curve of the Earth, so the result is in real kilometres.

```
a = sin(dlat / 2)^2 + cos(lat1) * cos(lat2) * sin(dlon / 2)^2
c = 2 * atan2(sqrt(a), sqrt(1 - a))
distance_km = 6371 * c
speed_kmph = distance_km / (tick_seconds / 3600)
```

I did not use straight-line distance on raw degrees because a degree of longitude gets shorter the further you are from the equator. That would give the wrong speed.

### Anomaly checks

Three checks run on every ping.

| Check | Rule | Flag in the ping |
|---|---|---|
| Stillness | No real movement for 12 hours or more | `still` |
| Speed | Speed above the limit (65 km/h) for the tiger's behaviour | `speed_anomaly` |
| Boundary | The new position is outside the reserve polygon | `outside_boundary` |

Sustained-fast is always flagged. Hunting is flagged above 65 km/h

Tigers are not pushed back inside the boundary after a step. If one wanders out it can keep going. That is on purpose, so boundary events can really happen.



### The ping

Each ping is one JSON message.

```json
{
  "animal_id": "T042",
  "timestamp": "2026-10-09T10:15:00+00:00",
  "lat": 11.9821,
  "lon": 76.2874,
  "speedkmph": 2.4,
  "still": false,
  "speed_anomaly": false,
  "outside_boundary": false,
  "behaviour": "normal"
}
```

Timestamps are in UTC. The key in the ping is `speedkmph` without an underscore. The SQL column is `speed_kmph`, and the SQL writer maps one to the other.

## Terraform

One `terraform apply` creates everything and one `terraform destroy` removes it.

![Resources in the Azure portal](docs/images/03-azure-resources.png)

### main.tf

| Resource | Name in Azure | Purpose |
|---|---|---|
| Resource group | `faunoryx-rg` | Holds everything |
| Event Hubs namespace | `faunoryx-ns` | Hosts the event hub `animal-telemetry` |
| Event Hub authorization rules | `send-policy` and `listen-policy` | The simulator can only send and the consumer can only listen |
| SQL server and database | `faunoryx-sqlserver` and `faunoryx-db` | Stores the data. The database is serverless and pauses when idle |
| SQL firewall rule | | Lets my IP and Azure services connect |
| Storage account | `faunofuncstorage` | Needed by the Function App |
| App Service plan | `faunofuncservice` | Hosts the function |
| Function App | `faunoryx-alert-func` | The Python API |
| Azure Maps account | `faunomap` | Gives the dashboard its map key |
| Action group | `faunogroup` | Sends alert emails |
| Metric alert | `faunoryx-func-error-alert` | Fires when the Function App has errors |
| Consumption budget | | Warns at 50%,80% and 100% of the monthly limit |

### variables.tf

| Variable | What it is |
|---|---|
| `my_ip` | My public IP, allowed through the SQL firewall |
| `sql_admin_password` | SQL admin password. Marked sensitive and passed when applying |
| `alert_email` | Where alert and budget emails go. It has to be a real address |
| `budget_start_date` | Must be the first day of a month |



### outputs.tf

| Output | Used for |
|---|---|
| `maps_primary_key` | Goes in the dashboard config as the Azure Maps key |
| `function_app_hostname` | Used to build the API address for the dashboard |

The Event Hub connection strings and the function key are fetched with the Azure CLI. The commands are in [Running it](#running-it).

## Consumer and SQL writer

`consumer/consumer.py` connects to the event hub with the listen connection string and the `$Default` consumer group. Every event goes to a handler that reads the JSON and writes the ping to `AnimalTelemetry`. If any anomaly flag is set, it also writes a row to `MovementAnomalies` and calls the `/alert` endpoint of the Function App. The script runs with `asyncio.run(main())`.

`consumer/sql_writer.py` has one class called `SQL` that holds the database connection (pyodbc with ODBC Driver 18).

| Method | What it does |
|---|---|
| `__init__` | Opens the connection |
| `insert_telemetry(ping)` | Adds a row to `AnimalTelemetry` |
| `insert_anomaly(ping, anomaly_type)` | Adds a row to `MovementAnomalies` |
| `close()` | Closes the connection |

All queries use `?` placeholders instead of string formatting.

## Database tables

```sql
CREATE TABLE AnimalTelemetry(
  id INT IDENTITY PRIMARY KEY,
  animal_id VARCHAR(20),
  timestamp DATETIME2,
  lat FLOAT,
  lon FLOAT,
  speed_kmph FLOAT,
  still BIT,
  speed_anomaly BIT,
  outside_boundary BIT,
  behaviour VARCHAR(20)
);

CREATE TABLE MovementAnomalies(
  id INT IDENTITY PRIMARY KEY,
  animal_id VARCHAR(20),
  timestamp DATETIME2,
  lat FLOAT,
  lon FLOAT,
  anomaly_type VARCHAR(50)
);
```

## Azure Functions API

`function_app/function_app.py` is the only thing the dashboard talks to. Each request opens a database connection, runs a query and returns JSON.

| Endpoint | Auth | What it returns |
|---|---|---|
| `GET /api/positions` | None | Latest position, speed, flags and behaviour for every tiger |
| `GET /api/history?animal_id=T149` | None | Past positions of one tiger, used to draw its path |
| `GET /api/stats` | None | Counts per behaviour, still and outside counts, average speed and the five fastest tigers |
| `GET /api/recent-anomalies` | None | The last 20 rows from `MovementAnomalies` |
| `GET /api/trend` | None | Anomalies grouped by hour and type |
| `POST /api/alert` | Function key | Takes an anomaly from the consumer and logs a warning |

Here is what `/api/positions` returns. Normal tigers move well under 1 km/h while the two sustained-fast tigers at the top of the list are at 50 and 38 km/h and are flagged.

![API response](docs/images/04-api-response.png)

The browser calls the API from another origin, so CORS has to be switched on:

```
az functionapp cors add --resource-group faunoryx-rg --name faunoryx-alert-func --allowed-origins "*"
```

## Alerts

There are three kinds of alerts and they work differently.

1. Tiger anomalies. The consumer saves each one in `MovementAnomalies` and posts it to `/api/alert`. The function writes a warning line to the Azure log. The dashboard alert list reads from the table.
2. Function errors. A metric alert on the Function App sends an email through the action group when requests fail.
3. Cost. The budget sends an email at 50%, 80% and 100% of the limit.



## The dashboard

The dashboard is a single file, `dashboard/index.html`. It uses the Azure Maps Web SDK. For the map setup I started from the Azure Maps documentation and the open source Azure Maps code samples, then built the layout around our data.

### What is on screen

- The reserve boundary drawn from the real GeoJSON file. The map can be zoomed and dragged.
- One pin per tiger, coloured by status.
- A left panel with the count for each status and the current weather at the reserve.
- A bottom strip with alerts, average speed, an anomaly trend for the last 24 hours and recent activity.
- A header with the tiger count, alert count, average speed, a refresh rate selector and a light and dark switch.
- A small tiger at the bottom left that walks across the empty space under the weather card and rests now and then.

| Colour | Meaning |
|---|---|
| Green | normal |
| Blue | still |
| Amber | hunting |
| Red | anomaly |
| Gold ring | outside the reserve |

### Focus mode

Click any pin and the map narrows down to that tiger.

1. All other pins disappear.
2. The map zooms to fit the tiger and its path.
3. The path is drawn as a solid line inside the reserve and a dotted line outside it.
4. The left panel shows the tiger's ID, status, speed, behaviour, flags and last update.
5. The back link brings every pin back and returns to the earlier view.

![Focus mode](docs/images/05-focus-mode.png)

### How the dashboard reads the API

On load and on every refresh the page calls `/positions`, `/stats`, `/recent-anomalies` and `/trend`. Clicking a pin calls `/history` for that tiger. To decide which parts of a path are inside the reserve, the browser runs a point in polygon test against the same GeoJSON file. If the API cannot be reached, the page falls back to generated demo data so the map is never empty.

Weather comes from Open-Meteo, a free service that needs no API key. The page calls it directly from the browser, using the centre point of the reserve boundary.



### Light and dark

The switch in the header changes both the page and the map style.

![Light theme](docs/images/06-light-theme.png)

![Dark theme](docs/images/07-dark-theme.png)

## Running it

These steps are for Windows PowerShell. You need the Azure CLI, Terraform, Azure Functions Core Tools, Python 3.11 and ODBC Driver 18 for SQL Server.

### 1. Create the Azure resources

```powershell
az login --use-device-code
Invoke-RestMethod https://api.ipify.org

cd terraform
terraform init
terraform apply -var="my_ip=<YOUR_IP>" -var="sql_admin_password=<YOUR_PASSWORD>"
```

### 2. Get the keys

```powershell
terraform output -raw maps_primary_key
terraform output -raw function_app_hostname

az eventhubs eventhub authorization-rule keys list --resource-group faunoryx-rg --namespace-name faunoryx-ns --eventhub-name animal-telemetry --name send-policy --query primaryConnectionString -o tsv

az eventhubs eventhub authorization-rule keys list --resource-group faunoryx-rg --namespace-name faunoryx-ns --eventhub-name animal-telemetry --name listen-policy --query primaryConnectionString -o tsv

az sql server show --name faunoryx-sqlserver --resource-group faunoryx-rg --query fullyQualifiedDomainName -o tsv
```

### 3. Create the tables

In the Azure portal open `faunoryx-db`, go to the Query editor and run the SQL from [Database tables](#database-tables).

### 4. Deploy the API

```powershell
cd function_app
func azure functionapp publish faunoryx-alert-func --python
az functionapp cors add --resource-group faunoryx-rg --name faunoryx-alert-func --allowed-origins "*"

az functionapp function keys list --resource-group faunoryx-rg --name faunoryx-alert-func --function-name alert --query default -o tsv
```

### 5. Fill in the config

`consumer/.env`

```
eventhub_name=animal-telemetry
listen_conn_str=<listen connection string>
sql_server=<SQL server hostname>
sql_database=faunoryx-db
sql_username=faunoryxadmin
sql_password=<SQL password>
function_url=https://faunoryx-alert-func.azurewebsites.net/api/alert?code=<function key>
```

`Simulator/.env`

```
conn_str=<send connection string>
eventhub_name=animal-telemetry
tick_seconds=30
```

`dashboard/index.html`, in the `CONFIG` block:

```js
AZURE_MAPS_KEY: "<maps key>",
API_BASE: "https://faunoryx-alert-func.azurewebsites.net/api",
```

### 6. Start everything

Use three terminals and start the consumer first.

```powershell
cd consumer
python consumer.py
```

```powershell
cd Simulator
python animal_position_script.py
```

```powershell
cd dashboard
python -m http.server 8000
```

Open http://localhost:8000. Do not open the HTML file directly because the GeoJSON is loaded over HTTP. Start the web server inside the `dashboard` folder and not the project root.

## Keeping secrets safe

- Never commit `terraform.tfstate`, the `.terraform` folder or any `.env` file. The state file holds keys and the SQL password in plain text.
- Do not share the Maps key, the function key or any connection string in screenshots or public repos.
- The simulator only has a send key and the consumer only has a listen key.
- The SQL firewall only lets my IP through. If my network changes I add a new rule or run apply again with the new IP.
- `allowed-origins "*"` is fine for a demo but should be limited for real use.

## Cost

The database is serverless and pauses when idle, and the budget emails me before spending gets out of hand. When I am done I run:

```powershell
cd terraform
terraform destroy -var="my_ip=<YOUR_IP>" -var="sql_admin_password=<YOUR_PASSWORD>"
```

This deletes the data and every key. After the next apply the keys have to be fetched again and put back into the config files.

## Problems I ran into

| What I saw | Why it happened | Fix |
|---|---|---|
| `Client with IP address ... is not allowed to access the server` | My IP changed | Add a SQL firewall rule or apply again with the new IP |
| `CBS Token authentication failed` in the consumer | Old or wrong Event Hubs connection string | Fetch the listen string again and restart |
| Blank map with no boundary | Wrong Azure Maps key, or the browser blocked the map script | Check the key and turn off the browser shield for localhost |
| Map and boundary load but no pins | `/api/positions` returned an empty list | Make sure the consumer and simulator are running |
| `/api/recent-anomalies` returned an error | A typo in the function code (`curor`) | Fix it and publish the function again |
| Directory listing instead of the dashboard | Web server started in the wrong folder | Start it inside `dashboard` |
| Budget failed with a connection reset | Network error during apply | Run `terraform apply` again |

## What I would add next

- An email or Teams message for each tiger anomaly.
- A login for the API and a tighter CORS setting.
- Hosting the dashboard on Azure Static Web Apps.
