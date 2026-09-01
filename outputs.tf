output "eventhub_send_connection_string" {
  value     = azurerm_eventhub_authorization_rule.send.primary_connection_string
  sensitive = true
}
output "eventhub_listen_connection_string" {
  value     = azurerm_eventhub_authorization_rule.listen.primary_connection_string
  sensitive = true
}
output "eventhub_name" {
  value = azurerm_eventhub.hub.name
}
output "sql_server_fqdn" {
  value = azurerm_mssql_server.sql_server.fully_qualified_domain_name
}
output "sql_database_name" {
  value = azurerm_mssql_database.sql_db.name
}