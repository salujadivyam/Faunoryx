variable "resource_group_name" {
  default = "faunoryx-rg"
}

variable "location" {
  default = "Malaysia West"
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

variable "monthly_budget_usd" {
  default = 30
}

variable "budget_start_date" {
  default = "2026-09-01T00:00:00Z"   #first day of current month, UTC
}

variable "alert_email" {
  default = "DIVYAM.ADT@GMAIL.COM"
}
