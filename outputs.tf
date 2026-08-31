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
