terraform{
    required_providers{
        azurerm={
            source="hashicorp/azurerm"
            version="~>3.0"
        
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