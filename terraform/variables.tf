variable "resource_group_name" {
  default = "faunoryx-rg"
}

variable "location" {
  default="Central India"
}

variable "eventhub_namespace_name" {
  default = "faunoryx-ns"
}

variable "eventhub_name" {
  default = "animal-telemetry"
}

variable "sku" {
  default = "Basic"
}

variable "monthly_budget" {
  default = 1000
}

variable "budget_start_date" {
  default = "2026-11-01T00:00:00Z"   #first day of current month, UTC
}

variable "alert_email" {
  default = "DIVYAM.ADT@GMAIL.COM"
}

variable "sql_admin_username"{
  default="faunoryxadmin"
}

variable "sql_admin_password"{
  sensitive=true
}

variable "my_ip"{
  sensitive=true
}