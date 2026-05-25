# Fastems MMS integration

Odoo 17 module that integrates Odoo with **Fastems MMS** (Manufacturing Management Software) via REST API (MMS-3010 ERP Interface).

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Architecture](#architecture)
- [Testing in a Development Environment](#testing-in-a-development-environment)
- [License](#license)

---

## Features

| Direction | Operation | MMS endpoint |
|---|---|---|
| Odoo → MMS | Create production order | `POST /erp/orders/productionorder` |
| Odoo → MMS | Delete production order | `DELETE /erp/orders/productionorder` |
| MMS → Odoo | Fetch production reports → update work order state | `GET /erp/reports/bufferdata` |

### Work Order State Mapping

MMS report messages automatically update the Odoo `mrp.workorder` state:

| MMS discriminator | Odoo workorder state |
|---|---|
| `operation-started` | `progress` |
| `parts-produced` | `progress` |
| `operation-completed` | `done` |
| `orders-completed` | closes `mrp.production` |
| `orders-started`, `parts-scrapped` | logged only, no state change |

---

## Requirements

- Odoo 17.0
- [`queue_job`](https://github.com/OCA/queue) module (OCA)
- Python `requests` library (included in standard Odoo installations)
- Fastems MMS 8.1+ with REST API functionality

---

## Installation

### 1. Copy the module to your addons folder

```bash
cp -r fastems_mms_integration /mnt/extra-addons/
```

### 2. Add `queue_job` to server_wide_modules

`odoo.conf`:

```ini
[options]
server_wide_modules = base,web,queue_job
```

### 3. Start an Odoo worker for queue jobs (docker-compose example)

`docker-compose.yml`:

```yaml
odoo-worker:
  image: odoo:17
  depends_on:
    - postgres
    - odoo
  volumes:
    - ./odoo/addons:/mnt/extra-addons
    - ./odoo/config:/etc/odoo
  environment:
    HOST: postgres
    USER: odoo
    PASSWORD: odoo
  command: >
      bash -c "sleep 30 && odoo
      --db_host=postgres
      --db_user=odoo
      --db_password=odoo
      --database=odoo
      --max-cron-threads=0
      --no-http"
```

### 4. Install the module in Odoo

Apps → Update Apps List → search `MMS` → Install Fastems MMS Integration

---

## Configuration

### Backend

**MMS Integration → Backends → New**

| Field | Description |
|---|---|
| Name | Descriptive name, e.g. `MMS Production` |
| API URL | MMS server address, e.g. `http://mms-server:8080` |
| Auth Method | `HTTP Basic` or `ApiKey` |
| Username / Password | Credentials for HTTP Basic authentication |
| API Key | Key for ApiKey authentication |
| Export Production Orders | Enable automatic export of production orders |
| Import Production Reports | Enable automatic import of manufacturing reports |
| Report Batch Size | Number of reports fetched per polling cycle (default: 100) |

Use the **Test Connection** button to verify connectivity, a success message confirms the API is reachable.

### Binding

**MMS Integration → Production Order Bindings → New**

| Field | Description |
|---|---|
| Manufacturing Order | The Odoo production order |
| Backend | The MMS backend to use |
| MMS Order Number | OrderNumber in MMS, usually the same as the Odoo order name |
| MMS Part Master Data | Part name in MMS, must already exist in MMS before sending |
| MMS Order Status | `Released` or `Urgent` |

### Work Order Matching

The module matches the MMS `OperationNumber` to an Odoo `mrp.workorder` using two strategies:

1. **Workcenter name** - the workcenter whose name ends with the operation number integer (e.g. workcenter `"Fms 5 - 10"` matches MMS op `10`)
2. **Positional fallback** - op `10` → index 0, op `20` → index 1, and so on

---

## Usage

### Exporting a Production Order to MMS (POST)

1. Create a binding linking a Manufacturing Order to a backend
2. The cron **MMS: Export Production Orders** runs every 10 minutes and enqueues a queue job per pending binding
3. The queue job sends `POST /erp/orders/productionorder`
4. On success `mms_id` is populated and `sync_state` becomes `done`

You can also export manually using the **Export to MMS** button on the binding form.

### Deleting a Production Order from MMS (DELETE)

Click **Delete from MMS** on the binding form.

> **Note:** MMS will reject the deletion if any parts are currently in progress for the order.

### Importing Manufacturing Reports from MMS (GET)

1. The cron **MMS: Import Production Reports** runs every 5 minutes
2. Fetches new reports from `GET /erp/reports/bufferdata` starting from `last_report_message_number`
3. Each report is dispatched to the matching binding, which finds the correct work order and applies the state transition using standard Odoo button methods

---

## Architecture

```
fastems_mms_integration/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── mms_api_request_mixin.py        # URL building, auth, headers, error handling
│   ├── mms_binding_mixin.py            # Abstract: external ID, sync state, on/off flag
│   ├── mms_backend.py                  # Settings, test connection, cron entry-points
│   └── mms_production_order_binding.py # POST, DELETE, report processing
├── views/
│   ├── mms_backend_views.xml
│   └── mms_production_order_binding_views.xml
├── data/
│   └── ir_cron_data.xml
└── security/
    └── ir.model.access.csv
```

### Design

- **API request mixin** - all HTTP logic in one place: URL construction, authentication, headers, error handling
- **Binding mixin** - abstract base providing external ID tracking and sync state management
- **Backend** - integration settings and cron trigger methods only
- **Crons are triggers only** - no business logic inside cron methods, all work is done in queue jobs
- **Queue jobs** - every API call is executed by the queue_job worker, enabling retries and error visibility

---

## Testing in a Development Environment

You can test the full integration flow without a real MMS connection using a Flask mock server.

### Project Structure

```
project/
├── docker-compose.yml
├── odoo/
│   ├── addons/
│   │   └── fastems_mms_integration/
│   ├── config/
│   │   └── odoo.conf
│   └── scripts/
│       └── init_odoo.sh
└── mms_mock/
    ├── Dockerfile
    └── mock_mms.py
```

### Mock Server

**`mms_mock/mock_mms.py`:**

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/erp/orders/productionorder", methods=["POST"])
def create_order():
    print("MMS POST order:", request.json)
    return jsonify({}), 200

@app.route("/erp/orders/productionorder", methods=["DELETE"])
def delete_order():
    print("MMS DELETE order:", request.args)
    return jsonify({}), 200

@app.route("/erp/reports/bufferdata")
def get_reports():
    return jsonify({
        "QueriedReportCount": 1,
        "NewReportsRemaining": 0,
        "Reports": [
            {
                "discriminator": "operation-started",
                "OrderNumber": "WH/MO/00001",  # update to match your Odoo order name
                "OperationNumber": "10",
                "MessageNumber": 1,
            }
        ]
    })

# debug=True enables auto-reload on file changes
app.run(host="0.0.0.0", port=8080, debug=True)
```

**`mms_mock/Dockerfile`:**

```dockerfile
FROM python:3.11-slim
RUN pip install flask
WORKDIR /app
COPY mock_mms.py .
CMD ["python3", "mock_mms.py"]
```

### docker-compose.yml

```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
    volumes:
      - postgres-data:/var/lib/postgresql/data

  odoo:
    image: odoo:17
    depends_on:
      - postgres
      - mms_mock
    ports:
      - "8069:8069"
    volumes:
      - ./odoo/addons:/mnt/extra-addons
      - ./odoo/config:/etc/odoo
      - ./odoo/scripts:/scripts
    environment:
      HOST: postgres
      USER: odoo
      PASSWORD: odoo
      ODOO_DB: odoo
    command: ["/scripts/init_odoo.sh"]

  odoo-worker:
    image: odoo:17
    depends_on:
      - postgres
      - odoo
    volumes:
      - ./odoo/addons:/mnt/extra-addons
      - ./odoo/config:/etc/odoo
    environment:
      HOST: postgres
      USER: odoo
      PASSWORD: odoo
    command: >
      bash -c "sleep 30 && odoo
      --db_host=postgres
      --db_user=odoo
      --db_password=odoo
      --database=odoo
      --max-cron-threads=0
      --no-http"

  mms_mock:
    build: ./mms_mock
    ports:
      - "8080:8080"
    volumes:
      - ./mms_mock:/app  # live reload without restarting the container

volumes:
  postgres-data:
```

### odoo.conf

```ini
[options]
db_host = postgres
db_port = 5432
db_user = odoo
db_password = odoo

addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons

server_wide_modules = base,web,queue_job  # required for queue_job to work

log_level = info
```

### Step-by-Step Testing

**1. Start the environment**

```bash
docker-compose up -d
```

**2. Create test data in Odoo** (`http://localhost:8069`)

- **Work Center:** Manufacturing → Configuration → Work Centers → New → `FMS Op 10`
- **Product:** Inventory → Products → New → `Test Part MMS`
- **Bill of Materials:** Manufacturing → Bills of Materials → New → add operation `Op 10` on work center `FMS Op 10`
- **Manufacturing Order:** Manufacturing → Manufacturing Orders → New → Confirm → copy the order name (e.g. `WH/MO/00001`)

**3. Update the mock with the correct order number**

In `mms_mock/mock_mms.py` set `"OrderNumber"` to match the order you just created. Flask's auto-reload will pick up the change automatically.

**4. Create a backend in Odoo**

MMS Integration → Backends → New:
- API URL: `http://mms_mock:8080`
- Auth Method: `HTTP Basic`
- Username: `test`, Password: `test`
- Click **Test Connection** → should show "Connection successful"

**5. Create a binding**

MMS Integration → Production Order Bindings → New:
- Manufacturing Order: `WH/MO/00001`
- MMS Order Number: `WH/MO/00001`
- MMS Part Master Data: `PRT-TEST`

**6. Run the cron manually**

Enable debug mode: `http://localhost:8069/web?debug=1`

Settings → Technical → Automation → Scheduled Actions → `MMS: Import Production Reports` → **Run Manually**

**7. Check the logs**

```bash
docker logs -f <odoo-container>
```

A successful run looks like:

```
INFO ... MMS report #1: discriminator=operation-started  order=WH/MO/00001  op=10
INFO ... MMS: workorder 1 ('Op 10') on WH/MO/00001: pending → progress
```

The Work Orders tab on the manufacturing order should now show the updated state.

### Testing Different Report Types

Change the `discriminator` value in `mock_mms.py` and run the cron again:

| discriminator | Expected result |
|---|---|
| `operation-started` | work order → `progress` |
| `operation-completed` | work order → `done` |
| `orders-completed` | manufacturing order is closed |

---

## License

[AGPL-3](LICENSE)
