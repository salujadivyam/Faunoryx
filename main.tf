terraform{
    required_providers{
        azurerm={
            source="hashicorp/azurerm"
            version="~>4.0"
        
        }
    }
}
provider "azurerm"{
    features{}
}
resource "azurerm_resource_group" "rg"{
    name=var.resource_group_name
    location=var.location
}
resource "azurerm_eventhub_namespace" "ns"{
    name=var.eventhub_namespace_name
    location=azurerm_resource_group.rg.location
    resource_group_name=azurerm_resource_group.rg.name
    sku=var.sku
    capacity=1
}
resource "azurerm_eventhub" "hub"{
    name=var.eventhub_name
    namespace_id=azurerm_eventhub_namespace.ns.id
    partition_count=2
    message_retention=1
}

resource "azurerm_eventhub_authorization_rule" "send"{
    name="send-policy"
    namespace_name=azurerm_eventhub_namespace.ns.name
    eventhub_name=azurerm_eventhub.hub.name
    resource_group_name=azurerm_resource_group.rg.name
    listen=false
    send=true
    manage=false
}

resource "azurerm_eventhub_authorization_rule" "listen"{
    name="listen-policy"
    namespace_name=azurerm_eventhub_namespace.ns.name
    eventhub_name=azurerm_eventhub.hub.name
    resource_group_name=azurerm_resource_group.rg.name
    listen=true
    send=false
    manage=false
}

resource "azurerm_consumption_budget_resource_group" "budget" {
  name="faunoryx-budget"
  resource_group_id=azurerm_resource_group.rg.id
  amount=var.monthly_budget_usd
  time_grain="Monthly"

  time_period {
    start_date=var.budget_start_date
  }

  notification {
    enabled=true
    threshold=80.0
    operator="GreaterThan"
    contact_emails=[var.alert_email]
  }

  notification {
    enabled=true
    threshold=100.0
    operator="GreaterThan"
    contact_emails=[var.alert_email]
  }
}

resource "azurerm_mssql_server" "sql_server" {
  name="faunoryx-sqlserver"
  resource_group_name=azurerm_resource_group.rg.name
  location=azurerm_resource_group.rg.location
  version="12.0"
  administrator_login=var.sql_admin_username
  administrator_login_password=var.sql_admin_password
}

resource "azurerm_mssql_database" "sql_db" {
  name="faunoryx-db"
  server_id=azurerm_mssql_server.sql_server.id
  sku_name="GP_S_Gen5_2"
  max_size_gb=32
  storage_account_type="Local"
  min_capacity=0.5
  auto_pause_delay_in_minutes=60
}

resource "azurerm_mssql_firewall_rule" "allow_azure" {
  name="AllowAzureServices"
  server_id=azurerm_mssql_server.sql_server.id
  start_ip_address="0.0.0.0"
  end_ip_address="0.0.0.0"
}